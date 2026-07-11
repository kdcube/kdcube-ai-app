# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""ReAct subagent spawner: charter-scoped child conversations.

``react.delegate`` hands this spawner a charter; the spawner opens a CHILD
conversation (same tenant/project/user, fresh conversation id), seeds its
timeline with the fork projection, authors the charter onto the child's
event lane (author = the parent agent), and runs a full react agent there in
a background task — built through the same ``build_react`` path as the
user-facing agent, with the child's browser/comm swapped in. The child's
communicator is silent: a deny-all event filter stops every emission at the
communicator's single choke point, so nothing the child does streams to the
user. The child reports back through the parent conversation's event lane
(``subagent.contribution`` en route, one terminal ``subagent.converged`` or
``subagent.failed``).
"""

from __future__ import annotations

import asyncio
import copy
import time
import traceback
from typing import Any, Dict, List, Optional, Set

from kdcube_ai_app.apps.chat.emitters import ChatCommunicator
from kdcube_ai_app.apps.chat.ids import timestamped_id, new_turn_id
from kdcube_ai_app.apps.chat.sdk.protocol import ExternalEventPayload
from kdcube_ai_app.apps.chat.sdk.runtime.comm_ctx import bind_current_request_context
from kdcube_ai_app.apps.chat.sdk.runtime.scratchpad import TurnScratchpad
from kdcube_ai_app.apps.chat.sdk.runtime.agent_inventory import (
    USER_MODEL_TARGET_ROLE,
    match_supported_model,
    normalize_model_pick,
    react_supported_models,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.proto import RuntimeCtx
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.charter import SubagentCharter
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.events import (
    SUBAGENT_CHARTER_EVENT_KIND,
    SUBAGENT_CONVERGED_EVENT_KIND,
    SUBAGENT_FAILED_EVENT_KIND,
    ParentLaneAddress,
    build_lane_source,
    publish_subagent_event,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.fork import FORK_HEADER_BLOCK_TYPE
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.launch import (
    SubagentLaunchRequest,
    SubagentLaunchTicket,
)
from kdcube_ai_app.infra import accounting as _accounting
from kdcube_ai_app.infra.accounting import with_accounting

# Component/metadata tag under which subagent spend is identifiable.
SUBAGENT_ACCOUNTING_AGENT = "react.subagent"

# Keep strong references to running child tasks (a bare create_task result is
# collectable) and let completed ones fall away.
_ACTIVE_SUBAGENT_TASKS: Set[asyncio.Task] = set()


class _DenyAllEventFilter:
    """Silent-v1 visibility: every communicator emission is filtered out at
    ``ChatCommunicator.emit`` — the single choke point all high-level methods
    (delta/step/event/service_event/complete/error) funnel through."""

    def allow_event(self, **_kwargs) -> bool:
        return False


def build_silent_child_comm(
    parent_comm: ChatCommunicator,
    *,
    conversation_id: str,
    turn_id: str,
) -> ChatCommunicator:
    """A communicator for the child that reaches no user.

    It keeps the parent's transport and service identity (hosting and
    accounting read tenant/project/user from ``comm.service``) but carries
    the CHILD conversation ids and a deny-all event filter."""
    return ChatCommunicator(
        emitter=parent_comm.emitter,
        tenant=parent_comm.tenant,
        project=parent_comm.project,
        user_id=parent_comm.user_id,
        user_type=parent_comm.user_type,
        service=dict(parent_comm.service or {}),
        conversation={
            "session_id": "",
            "conversation_id": conversation_id,
            "turn_id": turn_id,
        },
        room=None,
        target_sid=None,
        event_filter=_DenyAllEventFilter(),
    )


def _isolate_accounting_context() -> None:
    """Give the child task its OWN AccountingContext object.

    ``asyncio.create_task`` copies contextvars, but the copied var still
    points at the parent's mutable context object; overlaying child ids on
    it would corrupt the parent turn's accounting mid-flight. A fresh object
    seeded with the same fields keeps the child fully attributed without
    sharing state."""
    fresh = _accounting.AccountingContext()
    try:
        fresh.update(**(_accounting.get_context() or {}))
        fresh.event_enrichment = dict(_accounting.get_enrichment() or {})
    except Exception:
        pass
    _accounting._set_context(fresh)


def _child_comm_context(
    parent_payload: Any,
    *,
    conversation_id: str,
    turn_id: str,
) -> Any:
    """The child's ExternalEventPayload: parent identity, child routing, no
    live socket."""
    try:
        data = parent_payload.model_dump() if parent_payload is not None else {}
    except Exception:
        data = {}
    routing = dict(data.get("routing") or {})
    routing.setdefault("bundle_id", "")
    routing.setdefault("session_id", "")
    routing["conversation_id"] = conversation_id
    routing["turn_id"] = turn_id
    routing["socket_id"] = None
    data["routing"] = routing
    return ExternalEventPayload.model_validate(data)


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ReactSubagentSpawner:
    """Spawns and runs charter-scoped subagents for one workflow."""

    def __init__(self, *, workflow: Any, build_template: Dict[str, Any]) -> None:
        self.workflow = workflow
        self.build_template = dict(build_template or {})

    # ---- public API (awaited by react.delegate) ----

    async def spawn(self, request: SubagentLaunchRequest) -> SubagentLaunchTicket:
        if int(request.parent_depth or 0) >= 1:
            raise RuntimeError("subagent depth limit: a subagent cannot spawn subagents")
        redis = self._redis()
        if redis is None:
            raise RuntimeError("subagent spawning needs the conversation event lane (redis)")
        child_conversation_id = timestamped_id("sub", suffix_chars=6)
        child_turn_id = new_turn_id()
        task = asyncio.create_task(
            self._run_child(
                request=request,
                redis=redis,
                child_conversation_id=child_conversation_id,
                child_turn_id=child_turn_id,
            ),
            name=f"react.subagent.{child_conversation_id}",
        )
        _ACTIVE_SUBAGENT_TASKS.add(task)
        task.add_done_callback(_ACTIVE_SUBAGENT_TASKS.discard)
        return SubagentLaunchTicket(
            child_conversation_id=child_conversation_id,
            child_turn_id=child_turn_id,
            status="started",
        )

    # ---- internals ----

    def _redis(self) -> Any:
        redis = getattr(self.workflow, "redis", None)
        if redis is not None:
            return redis
        parent_ctx = getattr(self.workflow, "runtime_ctx", None)
        source = getattr(parent_ctx, "external_event_source", None)
        return getattr(source, "redis", None)

    def _log(self, message: str, level: str = "INFO") -> None:
        try:
            self.workflow.logger.log(f"[react.subagents] {message}", level=level)
        except Exception:
            pass

    def _resolve_child_model(self, charter: SubagentCharter) -> Optional[Dict[str, str]]:
        """The child's strong-decision model: the charter's override when it
        names an admin-allowed model, else the configured subagent default,
        else None (inherit the parent's role models)."""
        parent_ctx = getattr(self.workflow, "runtime_ctx", None)
        agent_id = getattr(parent_ctx, "agent_id", None)
        bundle_props = getattr(self.workflow, "bundle_props", None) or {}
        if charter.model:
            supported = react_supported_models(bundle_props, agent_id)
            matched = match_supported_model({"model": charter.model}, supported)
            if matched:
                return matched
            self._log(
                f"charter model {charter.model!r} is not in the admin-allowed list; "
                "using the configured subagent default",
                level="WARNING",
            )
        defaults = getattr(parent_ctx, "subagent_defaults", None) or {}
        configured = defaults.get("model")
        if isinstance(configured, str) and configured.strip():
            configured = {"model": configured.strip()}
        return normalize_model_pick(configured)

    def _build_child_runtime_ctx(
        self,
        *,
        request: SubagentLaunchRequest,
        child_conversation_id: str,
        child_turn_id: str,
        child_lane: Any,
        parent_lane: Any,
    ) -> RuntimeCtx:
        p = getattr(self.workflow, "runtime_ctx", None)
        charter = request.charter
        role_models = dict(getattr(p, "agent_role_models", None) or {})
        model_pick = self._resolve_child_model(charter)
        if model_pick and model_pick.get("model"):
            role_models[USER_MODEL_TARGET_ROLE] = {
                "provider": model_pick.get("provider") or "anthropic",
                "model": model_pick["model"],
            }
        optional_kwargs: Dict[str, Any] = {}
        if getattr(p, "session", None) is not None:
            optional_kwargs["session"] = copy.deepcopy(p.session)
        if getattr(p, "cache", None) is not None:
            optional_kwargs["cache"] = copy.deepcopy(p.cache)
        return RuntimeCtx(
            tenant=getattr(p, "tenant", None),
            project=getattr(p, "project", None),
            user_id=getattr(p, "user_id", None),
            conversation_id=child_conversation_id,
            user_type=getattr(p, "user_type", None),
            turn_id=child_turn_id,
            bundle_id=getattr(p, "bundle_id", None),
            agent_id=getattr(p, "agent_id", None) or "main",
            agent_role_models=role_models,
            timezone=getattr(p, "timezone", None),
            max_tokens=getattr(p, "max_tokens", None),
            # The charter budget IS the child's iteration budget; reactive
            # credit is off so nothing can extend it.
            max_iterations=int(charter.max_rounds or 1),
            reactive_event_iteration_credit_enabled=False,
            read_visible_max_text_symbols=getattr(p, "read_visible_max_text_symbols", None),
            read_visible_max_tokens=getattr(p, "read_visible_max_tokens", None),
            read_visible_max_bytes=getattr(p, "read_visible_max_bytes", None),
            read_visible_context_fraction=getattr(p, "read_visible_context_fraction", None),
            knowledge_read_visible_max_text_symbols=getattr(p, "knowledge_read_visible_max_text_symbols", None),
            knowledge_read_visible_max_tokens=getattr(p, "knowledge_read_visible_max_tokens", None),
            knowledge_read_visible_max_bytes=getattr(p, "knowledge_read_visible_max_bytes", None),
            exec_text_preview_max_symbols=getattr(p, "exec_text_preview_max_symbols", None),
            tool_result_preview_max_text_symbols=getattr(p, "tool_result_preview_max_text_symbols", None),
            bundle_storage=getattr(p, "bundle_storage", None),
            workspace_implementation=getattr(p, "workspace_implementation", "custom"),
            exec_runtime=copy.deepcopy(getattr(p, "exec_runtime", None) or {}),
            knowledge_search_fn=getattr(p, "knowledge_search_fn", None),
            knowledge_read_fn=getattr(p, "knowledge_read_fn", None),
            model_service=getattr(p, "model_service", None),
            external_event_source=child_lane,
            started_at=_utc_now_iso(),
            debug_log_announce=bool(getattr(p, "debug_log_announce", True)),
            announce_mode=getattr(p, "announce_mode", "full"),
            multi_action_mode=getattr(p, "multi_action_mode", "off"),
            line_numbers_mode=getattr(p, "line_numbers_mode", None) or "lines",
            render_thinking=bool(getattr(p, "render_thinking", True)),
            memory_enabled=bool(getattr(p, "memory_enabled", False)),
            memory_announce_enabled=bool(getattr(p, "memory_announce_enabled", False)),
            memory_scope_filter=getattr(p, "memory_scope_filter", "current_bundle"),
            subagent_depth=int(request.parent_depth or 0) + 1,
            subagent_parent=request.parent.to_dict(),
            subagent_parent_lane=parent_lane,
            **optional_kwargs,
        )

    async def _seed_child_timeline(
        self,
        *,
        child_ctx: RuntimeCtx,
        fork_blocks: List[Dict[str, Any]],
        child_conversation_id: str,
    ) -> None:
        """Persist the fork projection as the child conversation's history —
        the child's normal timeline load then finds it like any prior state."""
        if not fork_blocks:
            return
        from kdcube_ai_app.apps.chat.sdk.solutions.react.timeline import Timeline

        blocks: List[Dict[str, Any]] = []
        for block in fork_blocks:
            if not isinstance(block, dict):
                continue
            block = copy.deepcopy(block)
            if str(block.get("type") or "") == FORK_HEADER_BLOCK_TYPE:
                meta = dict(block.get("meta") or {})
                meta["child_conversation_id"] = child_conversation_id
                block["meta"] = meta
            blocks.append(block)
        seed = Timeline(
            runtime=child_ctx,
            svc=getattr(self.workflow, "model_service", None),
        )
        seed.blocks = blocks
        seed.conversation_started_at = _utc_now_iso()
        await seed.persist(self.workflow.ctx_client)

    async def _run_child(
        self,
        *,
        request: SubagentLaunchRequest,
        redis: Any,
        child_conversation_id: str,
        child_turn_id: str,
    ) -> None:
        charter = request.charter
        parent = request.parent
        parent_lane = build_lane_source(redis=redis, address=parent)
        child_lane = build_lane_source(
            redis=redis,
            address=ParentLaneAddress(
                tenant=parent.tenant,
                project=parent.project,
                user_id=parent.user_id,
                conversation_id=child_conversation_id,
                agent_id=parent.agent_id,
            ),
        )
        author_ref = f"agent:conv_{parent.conversation_id}/{parent.turn_id}"
        _isolate_accounting_context()
        try:
            async with with_accounting(
                str(getattr(getattr(self.workflow, "runtime_ctx", None), "bundle_id", "") or "subagent"),
                agent=SUBAGENT_ACCOUNTING_AGENT,
                conversation_id=child_conversation_id,
                turn_id=child_turn_id,
                metadata={
                    "agent": SUBAGENT_ACCOUNTING_AGENT,
                    "subagent": {
                        "parent_conversation_id": parent.conversation_id,
                        "parent_turn_id": parent.turn_id,
                        "charter_goal": charter.summary_line(),
                    },
                },
            ):
                await self._run_child_turn(
                    request=request,
                    parent_lane=parent_lane,
                    child_lane=child_lane,
                    child_conversation_id=child_conversation_id,
                    child_turn_id=child_turn_id,
                    author_ref=author_ref,
                )
        except Exception as exc:
            self._log(
                f"child run failed conversation={child_conversation_id}: {traceback.format_exc()}",
                level="ERROR",
            )
            # Failures are authored, never silenced.
            try:
                await publish_subagent_event(
                    lane_source=parent_lane,
                    semantic_type=SUBAGENT_FAILED_EVENT_KIND,
                    text=(
                        f"[SUBAGENT FAILED]\nThe subagent conv_{child_conversation_id} "
                        f"failed before converging: {exc}"
                    ),
                    facts={
                        "child_conversation_id": child_conversation_id,
                        "child_conversation_ref": f"conv_{child_conversation_id}",
                        "reason": str(exc),
                        "charter_goal": charter.summary_line(),
                    },
                    author=f"agent:conv_{child_conversation_id}/{child_turn_id}",
                    target_turn_id=parent.turn_id or None,
                )
            except Exception:
                self._log(
                    f"failed-event publish failed conversation={child_conversation_id}: {traceback.format_exc()}",
                    level="ERROR",
                )

    async def _run_child_turn(
        self,
        *,
        request: SubagentLaunchRequest,
        parent_lane: Any,
        child_lane: Any,
        child_conversation_id: str,
        child_turn_id: str,
        author_ref: str,
    ) -> None:
        charter = request.charter
        parent = request.parent
        workflow = self.workflow

        child_ctx = self._build_child_runtime_ctx(
            request=request,
            child_conversation_id=child_conversation_id,
            child_turn_id=child_turn_id,
            child_lane=child_lane,
            parent_lane=parent_lane,
        )

        # 1) The fork projection becomes the child conversation's history.
        await self._seed_child_timeline(
            child_ctx=child_ctx,
            fork_blocks=list(request.fork_blocks or []),
            child_conversation_id=child_conversation_id,
        )

        # 2) The charter is an authored event on the child's lane (author =
        #    the parent agent). Published BEFORE the timeline load, targeted
        #    at the child's turn, it folds into the child's current turn as
        #    its assignment — the same inception primitive throughout.
        await publish_subagent_event(
            lane_source=child_lane,
            semantic_type=SUBAGENT_CHARTER_EVENT_KIND,
            text=charter.charter_text(),
            facts={
                "charter": charter.to_dict(),
                "parent_conversation_id": parent.conversation_id,
                "parent_turn_id": parent.turn_id,
            },
            author=author_ref,
            target_turn_id=child_turn_id,
        )

        # 3) Child execution environment: silent comm, child payload, child
        #    browser — then the SAME build path as the user-facing agent.
        silent_comm = build_silent_child_comm(
            workflow.comm,
            conversation_id=child_conversation_id,
            turn_id=child_turn_id,
        )
        child_payload = _child_comm_context(
            getattr(workflow, "comm_context", None),
            conversation_id=child_conversation_id,
            turn_id=child_turn_id,
        )
        ContextBrowser = _child_symbol("browser", "ContextBrowser")
        ApplicationHostingService = _child_symbol("solution_workspace", "ApplicationHostingService")
        child_browser = ContextBrowser(
            ctx_client=workflow.ctx_client,
            logger=workflow.logger,
            model_service=workflow.model_service,
            runtime_ctx=child_ctx,
        )
        child_hosting = ApplicationHostingService(
            store=workflow.store,
            comm=silent_comm,
            logger=workflow.logger,
        )
        scratchpad = TurnScratchpad(
            user=child_ctx.user_id,
            conversation_id=child_conversation_id,
            turn_id=child_turn_id,
            text=charter.charter_text(),
        )
        scratchpad.started_at = child_ctx.started_at

        with bind_current_request_context(child_payload, comm=silent_comm):
            # Timeline load finds the seeded fork as history and folds the
            # charter event into the child's current turn.
            await child_browser.load_timeline(days=365)

            react = workflow.build_react(
                scratchpad,
                comm_override=silent_comm,
                comm_context_override=child_payload,
                ctx_browser_override=child_browser,
                hosting_service_override=child_hosting,
                **self.build_template,
            )
            self._log(
                f"child started conversation={child_conversation_id} turn={child_turn_id} "
                f"budget={charter.max_rounds} parent={parent.conversation_id}/{parent.turn_id}"
            )
            result = await react.run(
                allowed_plugins=list(request.allowed_plugins or []),
                allowed_tool_names_by_alias=request.allowed_tool_names_by_alias,
            )

            # 4) Close the child conversation record: completion block(s),
            #    workspace + timeline persistence.
            final_answer = str(getattr(result, "final_answer", "") or "").strip()
            try:
                from kdcube_ai_app.apps.chat.sdk.solutions.react.layout import (
                    build_assistant_completion_blocks,
                )

                if final_answer:
                    child_browser.contribute(
                        blocks=build_assistant_completion_blocks(
                            runtime=child_ctx,
                            completion_entries=list(getattr(scratchpad, "assistant_completion_attempts", []) or []),
                            final_answer_text=final_answer,
                            ended_at=_utc_now_iso(),
                            block_factory=child_browser.timeline.block,
                        ),
                    )
            except Exception:
                self._log(
                    f"child completion block failed conversation={child_conversation_id}: {traceback.format_exc()}",
                    level="ERROR",
                )
            try:
                await react.persist_workspace()
            except Exception:
                self._log(
                    f"child workspace persist failed conversation={child_conversation_id}: {traceback.format_exc()}",
                    level="ERROR",
                )
            try:
                await child_browser.persist_timeline()
            except Exception:
                self._log(
                    f"child timeline persist failed conversation={child_conversation_id}: {traceback.format_exc()}",
                    level="ERROR",
                )

        # 5) Terminal event on the parent lane.
        ok = bool(getattr(result, "ok", False)) and bool(final_answer)
        if ok:
            text_lines = [
                "[SUBAGENT CONVERGED]",
                f"Subagent conv_{child_conversation_id} completed its charter.",
                "",
                final_answer,
            ]
            await publish_subagent_event(
                lane_source=parent_lane,
                semantic_type=SUBAGENT_CONVERGED_EVENT_KIND,
                text="\n".join(text_lines),
                facts={
                    "child_conversation_id": child_conversation_id,
                    "child_conversation_ref": f"conv_{child_conversation_id}",
                    "final_answer": final_answer,
                    "charter_goal": charter.summary_line(),
                },
                author=f"agent:conv_{child_conversation_id}/{child_turn_id}",
                target_turn_id=parent.turn_id or None,
            )
            self._log(f"child converged conversation={child_conversation_id}")
        else:
            reason = str(getattr(result, "error", "") or "no final answer within budget")
            await publish_subagent_event(
                lane_source=parent_lane,
                semantic_type=SUBAGENT_FAILED_EVENT_KIND,
                text=(
                    f"[SUBAGENT FAILED]\nSubagent conv_{child_conversation_id} "
                    f"stopped without converging: {reason}"
                ),
                facts={
                    "child_conversation_id": child_conversation_id,
                    "child_conversation_ref": f"conv_{child_conversation_id}",
                    "reason": reason,
                    "charter_goal": charter.summary_line(),
                },
                author=f"agent:conv_{child_conversation_id}/{child_turn_id}",
                target_turn_id=parent.turn_id or None,
            )
            self._log(f"child failed conversation={child_conversation_id} reason={reason!r}", level="WARNING")


def _child_symbol(suffix: str, name: str) -> Any:
    """Version-resolved react symbol (matches base_workflow's resolution)."""
    from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.base_workflow import _react_symbol

    return _react_symbol(suffix, name)

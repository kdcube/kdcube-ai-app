# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""ReAct subagent spawner: charter-scoped child conversations.

``react.delegate`` hands this spawner a charter; the spawner does the only
work that needs the parent's in-memory, not-yet-persisted timeline and then
returns:

1. persist the fork projection as the CHILD conversation's seed timeline
   (durable, as-of delegate time),
2. author the ``subagent.charter`` event onto the child's lane WITH a task
   payload, atomically with the processor wakeup through the gateway's
   enqueue-time backpressure — the promotion IS the kickoff: the child runs
   as a first-class, fair-scheduled turn on the cluster, through the same
   admission, gates, throttling, and per-user capacity as any submitted
   turn. A backpressure rejection fails the delegate with the gateway's
   reason and cleans up the seed — no child state survives a rejection,
3. return the launch ticket; the delegating turn proceeds fully unpinned.

The child-side execution (runtime overrides, accounting identity,
end-of-turn persistence, promotable completion back to the parent lane)
lives in ``react.subagents.child_turn`` and is applied by the workflow when
the promoted charter turn runs.
"""

from __future__ import annotations

from typing import Any, Dict

from kdcube_ai_app.apps.chat.ids import new_turn_id, timestamped_id
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.child_turn import (
    SUBAGENT_ACCOUNTING_AGENT,
    SubagentChildTurnContext,
    subagent_stamp_from_context,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.comm_policy import (
    build_subagent_child_comm,
    normalize_subagent_visibility,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.events import (
    SUBAGENT_CHARTER_EVENT_KIND,
    ParentLaneAddress,
    build_lane_source,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.launch import (
    SubagentLaunchRequest,
    SubagentLaunchTicket,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.schedule import (
    SUBAGENT_TASK_SOURCE,
    SubagentEnqueueRejected,
    atomic_schedule_promotable_subagent_event,
    build_child_task_payload,
    build_subagent_session,
    build_subagent_wake_queue,
    persist_child_seed_timeline,
)

__all__ = [
    "SUBAGENT_ACCOUNTING_AGENT",
    "ReactSubagentSpawner",
    "SubagentEnqueueRejected",
    "build_subagent_child_comm",
]


class ReactSubagentSpawner:
    """Schedules charter-scoped subagent turns for one workflow."""

    def __init__(
        self,
        *,
        workflow: Any,
        build_template: Dict[str, Any],
        queue_manager: Any = None,
    ) -> None:
        self.workflow = workflow
        # The child rebuilds its own tool/skill configuration from the same
        # bundle config when its promoted turn runs; the template is kept for
        # spawner-policy parity checks and diagnostics.
        self.build_template = dict(build_template or {})
        # The atomic admission (injectable; built proc-side from the gateway
        # config when the first spawn needs it).
        self._queue_manager = queue_manager

    # ---- public API (awaited by react.delegate) ----

    async def spawn(self, request: SubagentLaunchRequest) -> SubagentLaunchTicket:
        if int(request.parent_depth or 0) >= 1:
            raise RuntimeError("subagent depth limit: a subagent cannot spawn subagents")
        redis = self._redis()
        if redis is None:
            raise RuntimeError("subagent spawning needs the conversation event lane (redis)")
        parent = request.parent
        charter = request.charter
        child_conversation_id = timestamped_id("sub", suffix_chars=6)
        child_turn_id = new_turn_id()
        comm_context = getattr(self.workflow, "comm_context", None)

        # 1) The fork projection becomes the child conversation's history —
        #    the only delegate-time work that needs the parent's live memory.
        await persist_child_seed_timeline(
            ctx_client=getattr(self.workflow, "ctx_client", None),
            model_service=getattr(self.workflow, "model_service", None),
            parent=parent,
            fork_blocks=list(request.fork_blocks or []),
            child_conversation_id=child_conversation_id,
            child_turn_id=child_turn_id,
            bundle_id=getattr(getattr(self.workflow, "runtime_ctx", None), "bundle_id", None),
            user_type=getattr(getattr(self.workflow, "runtime_ctx", None), "user_type", None),
        )

        # 2) The charter is an authored event on the child's lane (author =
        #    the parent agent) WITH a task payload: the promotion IS the
        #    kickoff. Lane event + wakeup are ONE atomic, admission-gated
        #    write, so the child turn is fair-scheduled like any
        #    reactive-event turn — including enqueue-time backpressure.
        context = SubagentChildTurnContext(
            charter=charter,
            parent=parent,
            depth=int(request.parent_depth or 0) + 1,
            child_conversation_id=child_conversation_id,
            child_turn_id=child_turn_id,
            parent_session_id=str(
                getattr(getattr(comm_context, "routing", None), "session_id", "") or ""
            ),
            parent_user=self._parent_user_dict(comm_context),
            allowed_plugins=list(request.allowed_plugins or []),
            allowed_tool_names_by_alias=request.allowed_tool_names_by_alias,
            visibility=self._visibility(),
        )
        task_payload = build_child_task_payload(
            parent_payload=comm_context,
            charter=charter,
            parent=parent,
            child_conversation_id=child_conversation_id,
            child_turn_id=child_turn_id,
            subagent_context=context.to_dict(),
        )
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
        session = build_subagent_session(
            user=context.parent_user,
            session_id=child_conversation_id,
            source=SUBAGENT_TASK_SOURCE,
        )
        try:
            await atomic_schedule_promotable_subagent_event(
                lane_source=child_lane,
                queue_manager=self._queue(),
                session=session,
                endpoint="react.delegate",
                semantic_type=SUBAGENT_CHARTER_EVENT_KIND,
                text=charter.charter_text(),
                facts={
                    "charter": charter.to_dict(),
                    "parent_conversation_id": parent.conversation_id,
                    "parent_turn_id": parent.turn_id,
                    "subagent": subagent_stamp_from_context(context),
                },
                author=f"agent:conv_{parent.conversation_id}/{parent.turn_id}",
                target_turn_id=child_turn_id,
                task_payload=task_payload,
            )
        except SubagentEnqueueRejected:
            # A rejected delegate leaves no child state behind: the atomic
            # script wrote nothing, and the seed persisted above is removed
            # (best-effort; a leftover is an inert, never-run conversation
            # shell with no charter and no turns).
            await self._cleanup_child_seed(
                parent=parent,
                child_conversation_id=child_conversation_id,
                child_turn_id=child_turn_id,
            )
            raise
        self._log(
            f"child scheduled conversation={child_conversation_id} turn={child_turn_id} "
            f"budget={charter.max_rounds} parent={parent.conversation_id}/{parent.turn_id}"
        )
        return SubagentLaunchTicket(
            child_conversation_id=child_conversation_id,
            child_turn_id=child_turn_id,
            status="scheduled",
        )

    # ---- internals ----

    def _visibility(self) -> str:
        """The child's live-emission visibility, decided at delegate time.

        Read from the agent's resolved subagents defaults
        (``react.agents.<id>.subagents.visibility`` via
        ``react_subagents_config``, stashed on the runtime context by the
        spawner install). Travels with the assignment so the child proc
        applies the same policy the delegating agent's config declared."""
        defaults = getattr(
            getattr(self.workflow, "runtime_ctx", None), "subagent_defaults", None
        )
        raw = (defaults or {}).get("visibility") if isinstance(defaults, dict) else None
        return normalize_subagent_visibility(raw)

    def _queue(self) -> Any:
        if self._queue_manager is None:
            self._queue_manager = build_subagent_wake_queue()
        return self._queue_manager

    async def _cleanup_child_seed(
        self,
        *,
        parent: ParentLaneAddress,
        child_conversation_id: str,
        child_turn_id: str,
    ) -> None:
        ctx_client = getattr(self.workflow, "ctx_client", None)
        delete_turn = getattr(ctx_client, "delete_turn", None)
        if not callable(delete_turn):
            return
        try:
            await delete_turn(
                tenant=parent.tenant,
                project=parent.project,
                user_id=parent.user_id,
                conversation_id=child_conversation_id,
                turn_id=child_turn_id,
                user_type=str(
                    getattr(getattr(self.workflow, "runtime_ctx", None), "user_type", "") or ""
                ),
                bundle_id=getattr(getattr(self.workflow, "runtime_ctx", None), "bundle_id", None),
                where="full",
            )
        except Exception:
            self._log(
                f"seed cleanup after rejected enqueue failed conversation={child_conversation_id}",
                level="WARNING",
            )

    @staticmethod
    def _parent_user_dict(comm_context: Any) -> Dict[str, Any] | None:
        user = getattr(comm_context, "user", None)
        if user is None:
            return None
        try:
            return user.model_dump()
        except Exception:
            return dict(user) if isinstance(user, dict) else None

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

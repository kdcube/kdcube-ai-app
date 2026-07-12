# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The child side of a delegated assignment.

A promoted ``subagent.charter`` turn arrives at the workflow as a normal
task payload; this module is what the workflow uses to (1) recognize it,
(2) apply the child runtime overrides (charter budget as the iteration
budget, depth, parent lane address, model resolution, accounting identity),
and (3) author the terminal ``subagent.converged``/``subagent.failed``
event back onto the parent lane — after the child's end-of-turn
persistence, with a task payload that promotes the parent's continuation
turn when no parent turn is live.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.charter import SubagentCharter
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.events import (
    SUBAGENT_CONVERGED_EVENT_KIND,
    SUBAGENT_FAILED_EVENT_KIND,
    ParentLaneAddress,
    build_lane_source,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.schedule import (
    SUBAGENT_CALL_CONTEXT_KEY,
    SUBAGENT_COMPLETION_TASK_SOURCE,
    build_completion_task_payload,
    build_subagent_session,
    build_subagent_wake_queue,
    publish_completion_with_atomic_wakeup,
)

LOGGER = logging.getLogger("kdcube.react.subagents")

# Component/metadata tag under which subagent spend is identifiable.
SUBAGENT_ACCOUNTING_AGENT = "react.subagent"


@dataclass
class SubagentChildTurnContext:
    """The assignment a promoted charter turn carries in its call context."""

    charter: SubagentCharter
    parent: ParentLaneAddress
    depth: int = 1
    child_conversation_id: str = ""
    child_turn_id: str = ""
    parent_session_id: str = ""
    parent_user: Optional[Dict[str, Any]] = None
    allowed_plugins: List[str] = field(default_factory=list)
    allowed_tool_names_by_alias: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "charter",
            "charter": self.charter.to_dict(),
            "parent": self.parent.to_dict(),
            "depth": int(self.depth or 1),
            "child_conversation_id": self.child_conversation_id,
            "child_turn_id": self.child_turn_id,
            "parent_session_id": self.parent_session_id,
            "parent_user": dict(self.parent_user) if self.parent_user else None,
            "allowed_plugins": list(self.allowed_plugins or []),
            "allowed_tool_names_by_alias": self.allowed_tool_names_by_alias,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> Optional["SubagentChildTurnContext"]:
        if not isinstance(raw, dict):
            return None
        if str(raw.get("kind") or "charter") != "charter":
            return None
        charter = SubagentCharter.from_dict(raw.get("charter"))
        if not charter.goal:
            return None
        parent = ParentLaneAddress.from_dict(raw.get("parent"))
        if not parent.conversation_id:
            return None
        parent_user = raw.get("parent_user")
        allowed = raw.get("allowed_plugins")
        return cls(
            charter=charter,
            parent=parent,
            depth=max(1, int(raw.get("depth") or 1)),
            child_conversation_id=str(raw.get("child_conversation_id") or ""),
            child_turn_id=str(raw.get("child_turn_id") or ""),
            parent_session_id=str(raw.get("parent_session_id") or ""),
            parent_user=dict(parent_user) if isinstance(parent_user, dict) else None,
            allowed_plugins=[str(p) for p in allowed] if isinstance(allowed, list) else [],
            allowed_tool_names_by_alias=(
                raw.get("allowed_tool_names_by_alias")
                if isinstance(raw.get("allowed_tool_names_by_alias"), dict)
                else None
            ),
        )


def charter_turn_context(payload: Any) -> Optional[SubagentChildTurnContext]:
    """Read the subagent assignment from a task payload (model or dict).

    Returns ``None`` for every non-charter turn — including the parent's
    continuation turns promoted from ``subagent.converged``/``failed``,
    which carry no assignment in their call context."""
    if payload is None:
        return None
    call_context = getattr(payload, "bundle_call_context", None)
    if call_context is None and isinstance(payload, dict):
        call_context = payload.get("bundle_call_context")
    if not isinstance(call_context, dict):
        return None
    return SubagentChildTurnContext.from_dict(call_context.get(SUBAGENT_CALL_CONTEXT_KEY))


def resolve_child_model(
    charter: SubagentCharter,
    *,
    bundle_props: Optional[Dict[str, Any]],
    agent_id: Any,
    subagent_defaults: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """The child's strong-decision model: the charter's override when it
    names an admin-allowed model, else the configured subagent default,
    else None (inherit the parent's role models)."""
    from kdcube_ai_app.apps.chat.sdk.runtime.agent_inventory import (
        match_supported_model,
        normalize_model_pick,
        react_supported_models,
    )

    if charter.model:
        supported = react_supported_models(dict(bundle_props or {}), agent_id)
        matched = match_supported_model({"model": charter.model}, supported)
        if matched:
            return matched
        LOGGER.warning(
            "[react.subagents] charter model %r is not in the admin-allowed list; "
            "using the configured subagent default",
            charter.model,
        )
    configured = (subagent_defaults or {}).get("model")
    if isinstance(configured, str) and configured.strip():
        configured = {"model": configured.strip()}
    return normalize_model_pick(configured)


def apply_child_runtime_overrides(
    runtime_ctx: Any,
    context: SubagentChildTurnContext,
    *,
    bundle_props: Optional[Dict[str, Any]] = None,
    subagent_defaults: Optional[Dict[str, Any]] = None,
    redis: Any = None,
) -> None:
    """Shape a workflow runtime context into the child's.

    The charter budget IS the child's iteration budget; reactive credit is
    off so nothing can extend it. Depth and the parent lane address make
    ``react.contribute`` work and keep ``react.delegate`` out of the child's
    catalog."""
    from kdcube_ai_app.apps.chat.sdk.runtime.agent_inventory import USER_MODEL_TARGET_ROLE

    runtime_ctx.subagent_depth = max(1, int(context.depth or 1))
    runtime_ctx.subagent_parent = context.parent.to_dict()
    if redis is not None:
        runtime_ctx.subagent_parent_lane = build_lane_source(
            redis=redis, address=context.parent,
        )
    runtime_ctx.max_iterations = int(context.charter.max_rounds or 1)
    runtime_ctx.reactive_event_iteration_credit_enabled = False
    model_pick = resolve_child_model(
        context.charter,
        bundle_props=bundle_props,
        agent_id=getattr(runtime_ctx, "agent_id", None),
        subagent_defaults=subagent_defaults,
    )
    if model_pick and model_pick.get("model"):
        role_models = dict(getattr(runtime_ctx, "agent_role_models", None) or {})
        role_models[USER_MODEL_TARGET_ROLE] = {
            "provider": model_pick.get("provider") or "anthropic",
            "model": model_pick["model"],
        }
        runtime_ctx.agent_role_models = role_models


def bind_child_turn_accounting(context: SubagentChildTurnContext) -> None:
    """Stamp the task's accounting identity as subagent spend.

    The processor binds a fresh ``AccountingContext`` per task, so the child
    turn's context is isolated by construction; this stamps ``agent`` and the
    ``subagent`` metadata block onto it so child spend is separable in the
    ledgers. ``event_enrichment`` has no public field setter; the context
    object is the sanctioned mutation point for task-lifetime identity."""
    from kdcube_ai_app.infra import accounting as _accounting

    subagent_meta = {
        "parent_conversation_id": context.parent.conversation_id,
        "parent_turn_id": context.parent.turn_id,
        "charter_goal": context.charter.summary_line(),
    }
    _accounting.set_context(agent=SUBAGENT_ACCOUNTING_AGENT)
    ctx = _accounting._get_context()
    enrichment = dict(ctx.event_enrichment or {})
    metadata = dict(enrichment.get("metadata") or {})
    metadata["agent"] = SUBAGENT_ACCOUNTING_AGENT
    metadata["subagent"] = subagent_meta
    enrichment["metadata"] = metadata
    enrichment["agent"] = SUBAGENT_ACCOUNTING_AGENT
    ctx.event_enrichment = enrichment


def _completion_directive(parent_turn_id: str) -> str:
    return (
        "Fold this completion into your context, pull the deliverable refs "
        "you need with react.pull, and respond to the user with the outcome."
    )


async def publish_child_completion(
    *,
    redis: Any,
    runtime_ctx: Any,
    context: SubagentChildTurnContext,
    child_payload: Any = None,
    ok: bool,
    final_answer: str = "",
    reason: str = "",
    queue_manager: Any = None,
) -> Any:
    """Author the terminal event to the parent lane, promotably.

    Called AFTER the child's end-of-turn persistence (completion blocks,
    workspace, timeline), so every ref the completion names is pullable when
    the parent reads it. The task payload describes the parent's
    continuation turn; the promoter starts it when no parent turn is live,
    and acks instead when a live parent turn already folded the event.

    The lane publish is unconditional (a completion is never lost); the
    wakeup goes through the gateway's atomic admission, and a rejected
    wakeup leaves the completion resting in the lane for the parent's next
    turn to fold."""
    parent = context.parent
    child_conversation_id = (
        str(getattr(runtime_ctx, "conversation_id", "") or "")
        or context.child_conversation_id
    )
    child_turn_id = (
        str(getattr(runtime_ctx, "turn_id", "") or "") or context.child_turn_id
    )
    parent_lane = getattr(runtime_ctx, "subagent_parent_lane", None)
    if parent_lane is None:
        parent_lane = build_lane_source(redis=redis, address=parent)

    final_answer = str(final_answer or "").strip()
    ok = bool(ok and final_answer)
    directive = _completion_directive(parent.turn_id)
    if ok:
        semantic_type = SUBAGENT_CONVERGED_EVENT_KIND
        text = "\n".join([
            "[SUBAGENT CONVERGED]",
            f"Subagent conv_{child_conversation_id} completed its charter.",
            "",
            final_answer,
            "",
            directive,
        ])
        facts = {
            "child_conversation_id": child_conversation_id,
            "child_conversation_ref": f"conv_{child_conversation_id}",
            "final_answer": final_answer,
            "charter_goal": context.charter.summary_line(),
        }
    else:
        semantic_type = SUBAGENT_FAILED_EVENT_KIND
        reason = str(reason or "").strip() or "no final answer within budget"
        text = "\n".join([
            "[SUBAGENT FAILED]",
            f"Subagent conv_{child_conversation_id} stopped without converging: {reason}",
            "",
            directive,
        ])
        facts = {
            "child_conversation_id": child_conversation_id,
            "child_conversation_ref": f"conv_{child_conversation_id}",
            "reason": reason,
            "charter_goal": context.charter.summary_line(),
        }

    task_payload = build_completion_task_payload(
        child_payload=child_payload,
        semantic_type=semantic_type,
        text=text,
        facts=facts,
        parent=parent,
        parent_session_id=context.parent_session_id,
        parent_user=context.parent_user,
    )
    if queue_manager is None:
        queue_manager = build_subagent_wake_queue()
    session = build_subagent_session(
        user=context.parent_user,
        session_id=context.parent_session_id or parent.conversation_id,
        source=SUBAGENT_COMPLETION_TASK_SOURCE,
    )
    event, wake_admitted, wake_reason = await publish_completion_with_atomic_wakeup(
        lane_source=parent_lane,
        queue_manager=queue_manager,
        session=session,
        endpoint=SUBAGENT_COMPLETION_TASK_SOURCE,
        semantic_type=semantic_type,
        text=text,
        facts=facts,
        author=f"agent:conv_{child_conversation_id}/{child_turn_id}",
        target_turn_id=parent.turn_id or None,
        task_payload=task_payload,
    )
    if not wake_admitted:
        LOGGER.warning(
            "[react.subagents] completion wakeup rejected (%s); the %s event "
            "rests in conversation=%s and folds on the parent's next turn",
            wake_reason,
            semantic_type,
            parent.conversation_id,
        )
    return event

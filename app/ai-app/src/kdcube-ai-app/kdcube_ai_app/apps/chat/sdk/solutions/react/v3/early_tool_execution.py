# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, Optional


EARLY_TOOL_EXECUTION_LEDGER_KEY = "early_tool_executions"
_CONSUMED_STATUSES = frozenset({"consumed", "failed"})
_ACTIVE_STATUSES = frozenset({"running", *_CONSUMED_STATUSES})

_LOG = logging.getLogger(__name__)

DecisionValidator = Callable[[dict[str, Any]], Optional[str]]
ProtocolValidator = Callable[[Any], dict[str, Any] | Awaitable[dict[str, Any]]]
ActionAccepted = Callable[[int, str, str], bool]
ExecutionPolicyCheck = Callable[[dict[str, Any]], bool]
ToolExecutor = Callable[[dict[str, Any], str], Awaitable[Optional[dict[str, Any]]]]
ExecutionCallback = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class EarlyToolExecutionIdentity:
    action_key: str
    tool_call_id: str
    semantic_fingerprint: str
    tool_id: str
    turn_id: str
    iteration: int
    action_index: int


def _tool_id(decision: Mapping[str, Any]) -> str:
    tool_call = decision.get("tool_call") if isinstance(decision.get("tool_call"), Mapping) else {}
    return str(tool_call.get("tool_id") or "").strip()


def _canonical_tool_payload(decision: Mapping[str, Any]) -> str:
    tool_call = decision.get("tool_call") if isinstance(decision.get("tool_call"), Mapping) else {}
    payload = {
        "tool_id": str(tool_call.get("tool_id") or "").strip(),
        "params": tool_call.get("params") if isinstance(tool_call.get("params"), Mapping) else {},
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def early_tool_execution_identity(
    *,
    turn_id: str,
    iteration: int,
    action_index: int,
    decision: Mapping[str, Any],
) -> EarlyToolExecutionIdentity:
    safe_turn_id = str(turn_id or "").strip()
    safe_iteration = max(0, int(iteration or 0))
    safe_action_index = max(0, int(action_index or 0))
    tool_id = _tool_id(decision)
    slot_text = f"{safe_turn_id}\x1f{safe_iteration}\x1f{safe_action_index}"
    slot_digest = hashlib.sha256(slot_text.encode("utf-8")).hexdigest()
    semantic_digest = hashlib.sha256(_canonical_tool_payload(decision).encode("utf-8")).hexdigest()
    return EarlyToolExecutionIdentity(
        action_key=f"early-tool:{slot_digest}",
        tool_call_id=f"tc_{slot_digest[:12]}",
        semantic_fingerprint=semantic_digest,
        tool_id=tool_id,
        turn_id=safe_turn_id,
        iteration=safe_iteration,
        action_index=safe_action_index,
    )


def _ledger(
    state: Mapping[str, Any] | MutableMapping[str, Any],
    *,
    create: bool,
) -> dict[str, dict[str, Any]]:
    existing = state.get(EARLY_TOOL_EXECUTION_LEDGER_KEY)
    if isinstance(existing, dict):
        return existing
    if not create or not isinstance(state, MutableMapping):
        return {}
    created: dict[str, dict[str, Any]] = {}
    state[EARLY_TOOL_EXECUTION_LEDGER_KEY] = created
    return created


def early_tool_execution_record(
    *,
    state: Mapping[str, Any],
    identity: EarlyToolExecutionIdentity,
    include_running: bool = False,
) -> Optional[dict[str, Any]]:
    accepted_statuses = _ACTIVE_STATUSES if include_running else _CONSUMED_STATUSES
    ledger = _ledger(state, create=False)
    record = ledger.get(identity.action_key)
    if isinstance(record, dict) and str(record.get("status") or "") in accepted_statuses:
        return record

    # A provider retry can re-order otherwise identical actions. The semantic
    # fallback keeps an irreversible call at-most-once within the same logical
    # round while distinct tool inputs retain distinct identities.
    for candidate in ledger.values():
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("status") or "") not in accepted_statuses:
            continue
        if str(candidate.get("turn_id") or "") != identity.turn_id:
            continue
        if int(candidate.get("iteration") or 0) != identity.iteration:
            continue
        if str(candidate.get("tool_id") or "") != identity.tool_id:
            continue
        if str(candidate.get("semantic_fingerprint") or "") == identity.semantic_fingerprint:
            return candidate
    return None


def consumed_early_tool_record(
    *,
    state: Mapping[str, Any],
    identity: EarlyToolExecutionIdentity,
) -> Optional[dict[str, Any]]:
    return early_tool_execution_record(
        state=state,
        identity=identity,
        include_running=False,
    )


def resolved_early_tool_call_id(
    *,
    state: Mapping[str, Any],
    identity: EarlyToolExecutionIdentity,
) -> str:
    record = consumed_early_tool_record(state=state, identity=identity)
    if isinstance(record, dict):
        existing = str(record.get("tool_call_id") or "").strip()
        if existing:
            return existing
    return identity.tool_call_id


class EarlyToolExecutionListener:
    """Executes one opted-in tool when its complete action block is valid."""

    def __init__(
        self,
        *,
        state: MutableMapping[str, Any],
        turn_id: str,
        iteration: int,
        action_index: int,
        validate_decision: DecisionValidator,
        validate_protocol: ProtocolValidator,
        action_accepted: ActionAccepted,
        execution_policy_allows: ExecutionPolicyCheck,
        execute_tool: ToolExecutor,
        execution_tasks: MutableMapping[str, asyncio.Task[Any]],
        on_consumed: Optional[ExecutionCallback] = None,
    ) -> None:
        self.state = state
        self.turn_id = str(turn_id or "").strip()
        self.iteration = max(0, int(iteration or 0))
        self.action_index = max(0, int(action_index or 0))
        self.validate_decision = validate_decision
        self.validate_protocol = validate_protocol
        self.action_accepted = action_accepted
        self.execution_policy_allows = execution_policy_allows
        self.execute_tool = execute_tool
        self.execution_tasks = execution_tasks
        self.on_consumed = on_consumed

    async def on_action_completed(
        self,
        *,
        decision: Optional[dict[str, Any]],
        parse_error: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        del parse_error
        if not isinstance(decision, dict):
            return None
        action = str(decision.get("action") or "").strip()
        tool_call = decision.get("tool_call") if isinstance(decision.get("tool_call"), dict) else {}
        tool_id = str(tool_call.get("tool_id") or "").strip()
        if action != "call_tool" or not tool_id:
            return None

        identity = early_tool_execution_identity(
            turn_id=self.turn_id,
            iteration=self.iteration,
            action_index=self.action_index,
            decision=decision,
        )
        existing = early_tool_execution_record(
            state=self.state,
            identity=identity,
            include_running=True,
        )
        if existing is not None:
            return existing

        if not self.action_accepted(self.action_index, action, tool_id):
            return None
        if not self.execution_policy_allows(decision):
            return None
        if self.validate_decision(decision):
            return None
        maybe_verdict = self.validate_protocol(tool_call)
        verdict = await maybe_verdict if inspect.isawaitable(maybe_verdict) else maybe_verdict
        if not bool(verdict.get("ok")):
            return None

        ledger = _ledger(self.state, create=True)

        record: dict[str, Any] = {
            "action_key": identity.action_key,
            "tool_call_id": identity.tool_call_id,
            "tool_id": identity.tool_id,
            "turn_id": identity.turn_id,
            "iteration": identity.iteration,
            "action_index": identity.action_index,
            "semantic_fingerprint": identity.semantic_fingerprint,
            "status": "running",
            "started_at": time.time(),
        }
        ledger[identity.action_key] = record

        async def _run() -> None:
            try:
                result = await self.execute_tool(decision, identity.tool_call_id)
                record["status"] = "consumed"
                record["finished_at"] = time.time()
                if isinstance(result, dict):
                    record["result"] = dict(result)
                    self.state["last_tool_result"] = dict(result)
            except asyncio.CancelledError:
                record["status"] = "failed"
                record["finished_at"] = time.time()
                record["error"] = {
                    "type": "CancelledError",
                    "message": "Early tool execution was cancelled.",
                }
                raise
            except Exception as exc:
                record["status"] = "failed"
                record["finished_at"] = time.time()
                record["error"] = {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                }
                self.state["last_tool_result"] = {
                    "status": "error",
                    "code": "early_tool_execution_failed",
                    "message": str(exc),
                }
                _LOG.exception(
                    "early tool execution failed: tool=%s turn=%s iteration=%s index=%s call=%s",
                    identity.tool_id,
                    identity.turn_id,
                    identity.iteration,
                    identity.action_index,
                    identity.tool_call_id,
                )
            finally:
                if self.on_consumed is not None:
                    try:
                        await self.on_consumed(record)
                    except Exception:
                        _LOG.exception(
                            "early tool completion callback failed: tool=%s call=%s",
                            identity.tool_id,
                            identity.tool_call_id,
                        )

        task = asyncio.create_task(_run(), name=f"react.tool.early.{identity.tool_call_id}")
        self.execution_tasks[identity.action_key] = task
        # Give the detached call an immediate scheduling opportunity before
        # the stream parser advances to a later action instance.
        await asyncio.sleep(0)
        return record


async def drain_early_tool_executions(
    execution_tasks: MutableMapping[str, asyncio.Task[Any]],
) -> None:
    tasks = [task for task in execution_tasks.values() if task is not None]
    if not tasks:
        return
    await asyncio.gather(*tasks, return_exceptions=True)
    execution_tasks.clear()


__all__ = [
    "EARLY_TOOL_EXECUTION_LEDGER_KEY",
    "EarlyToolExecutionIdentity",
    "EarlyToolExecutionListener",
    "consumed_early_tool_record",
    "drain_early_tool_executions",
    "early_tool_execution_record",
    "early_tool_execution_identity",
    "resolved_early_tool_call_id",
]

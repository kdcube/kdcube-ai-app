# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from kdcube_ai_app.apps.chat.sdk.runtime.tool_traits import (
    STRATEGY_TRAIT,
    UNKNOWN_STRATEGY,
    strategies_compatible,
    strategy_values,
)
from kdcube_ai_app.apps.chat.sdk.streaming.stream_policy import StreamPolicyViolation


EmitDelta = Callable[..., Awaitable[None]]
TraitsResolver = Callable[..., Mapping[str, Any]]
DEFAULT_MAX_ACTIONS_PER_ROUND = 2
logger = logging.getLogger(__name__)


class ActionStreamGate:
    """Buffered output gate for one observed action lane."""

    def __init__(self, *, emit_delta: EmitDelta, action_index: int, lane: str = "action") -> None:
        self._emit_delta = emit_delta
        self.action_index = int(action_index or 0)
        self.lane = str(lane or "action")
        self._status = "pending"
        self._buffer: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    @property
    def status(self) -> str:
        return self._status

    async def emit_delta(self, **kwargs: Any) -> None:
        async with self._lock:
            if self._status == "denied":
                return
            if self._status != "allowed":
                if not self._buffer:
                    logger.info(
                        "[react.action_overseer.gate] buffering lane=%s index=%s marker=%s artifact=%s",
                        self.lane,
                        self.action_index,
                        kwargs.get("marker"),
                        kwargs.get("artifact_name"),
                    )
                self._buffer.append(dict(kwargs))
                return
        await self._emit_delta(**kwargs)

    async def allow(self) -> None:
        async with self._lock:
            if self._status != "pending":
                return
            self._status = "allowed"
            buffered = list(self._buffer)
            self._buffer.clear()
        logger.info(
            "[react.action_overseer.gate] allowed lane=%s index=%s flushed=%s",
            self.lane,
            self.action_index,
            len(buffered),
        )
        for item in buffered:
            await self._emit_delta(**item)

    async def deny(self) -> None:
        async with self._lock:
            dropped = len(self._buffer)
            self._status = "denied"
            self._buffer.clear()
        logger.info(
            "[react.action_overseer.gate] denied lane=%s index=%s dropped=%s",
            self.lane,
            self.action_index,
            dropped,
        )


@dataclass(frozen=True)
class ObservedAction:
    index: int
    action: str
    tool_id: str
    traits: dict[str, Any]
    tool_params: dict[str, Any] | None = None

    @property
    def strategies(self) -> set[str]:
        return strategy_values(self.traits)

    @property
    def is_tool(self) -> bool:
        return self.action == "call_tool"

    @property
    def is_final(self) -> bool:
        return self.action in {"complete", "exit"}

    @property
    def is_neutral_tool(self) -> bool:
        strategies = self.strategies
        return bool(strategies) and UNKNOWN_STRATEGY not in strategies and strategies == {"neutral"}

    @property
    def answer_lane_allowed(self) -> bool:
        if self.is_final:
            return True
        return False


@dataclass(frozen=True)
class RejectedAction:
    index: int
    action: str
    tool_id: str
    code: str
    extra: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "action": self.action,
            **({"tool_id": self.tool_id} if self.tool_id else {}),
            "code": self.code,
            **({"extra": dict(self.extra)} if self.extra else {}),
        }


class RoundActionOverseer:
    """External per-round compatibility policy for streamed action instances."""

    def __init__(self, *, resolve_traits: TraitsResolver, max_actions: int = DEFAULT_MAX_ACTIONS_PER_ROUND) -> None:
        self._resolve_traits = resolve_traits
        self._max_actions = max(1, int(max_actions or DEFAULT_MAX_ACTIONS_PER_ROUND))
        self._observed: list[ObservedAction] = []
        self._rejected: list[RejectedAction] = []
        self._lock = asyncio.Lock()

    def gate_for(self, *, action_index: int, emit_delta: EmitDelta, lane: str = "action") -> ActionStreamGate:
        return ActionStreamGate(emit_delta=emit_delta, action_index=action_index, lane=lane)

    async def observe_action_signal(
        self,
        *,
        action_index: int,
        action: str,
        tool_id: str,
        action_gate: ActionStreamGate,
        answer_gate: Optional[ActionStreamGate] = None,
        tool_params: Optional[Mapping[str, Any]] = None,
    ) -> ObservedAction:
        action_text = str(action or "").strip()
        tool_id_text = str(tool_id or "").strip()
        params_dict = dict(tool_params or {}) if isinstance(tool_params, Mapping) else None
        traits = self._traits_for(action_text, tool_id_text, params_dict)
        observed = ObservedAction(
            index=int(action_index or 0),
            action=action_text,
            tool_id=tool_id_text,
            traits=traits,
            tool_params=params_dict,
        )
        logger.info(
            "[react.action_overseer] observed index=%s action=%s tool_id=%s strategies=%s",
            observed.index,
            observed.action,
            observed.tool_id or "-",
            sorted(observed.strategies or {UNKNOWN_STRATEGY}),
        )

        async with self._lock:
            previous_same_index = next((item for item in self._observed if item.index == observed.index), None)
            if previous_same_index is not None:
                action_allowed = True
                answer_allowed = self._answer_gate_allowed(previous_same_index)
                violation: tuple[str, dict[str, Any]] | None = None
            else:
                violation = self._violation_for(observed)
                action_allowed = violation is None
                answer_allowed = action_allowed and self._answer_gate_allowed(observed)
                if action_allowed:
                    self._observed.append(observed)

        if action_allowed:
            logger.info(
                "[react.action_overseer] accepted index=%s action=%s tool_id=%s answer_lane=%s previous=%s",
                observed.index,
                observed.action,
                observed.tool_id or "-",
                answer_allowed,
                previous_same_index is not None,
            )
            await action_gate.allow()
            if answer_gate is not None:
                if answer_allowed:
                    await answer_gate.allow()
                else:
                    await answer_gate.deny()
            return previous_same_index or observed

        await action_gate.deny()
        if answer_gate is not None:
            await answer_gate.deny()
        assert violation is not None
        code, extra = violation
        logger.info(
            "[react.action_overseer] rejected index=%s action=%s tool_id=%s code=%s extra=%s",
            observed.index,
            observed.action,
            observed.tool_id or "-",
            code,
            dict(extra or {}),
        )
        async with self._lock:
            previous_rejected = next((item for item in self._rejected if item.index == observed.index), None)
            if previous_rejected is None:
                self._rejected.append(RejectedAction(
                    index=observed.index,
                    action=observed.action,
                    tool_id=observed.tool_id,
                    code=code,
                    extra=dict(extra or {}),
                ))
        raise StreamPolicyViolation(code=code, extra=extra)

    def accepted_actions(self) -> list[ObservedAction]:
        return list(self._observed)

    def rejected_actions(self) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self._rejected]

    def _traits_for(self, action: str, tool_id: str, tool_params: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
        if action in {"complete", "exit"}:
            return {STRATEGY_TRAIT: ["exploitation"]}
        if action == "call_tool" and tool_id:
            try:
                return dict(self._resolve_traits(tool_id, tool_params) or {})
            except TypeError:
                return dict(self._resolve_traits(tool_id) or {})
        return {}

    def _violation_for(self, observed: ObservedAction) -> tuple[str, dict[str, Any]] | None:
        if not observed.is_tool and not observed.is_final:
            return (
                "multi_action_bundle_mixed_actions",
                {"index": observed.index, "action": observed.action},
            )

        if not self._observed:
            return None

        if len(self._observed) >= self._max_actions:
            return (
                "multi_action_bundle_too_many_actions",
                {
                    "index": observed.index,
                    "action": observed.action,
                    "tool_id": observed.tool_id,
                    "max_actions": self._max_actions,
                },
            )

        if observed.is_final:
            non_neutral = next((item for item in self._observed if not item.is_final and not item.is_neutral_tool), None)
            if non_neutral is not None:
                return (
                    "multi_action_bundle_final_answer_after_non_neutral",
                    {
                        "index": observed.index,
                        "action": observed.action,
                        "first_index": non_neutral.index,
                        "first_tool_id": non_neutral.tool_id,
                        "first_strategy": sorted(non_neutral.strategies),
                    },
                )
            return None

        current_strategies = observed.strategies
        if not current_strategies:
            return (
                "multi_action_bundle_unsafe_tool",
                {
                    "index": observed.index,
                    "tool_id": observed.tool_id,
                    "strategy": sorted(current_strategies or {UNKNOWN_STRATEGY}),
                },
            )

        for previous in self._observed:
            if previous.is_final and not observed.is_neutral_tool:
                return (
                    "multi_action_bundle_non_neutral_after_final_answer",
                    {
                        "index": observed.index,
                        "tool_id": observed.tool_id,
                        "strategy": sorted(current_strategies),
                        "first_index": previous.index,
                        "first_action": previous.action,
                    },
                )
            if previous.is_final:
                continue
            if not strategies_compatible(previous.traits, observed.traits):
                return (
                    "multi_action_bundle_strategy_incompatible",
                    {
                        "index": observed.index,
                        "tool_id": observed.tool_id,
                        "strategy": sorted(current_strategies),
                        "first_index": previous.index,
                        "first_tool_id": previous.tool_id,
                        "first_strategy": sorted(previous.strategies),
                    },
                )
        return None

    def _answer_gate_allowed(self, observed: ObservedAction) -> bool:
        if not observed.answer_lane_allowed:
            return False
        if observed.is_final:
            return all(item.is_final or item.is_neutral_tool for item in self._observed)
        return True


__all__ = [
    "ActionStreamGate",
    "DEFAULT_MAX_ACTIONS_PER_ROUND",
    "ObservedAction",
    "RejectedAction",
    "RoundActionOverseer",
]

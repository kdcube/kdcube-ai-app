# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The subagent charter: the written contract a parent hands a child.

A charter carries the goal, the declared deliverables, the round budget, and
what the child sends back. It travels as data end to end: react.delegate
params -> launch request -> the authored charter event on the child lane ->
the child's contribute/converge report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SUBAGENT_MAX_ROUNDS = 8
MAX_SUBAGENT_MAX_ROUNDS = 30


@dataclass
class SubagentCharter:
    goal: str
    deliverables: List[str] = field(default_factory=list)
    max_rounds: int = DEFAULT_SUBAGENT_MAX_ROUNDS
    contribute: str = ""
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "deliverables": list(self.deliverables or []),
            "max_rounds": int(self.max_rounds or DEFAULT_SUBAGENT_MAX_ROUNDS),
            "contribute": self.contribute,
            "model": self.model,
        }

    def summary_line(self, *, max_chars: int = 220) -> str:
        goal = " ".join(str(self.goal or "").split())
        if len(goal) > max_chars:
            goal = goal[: max_chars - 1] + "…"
        return goal

    def charter_text(self) -> str:
        """The model-facing charter statement (the child's task)."""
        lines = [
            "[SUBAGENT CHARTER]",
            "You are a subagent: a full ReAct agent working a scoped assignment "
            "inside your own conversation. The timeline above this charter is a "
            "fork: a copy of what the delegating agent saw when it opened this "
            "assignment (its in-progress turn plus the conversation's working "
            "summaries). It is context, not your task. Your task is this charter.",
            "",
            f"GOAL: {self.goal}",
        ]
        if self.deliverables:
            lines.append("DELIVERABLES:")
            lines.extend(f"- {item}" for item in self.deliverables)
        if self.contribute:
            lines.append(f"CONTRIBUTE BACK: {self.contribute}")
        lines.extend([
            f"BUDGET: at most {int(self.max_rounds or DEFAULT_SUBAGENT_MAX_ROUNDS)} rounds.",
            "Report results with react.contribute(refs=[...], report=...). Refs you "
            "contribute must be logical paths from THIS conversation; they are "
            "delivered to the delegating agent in a cross-conversation form it can "
            "pull. Your final answer is delivered back automatically when you "
            "finish; contribute earlier when a partial result is already useful.",
        ])
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, raw: Any) -> "SubagentCharter":
        raw = raw if isinstance(raw, dict) else {}
        deliverables = raw.get("deliverables")
        if isinstance(deliverables, str):
            deliverables = [deliverables]
        return cls(
            goal=str(raw.get("goal") or "").strip(),
            deliverables=[str(d).strip() for d in (deliverables or []) if str(d or "").strip()],
            max_rounds=_clamp_rounds(raw.get("max_rounds") or raw.get("budget")),
            contribute=str(raw.get("contribute") or "").strip(),
            model=str(raw.get("model") or "").strip(),
        )


def _clamp_rounds(value: Any) -> int:
    try:
        rounds = int(value)
    except Exception:
        rounds = DEFAULT_SUBAGENT_MAX_ROUNDS
    if rounds <= 0:
        rounds = DEFAULT_SUBAGENT_MAX_ROUNDS
    return min(rounds, MAX_SUBAGENT_MAX_ROUNDS)


def parse_charter(params: Any) -> Tuple[Optional[SubagentCharter], str]:
    """Parse react.delegate params into a charter.

    Returns ``(charter, "")`` or ``(None, error_code)``.
    """
    params = params if isinstance(params, dict) else {}
    raw = params.get("charter")
    if not isinstance(raw, dict):
        # Tolerate flat params: {goal, deliverables, max_rounds, contribute}.
        raw = params
    charter = SubagentCharter.from_dict(raw)
    if isinstance(params.get("model"), str) and params.get("model").strip() and not charter.model:
        charter.model = params["model"].strip()
    if not charter.goal:
        return None, "missing_goal"
    return charter, ""

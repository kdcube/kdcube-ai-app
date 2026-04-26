# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReactRuntimeState:
    session_id: str
    turn_id: str

    adapters: List[Dict[str, Any]]

    workdir: pathlib.Path
    outdir: pathlib.Path
    plan_steps: List[str]
    plan_status: Dict[str, str] = field(default_factory=dict)

    # Loop control
    iteration: int = 0
    max_iterations: int = 15
    base_max_iterations: int = 15
    reactive_iteration_credit: int = 0
    reactive_iteration_credit_cap: int = 0
    decision_retries: int = 0
    max_decision_retries: int = 2

    exit_reason: Optional[str] = None
    final_answer: Optional[str] = None
    suggested_followups: Optional[List[str]] = None

    last_decision: Optional[Dict[str, Any]] = None
    last_tool_result: Optional[Any] = None

    pending_tool_skills: Optional[List[str]] = None

    session_log: List[Dict[str, Any]] = field(default_factory=list)
    round_timings: List[Dict[str, Any]] = field(default_factory=list)

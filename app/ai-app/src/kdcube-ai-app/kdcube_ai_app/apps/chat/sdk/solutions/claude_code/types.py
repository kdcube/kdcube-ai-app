# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence


ClaudeCodeTurnKind = Literal["regular", "followup", "steer"]


@dataclass(frozen=True)
class ClaudeCodeAgentConfig:
    agent_name: str
    workspace_path: Path
    model: str | None = None
    allowed_tools: Sequence[str] = field(default_factory=tuple)
    additional_directories: Sequence[Path] = field(default_factory=tuple)
    extra_args: Sequence[str] = field(default_factory=tuple)
    env: Mapping[str, str] = field(default_factory=dict)
    step_name: str = "claude_code.agent"
    delta_marker: str = "answer"
    emit_stderr_steps: bool = True
    command: str = "claude"
    permission_mode: str | None = "acceptEdits"

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace_path", Path(self.workspace_path))
        object.__setattr__(
            self,
            "allowed_tools",
            tuple(tool.strip() for tool in self.allowed_tools if str(tool).strip()),
        )
        object.__setattr__(
            self,
            "additional_directories",
            tuple(Path(path) for path in self.additional_directories if str(path).strip()),
        )
        object.__setattr__(
            self,
            "extra_args",
            tuple(str(arg) for arg in self.extra_args if str(arg).strip()),
        )
        object.__setattr__(
            self,
            "env",
            {str(key): str(value) for key, value in dict(self.env or {}).items() if str(value).strip()},
        )
        object.__setattr__(self, "model", str(self.model or "").strip() or None)
        if self.permission_mode is not None:
            object.__setattr__(self, "permission_mode", str(self.permission_mode).strip() or None)


@dataclass(frozen=True)
class ClaudeCodeBinding:
    user_id: str
    conversation_id: str
    session_id: str
    claude_session_id: str


@dataclass
class ClaudeCodeRunResult:
    status: Literal["completed", "failed"]
    session_id: str
    final_text: str
    delta_count: int
    exit_code: int | None
    stderr_lines: list[str]
    raw_output_lines: list[str]
    turn_kind: ClaudeCodeTurnKind
    agent_name: str
    provider: str | None = None
    requested_model: str | None = None
    model: str | None = None
    usage: dict[str, Any] | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    api_duration_ms: int | None = None
    raw_result_event: dict[str, Any] | None = None
    resolved_from_stream: bool = False
    error_message: str | None = None

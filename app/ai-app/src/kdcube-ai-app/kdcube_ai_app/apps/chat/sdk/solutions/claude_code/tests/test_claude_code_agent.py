# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from kdcube_ai_app.apps.chat.emitters import ChatCommunicator
from kdcube_ai_app.apps.chat.sdk.protocol import (
    ChatTaskActor,
    ChatTaskPayload,
    ChatTaskRequest,
    ChatTaskRouting,
    ChatTaskUser,
)
from kdcube_ai_app.apps.chat.sdk.runtime.comm_ctx import bind_current_request_context
from kdcube_ai_app.apps.chat.sdk.solutions.claude_code import ClaudeCodeAgent
from kdcube_ai_app.apps.chat.sdk.solutions.claude_code.types import ClaudeCodeAgentConfig, ClaudeCodeBinding
from kdcube_ai_app.infra.accounting import AccountingSystem, clear_context


class _RecordingEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, *, event: str, data: dict, **kwargs) -> None:
        del kwargs
        self.events.append((event, data))


class _FakeProcess:
    def __init__(self, *, stdout_lines: list[str], stderr_lines: list[str], returncode: int):
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.returncode = None
        self._stdout_lines = list(stdout_lines)
        self._stderr_lines = list(stderr_lines)
        self._planned_returncode = returncode
        self._task = asyncio.create_task(self._feed())

    async def _feed(self) -> None:
        for line in self._stdout_lines:
            self.stdout.feed_data(line.encode("utf-8"))
            await asyncio.sleep(0)
        self.stdout.feed_eof()
        for line in self._stderr_lines:
            self.stderr.feed_data(line.encode("utf-8"))
            await asyncio.sleep(0)
        self.stderr.feed_eof()
        self.returncode = self._planned_returncode

    async def wait(self) -> int:
        await self._task
        return self._planned_returncode


class _RecordingAccountingBackend:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str]] = []

    async def write_text_a(self, path: str, content: str) -> None:
        self.writes.append((path, content))


def _ctx() -> ChatTaskPayload:
    return ChatTaskPayload(
        request=ChatTaskRequest(request_id="req-claude-code"),
        routing=ChatTaskRouting(
            session_id="sid-claude",
            conversation_id="conv-claude",
            turn_id="turn-claude",
            bundle_id="bundle.claude",
        ),
        actor=ChatTaskActor(
            tenant_id="demo-tenant",
            project_id="demo-project",
        ),
        user=ChatTaskUser(
            user_type="privileged",
            user_id="admin-user-1",
            fingerprint="fingerprint-1",
            username="admin",
            roles=["kdcube:role:super-admin"],
            permissions=["kdcube:*:chat:*;read;write;delete"],
            timezone="UTC",
        ),
    )


def _make_comm() -> tuple[ChatCommunicator, _RecordingEmitter]:
    emitter = _RecordingEmitter()
    comm = ChatCommunicator(
        emitter=emitter,
        tenant="demo-tenant",
        project="demo-project",
        user_id="admin-user-1",
        user_type="privileged",
        service={
            "request_id": "req-claude-code",
            "tenant": "demo-tenant",
            "project": "demo-project",
            "user": "admin-user-1",
        },
        conversation={
            "session_id": "sid-claude",
            "conversation_id": "conv-claude",
            "turn_id": "turn-claude",
        },
    )
    return comm, emitter


def _config(workspace_path: Path) -> ClaudeCodeAgentConfig:
    return ClaudeCodeAgentConfig(
        agent_name="kb-writer",
        workspace_path=workspace_path,
        allowed_tools=("Read", "Grep", "WebSearch"),
        additional_directories=(workspace_path / "repos" / "output",),
        extra_args=("--append-system-prompt", "Stay concise."),
        env={"EXTRA_ENV": "yes"},
    )


@pytest.mark.asyncio
async def test_from_current_context_derives_deterministic_binding(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    comm, _ = _make_comm()
    ctx = _ctx()

    with bind_current_request_context(ctx, comm=comm):
        first = ClaudeCodeAgent.from_current_context(
            agent_name="kb-writer",
            workspace_path=workspace,
        )
        second = ClaudeCodeAgent.from_current_context(
            agent_name="kb-writer",
            workspace_path=workspace,
        )

    assert first.binding == second.binding
    assert first.binding.user_id == "admin-user-1"
    assert first.binding.conversation_id == "conv-claude"
    assert first.binding.session_id == "sid-claude"
    assert first.binding.claude_session_id


def test_build_args_includes_session_allowed_tools_and_agent(tmp_path: Path):
    workspace = tmp_path / "workspace"
    (workspace / "repos" / "output").mkdir(parents=True)
    binding = ClaudeCodeBinding(
        user_id="admin-user-1",
        conversation_id="conv-claude",
        session_id="sid-claude",
        claude_session_id="claude-session-1",
    )
    agent = ClaudeCodeAgent(config=_config(workspace), binding=binding, comm=None)

    args = agent.build_args("Explain the repo")
    resume_args = agent.build_args("Explain the repo", resume_existing=True)

    assert "--allowedTools" in args
    assert "Read,Grep,WebSearch" in args
    assert "--permission-mode" in args
    assert "acceptEdits" in args
    assert "--add-dir" in args
    assert str(workspace / "repos" / "output") in args
    assert "--session-id" in args
    assert "claude-session-1" in args
    assert "--resume" in resume_args
    assert "claude-session-1" in resume_args
    assert "--session-id" not in resume_args
    assert "--agent" in args
    assert "kb-writer" in args
    assert args[-1] == "Explain the repo"


def test_build_args_includes_selected_model(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    binding = ClaudeCodeBinding(
        user_id="admin-user-1",
        conversation_id="conv-claude",
        session_id="sid-claude",
        claude_session_id="claude-session-1",
    )
    config = ClaudeCodeAgentConfig(
        agent_name="kb-writer",
        workspace_path=workspace,
        model="claude-opus-4-6",
    )
    agent = ClaudeCodeAgent(config=config, binding=binding, comm=None)

    args = agent.build_args("Explain the repo")

    assert "--model" in args
    assert "claude-opus-4-6" in args


@pytest.mark.asyncio
async def test_run_turn_streams_incremental_deltas(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    comm, emitter = _make_comm()
    ctx = _ctx()

    outputs = [
        json.dumps({"message": {"content": [{"type": "text", "text": "Hello"}]}}) + "\n",
        json.dumps({"message": {"content": [{"type": "text", "text": "Hello world"}]}}) + "\n",
    ]

    async def _fake_create_subprocess_exec(*args, **kwargs):
        del args, kwargs
        return _FakeProcess(stdout_lines=outputs, stderr_lines=[], returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    with bind_current_request_context(ctx, comm=comm):
        agent = ClaudeCodeAgent.from_current_context(
            agent_name="kb-writer",
            workspace_path=workspace,
            allowed_tools=("Read", "WebSearch"),
        )
        result = await agent.run_turn("Summarize repo")

    deltas = [
        envelope["delta"]["text"]
        for _, envelope in emitter.events
        if envelope.get("type") == "chat.delta"
    ]
    steps = [
        envelope
        for _, envelope in emitter.events
        if envelope.get("type") == "chat.step"
    ]

    assert result.status == "completed"
    assert result.final_text == "Hello world"
    assert result.delta_count == 2
    assert deltas == ["Hello", " world"]
    assert steps[0]["event"]["status"] == "started"
    assert steps[0]["data"]["turn_kind"] == "regular"
    assert steps[-1]["event"]["status"] == "completed"


@pytest.mark.asyncio
async def test_run_turn_preserves_multiple_distinct_claude_messages(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    comm, emitter = _make_comm()
    ctx = _ctx()

    outputs = [
        json.dumps({"message": {"content": [{"type": "text", "text": "First message"}]}}) + "\n",
        json.dumps({"message": {"content": [{"type": "text", "text": "Second message"}]}}) + "\n",
    ]

    async def _fake_create_subprocess_exec(*args, **kwargs):
        del args, kwargs
        return _FakeProcess(stdout_lines=outputs, stderr_lines=[], returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    with bind_current_request_context(ctx, comm=comm):
        agent = ClaudeCodeAgent.from_current_context(
            agent_name="kb-writer",
            workspace_path=workspace,
            allowed_tools=("Read",),
        )
        result = await agent.run_turn("Summarize repo")

    deltas = [
        envelope["delta"]["text"]
        for _, envelope in emitter.events
        if envelope.get("type") == "chat.delta"
    ]

    assert result.status == "completed"
    assert result.final_text == "First message\n\nSecond message"
    assert deltas == ["First message", "\n\nSecond message"]


@pytest.mark.asyncio
async def test_run_turn_emits_stderr_and_failure_step(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    comm, emitter = _make_comm()
    ctx = _ctx()

    async def _fake_create_subprocess_exec(*args, **kwargs):
        del args, kwargs
        return _FakeProcess(stdout_lines=[], stderr_lines=["fatal: boom\n"], returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    with bind_current_request_context(ctx, comm=comm):
        agent = ClaudeCodeAgent.from_current_context(
            agent_name="kb-writer",
            workspace_path=workspace,
        )
        result = await agent.run_followup("Continue")

    steps = [
        envelope
        for _, envelope in emitter.events
        if envelope.get("type") == "chat.step"
    ]

    assert result.status == "failed"
    assert result.turn_kind == "followup"
    assert any(step["event"]["step"] == "claude_code.agent.stderr" for step in steps)
    assert steps[-1]["event"]["status"] == "error"
    assert steps[-1]["data"]["error"] == "fatal: boom"


@pytest.mark.asyncio
async def test_followup_and_steer_resume_same_claude_session_id(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    comm, emitter = _make_comm()
    ctx = _ctx()
    captured: list[tuple] = []

    async def _fake_create_subprocess_exec(*args, **kwargs):
        captured.append(args)
        del kwargs
        return _FakeProcess(stdout_lines=[], stderr_lines=[], returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    with bind_current_request_context(ctx, comm=comm):
        agent = ClaudeCodeAgent.from_current_context(
            agent_name="kb-writer",
            workspace_path=workspace,
        )
        first = await agent.run_followup("Continue")
        second = await agent.run_steer("Change direction")

    assert first.session_id == second.session_id
    assert captured
    session_ids = []
    for args in captured:
        idx = args.index("--resume")
        session_ids.append(args[idx + 1])
    assert len(set(session_ids)) == 1

    started_steps = [
        envelope["data"]["turn_kind"]
        for _, envelope in emitter.events
        if envelope.get("type") == "chat.step" and envelope.get("event", {}).get("status") == "started"
    ]
    assert started_steps == ["followup", "steer"]


@pytest.mark.asyncio
async def test_run_turn_emits_accounting_event_with_usage(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    comm, _ = _make_comm()
    ctx = _ctx()
    backend = _RecordingAccountingBackend()

    outputs = [
        json.dumps({"type": "system", "subtype": "init", "model": "sonnet"}) + "\n",
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "model": "claude-sonnet-4-5-20250929",
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 30,
                        "cache_creation_input_tokens": 40,
                        "cache_read_input_tokens": 5,
                    },
                    "content": [{"type": "text", "text": "Done"}],
                },
            }
        )
        + "\n",
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "duration_ms": 1500,
                "duration_api_ms": 1200,
                "total_cost_usd": 0.0123,
            }
        )
        + "\n",
    ]

    async def _fake_create_subprocess_exec(*args, **kwargs):
        del args, kwargs
        return _FakeProcess(stdout_lines=outputs, stderr_lines=[], returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    AccountingSystem.init_storage(
        backend,
        enabled=True,
        cache_in_memory=False,
        redis_turn_cache=False,
    )
    AccountingSystem.set_context(
        user_id="admin-user-1",
        session_id="sid-claude",
        tenant_id="demo-tenant",
        project_id="demo-project",
        request_id="req-claude-code",
        app_bundle_id="bundle.claude",
        component="bundle.claude",
    )

    try:
        with bind_current_request_context(ctx, comm=comm):
            agent = ClaudeCodeAgent.from_current_context(
                agent_name="kb-writer",
                workspace_path=workspace,
            )
            result = await agent.run_turn("Summarize repo")
    finally:
        clear_context()
        AccountingSystem.init_storage(None, enabled=False)

    assert result.status == "completed"
    assert result.model == "claude-sonnet-4-5-20250929"
    assert result.cost_usd == pytest.approx(0.0123)
    assert backend.writes, "Claude Code run should emit an accounting event"

    _, content = backend.writes[-1]
    event = json.loads(content)
    assert event["service_type"] == "llm"
    assert event["provider"] == "anthropic"
    assert event["model_or_service"] == "claude-sonnet-4-5-20250929"
    assert event["success"] is True
    assert event["usage"]["input_tokens"] == 120
    assert event["usage"]["output_tokens"] == 30
    assert event["usage"]["cache_creation_tokens"] == 40
    assert event["usage"]["cache_read_tokens"] == 5
    assert event["usage"]["cost_usd"] == pytest.approx(0.0123)
    assert event["metadata"]["runtime"] == "claude_code"
    assert event["metadata"]["turn_kind"] == "regular"


@pytest.mark.asyncio
async def test_failed_run_marks_accounting_event_unsuccessful(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    comm, _ = _make_comm()
    ctx = _ctx()
    backend = _RecordingAccountingBackend()

    outputs = [
        json.dumps({"type": "system", "subtype": "init", "model": "haiku"}) + "\n",
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "model": "claude-haiku-4-5-20251001",
                    "usage": {
                        "input_tokens": 20,
                        "output_tokens": 10,
                    },
                },
            }
        )
        + "\n",
        json.dumps(
            {
                "type": "result",
                "subtype": "error",
                "duration_ms": 800,
                "total_cost_usd": 0.001,
            }
        )
        + "\n",
    ]

    async def _fake_create_subprocess_exec(*args, **kwargs):
        del args, kwargs
        return _FakeProcess(stdout_lines=outputs, stderr_lines=["fatal: boom\n"], returncode=1)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    AccountingSystem.init_storage(
        backend,
        enabled=True,
        cache_in_memory=False,
        redis_turn_cache=False,
    )
    AccountingSystem.set_context(
        user_id="admin-user-1",
        session_id="sid-claude",
        tenant_id="demo-tenant",
        project_id="demo-project",
        request_id="req-claude-code",
        app_bundle_id="bundle.claude",
        component="bundle.claude",
    )

    try:
        with bind_current_request_context(ctx, comm=comm):
            agent = ClaudeCodeAgent.from_current_context(
                agent_name="kb-writer",
                workspace_path=workspace,
            )
            result = await agent.run_turn("Continue")
    finally:
        clear_context()
        AccountingSystem.init_storage(None, enabled=False)

    assert result.status == "failed"
    assert backend.writes, "Failed Claude Code run should still emit an accounting event"

    _, content = backend.writes[-1]
    event = json.loads(content)
    assert event["service_type"] == "llm"
    assert event["provider"] == "anthropic"
    assert event["success"] is False
    assert event["error_message"] == "fatal: boom"
    assert event["usage"]["input_tokens"] == 20
    assert event["usage"]["output_tokens"] == 10
    assert event["usage"]["cost_usd"] == pytest.approx(0.001)

#!/usr/bin/env python
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

from dotenv import find_dotenv, load_dotenv

from kdcube_ai_app.apps.chat.sdk.solutions.claude_code import (
    ClaudeCodeAgent,
    ClaudeCodeAgentConfig,
    ClaudeCodeBinding,
)
from kdcube_ai_app.infra.accounting import with_accounting
from kdcube_ai_app.infra.accounting.envelope import bind_accounting, build_envelope_from_session


class _LocalRecordingStorageBackend:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.writes: list[Path] = []

    async def write_text_a(self, path: str, content: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.writes.append(target)


def _load_example_env() -> None:
    examples_root = Path(__file__).resolve().parent.parent
    example_env = examples_root / ".example.env"
    env = examples_root / ".env"

    if example_env.exists():
        load_dotenv(example_env, override=False)
    if env.exists():
        load_dotenv(env, override=True)
        return

    fallback = find_dotenv(usecwd=True)
    if fallback:
        load_dotenv(fallback, override=False)


def _resolve_file_storage_root(storage_uri: str | None) -> Path | None:
    raw = str(storage_uri or "").strip()
    if not raw:
        return None
    if raw.startswith("file://"):
        parsed = urlparse(raw)
        return Path(unquote(parsed.path))
    if "://" in raw:
        return None
    return Path(raw)


def _make_binding(*, user_id: str, conversation_id: str, session_id: str, agent_name: str) -> ClaudeCodeBinding:
    claude_session_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"kdcube/claude-code/{user_id}/{conversation_id}/{agent_name}",
        )
    )
    return ClaudeCodeBinding(
        user_id=user_id,
        conversation_id=conversation_id,
        session_id=session_id,
        claude_session_id=claude_session_id,
    )


async def main() -> None:
    _load_example_env()

    tenant_id = os.getenv("DEFAULT_TENANT", "home")
    project_id = os.getenv("DEFAULT_PROJECT_NAME", "demo")
    bundle_id = os.getenv("CLAUDE_CODE_DEMO_BUNDLE_ID", "demo.claude-code.accounting")
    demo_dir = Path(
        os.getenv("CLAUDE_CODE_ACCOUNTING_FAILURE_DEMO_DIR")
        or tempfile.mkdtemp(prefix="kdcube-claude-code-accounting-failure-")
    )
    configured_storage_root = _resolve_file_storage_root(os.getenv("KDCUBE_STORAGE_PATH"))
    storage_root = configured_storage_root or (demo_dir / "storage")
    workspace_root = demo_dir / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "README.md").write_text("failure smoke\n", encoding="utf-8")

    request_id = str(uuid.uuid4())
    conversation_id = f"conv-{uuid.uuid4().hex[:8]}"
    turn_id = f"turn-{uuid.uuid4().hex[:8]}"
    session = SimpleNamespace(
        user_id=os.getenv("DEMO_USER_ID", "demo-user"),
        session_id=os.getenv("DEMO_SESSION_ID", f"session-{uuid.uuid4().hex[:8]}"),
        user_type="privileged",
        timezone=os.getenv("DEMO_TIMEZONE", "UTC"),
    )

    storage_backend = _LocalRecordingStorageBackend(storage_root)
    envelope = build_envelope_from_session(
        session=session,
        tenant_id=tenant_id,
        project_id=project_id,
        request_id=request_id,
        component="sdk.examples.accounting.claude_code.failure",
        app_bundle_id=bundle_id,
        metadata={
            "demo": True,
            "runtime": "claude_code",
            "example": "claude_code_accounting_failure_smoke",
        },
    )

    binding = _make_binding(
        user_id=str(session.user_id),
        conversation_id=conversation_id,
        session_id=str(session.session_id),
        agent_name="claude-code-demo-failure",
    )

    agent = ClaudeCodeAgent(
        config=ClaudeCodeAgentConfig(
            agent_name="claude-code-demo-failure",
            workspace_path=workspace_root,
            allowed_tools=("Read",),
            command="claude-command-that-does-not-exist",
            env={},
        ),
        binding=binding,
        comm=None,
    )

    try:
        async with bind_accounting(envelope, storage_backend, enabled=True):
            async with with_accounting(
                "sdk.examples.accounting.claude_code.failure",
                agent="claude-code-demo-failure",
                conversation_id=conversation_id,
                turn_id=turn_id,
                metadata={
                    "agent": "claude-code-demo-failure",
                    "conversation_id": conversation_id,
                    "turn_id": turn_id,
                    "validation_mode": "failure-smoke",
                },
            ):
                await agent.run_turn("This call is expected to fail before reaching the provider.")
    except Exception as exc:
        print(f"Expected failure captured: {exc}")

    if not storage_backend.writes:
        raise SystemExit("No accounting event was written for the failure case.")

    event_path = storage_backend.writes[-1]
    event = json.loads(event_path.read_text(encoding="utf-8"))

    print()
    print("=== Claude Code failure accounting event ===")
    print(f"path: {event_path}")
    print(f"service_type: {event.get('service_type')}")
    print(f"provider: {event.get('provider')}")
    print(f"model_or_service: {event.get('model_or_service')}")
    print(f"success: {event.get('success')}")
    print(f"error_message: {event.get('error_message')}")
    print(f"usage: {json.dumps(event.get('usage') or {}, indent=2, ensure_ascii=False)}")
    print(f"metadata.runtime: {(event.get('metadata') or {}).get('runtime')}")
    print()
    print("This sample validates the failure-event path.")
    print("It does not validate provider-billed failed usage, because the CLI never reaches Anthropic.")
    if configured_storage_root is None:
        print("Storage note: KDCUBE_STORAGE_PATH was not a local file:// path, so the sample used a temp local storage root.")
    print(f"Demo artifacts root: {demo_dir}")


if __name__ == "__main__":
    asyncio.run(main())

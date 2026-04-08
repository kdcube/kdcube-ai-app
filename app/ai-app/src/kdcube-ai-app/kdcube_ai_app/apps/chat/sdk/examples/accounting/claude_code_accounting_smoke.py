#!/usr/bin/env python
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

from dotenv import find_dotenv, load_dotenv

from kdcube_ai_app.apps.chat.sdk.config import get_settings
from kdcube_ai_app.apps.chat.sdk.solutions.claude_code import (
    ClaudeCodeAgent,
    ClaudeCodeAgentConfig,
    ClaudeCodeBinding,
)
from kdcube_ai_app.infra.accounting import with_accounting
from kdcube_ai_app.infra.accounting.envelope import bind_accounting, build_envelope_from_session


class _LocalRecordingStorageBackend:
    """
    Minimal async storage backend for accounting examples.

    FileAccountingStorage writes relative paths such as:
      accounting/<tenant>/<project>/...
    We persist those under a local root and keep the writes list so the example
    can print the exact event path that was created.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.writes: list[Path] = []

    async def write_text_a(self, path: str, content: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.writes.append(target)


def _build_demo_workspace(workspace_root: Path) -> None:
    (workspace_root / "src").mkdir(parents=True, exist_ok=True)
    (workspace_root / "README.md").write_text(
        "# Claude Code Accounting Demo\n\n"
        "This workspace exists only to validate accountable Claude Code runs.\n",
        encoding="utf-8",
    )
    (workspace_root / "src" / "demo.py").write_text(
        'def greet(name: str) -> str:\n'
        '    return f"Hello, {name}"\n',
        encoding="utf-8",
    )


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

    settings = get_settings()
    claude_code_key = settings.CLAUDE_CODE_KEY or os.getenv("CLAUDE_CODE_KEY") or ""
    claude_bin = os.getenv("CLAUDE_CODE_BIN", "claude").strip() or "claude"

    if not claude_code_key:
        raise SystemExit(
            "CLAUDE_CODE_KEY is not set. Add it to your env or examples/.env before running this sample."
        )
    if shutil.which(claude_bin) is None:
        raise SystemExit(
            f"Claude Code binary '{claude_bin}' is not available on PATH."
        )

    tenant_id = os.getenv("DEFAULT_TENANT", settings.TENANT or "home")
    project_id = os.getenv("DEFAULT_PROJECT_NAME", settings.PROJECT or "demo")
    bundle_id = os.getenv("CLAUDE_CODE_DEMO_BUNDLE_ID", "demo.claude-code.accounting")
    demo_dir = Path(
        os.getenv("CLAUDE_CODE_ACCOUNTING_DEMO_DIR")
        or tempfile.mkdtemp(prefix="kdcube-claude-code-accounting-")
    )
    configured_storage_root = _resolve_file_storage_root(os.getenv("KDCUBE_STORAGE_PATH") or settings.STORAGE_PATH)
    storage_root = configured_storage_root or (demo_dir / "storage")
    workspace_root = demo_dir / "workspace"
    _build_demo_workspace(workspace_root)

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
        component="sdk.examples.accounting.claude_code",
        app_bundle_id=bundle_id,
        metadata={
            "demo": True,
            "runtime": "claude_code",
            "example": "claude_code_accounting_smoke",
        },
    )

    prompt = (
        "Read the current workspace and reply with three short bullets: "
        "what project this is, which files are present, and whether it is enough "
        "to continue work."
    )

    binding = _make_binding(
        user_id=str(session.user_id),
        conversation_id=conversation_id,
        session_id=str(session.session_id),
        agent_name="claude-code-demo",
    )
    env = {"CLAUDE_CODE_KEY": claude_code_key}
    agent = ClaudeCodeAgent(
        config=ClaudeCodeAgentConfig(
            agent_name="claude-code-demo",
            workspace_path=workspace_root,
            allowed_tools=("Read", "Grep"),
            command=claude_bin,
            env=env,
        ),
        binding=binding,
        comm=None,
    )

    async with bind_accounting(envelope, storage_backend, enabled=True):
        async with with_accounting(
            "sdk.examples.accounting.claude_code",
            agent="claude-code-demo",
            conversation_id=conversation_id,
            turn_id=turn_id,
            metadata={
                "agent": "claude-code-demo",
                "conversation_id": conversation_id,
                "turn_id": turn_id,
                "validation_mode": "smoke",
            },
        ):
            result = await agent.run_turn(prompt)

    if not storage_backend.writes:
        raise SystemExit("No accounting event was written.")

    event_path = storage_backend.writes[-1]
    event = json.loads(event_path.read_text(encoding="utf-8"))
    accounting_root = storage_root / "accounting"

    print()
    print("=== Claude Code run completed ===")
    print(f"status: {result.status}")
    print(f"model: {result.model}")
    print(f"cost_usd: {result.cost_usd}")
    print(f"session_id: {result.session_id}")
    print()
    print("=== Accounting event ===")
    print(f"path: {event_path}")
    print(f"service_type: {event.get('service_type')}")
    print(f"provider: {event.get('provider')}")
    print(f"model_or_service: {event.get('model_or_service')}")
    print(f"success: {event.get('success')}")
    print(f"usage: {json.dumps(event.get('usage') or {}, indent=2, ensure_ascii=False)}")
    print(f"metadata.runtime: {(event.get('metadata') or {}).get('runtime')}")
    print()
    print("=== Validation follow-up ===")
    print("Check that the event exists and contains provider/model/usage fields.")
    print("Then run the calculator over the generated accounting folder:")
    print(
        "PYTHONPATH=app/ai-app/src/kdcube-ai-app "
        "python app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/accounting/calc.py "
        f"{accounting_root}"
    )
    print()
    if configured_storage_root is None:
        print("Storage note: KDCUBE_STORAGE_PATH was not a local file:// path, so the sample used a temp local storage root.")
        print()
    print(f"Demo artifacts root: {demo_dir}")


if __name__ == "__main__":
    asyncio.run(main())

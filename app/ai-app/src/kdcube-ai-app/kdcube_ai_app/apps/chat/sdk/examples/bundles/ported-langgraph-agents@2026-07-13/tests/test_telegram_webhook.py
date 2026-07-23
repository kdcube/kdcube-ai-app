"""The second surface: the Telegram Bot API webhook (T2c).

These tests prove, offline (no DB, no API key, no network):

  1. the webhook surface is DECLARED — in the entrypoint (AST: the
     ``telegram_webhook`` method carries ``@api(route="public")``) and in the
     OpenAPI contract (the ``/public/telegram_webhook`` path);
  2. AUTH is enforced at the SDK boundary the bundle delegates to — a missing or
     wrong ``X-Telegram-Bot-Api-Secret-Token`` is rejected with 401;
  3. a parsed update ROUTES to the shared turn path — the bundle's thin wiring
     (``platform/telegram.py``) delegates to the SDK ``handle_webhook`` /
     ``run_with_queued_telegram_delivery`` (the SDK is mocked).

The Telegram protocol mechanics themselves live in the SDK; the bundle only
routes + renders, so these tests assert the wiring, not the protocol.
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest
import yaml

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = BUNDLE_ROOT / "entrypoint.py"
OPENAPI = BUNDLE_ROOT / "interface" / "ported-langgraph-agents.openapi.yaml"


class _FakeRequest:
    """Minimal stand-in for the platform request (headers + query only)."""

    def __init__(self, headers: dict | None = None, query: dict | None = None):
        self.headers = headers or {}
        self.query_params = query or {}


# ── 1. surface is declared ────────────────────────────────────────────────────

def test_entrypoint_declares_public_webhook_api() -> None:
    tree = ast.parse(ENTRYPOINT.read_text(encoding="utf-8"))
    webhook_api = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "telegram_webhook":
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "api":
                    webhook_api = dec
    assert webhook_api is not None, "entrypoint must declare a telegram_webhook @api handler"
    kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in webhook_api.keywords if kw.arg}
    assert kwargs.get("route") == "public"
    assert kwargs.get("method") == "POST"
    assert kwargs.get("alias") == "telegram_webhook"


def test_openapi_declares_the_webhook_path() -> None:
    contract = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    paths = contract.get("paths") or {}
    assert "/public/telegram_webhook" in paths
    post = paths["/public/telegram_webhook"]["post"]
    # No platform auth: the trust boundary is the webhook secret.
    assert post.get("security") == []
    assert "401" in post.get("responses", {}), "the contract must document the auth rejection"


# ── 2. auth is enforced (SDK boundary the bundle delegates to) ────────────────

def _user_admin():
    from kdcube_ai_app.apps.chat.sdk.integrations.telegram import user_admin
    return user_admin


def test_webhook_rejects_missing_secret_header() -> None:
    from fastapi import HTTPException

    user_admin = _user_admin()
    request = _FakeRequest(headers={})  # no X-Telegram-Bot-Api-Secret-Token
    with pytest.raises(HTTPException) as exc:
        asyncio.run(user_admin._resolve_webhook_integration_id(object(), request=request))
    assert exc.value.status_code == 401
    assert exc.value.detail == "telegram_webhook_secret_missing"


def test_webhook_rejects_wrong_secret(monkeypatch) -> None:
    from fastapi import HTTPException

    user_admin = _user_admin()
    # The bundle configures the SDK at entrypoint import; do the same here so the
    # rejection log path can resolve the bundle id. Storage is never touched on
    # the auth path, so a no-op factory is fine.
    _telegram_wiring().configure(bundle_id="ported-langgraph-agents@2026-07-13")

    # A single configured, enabled telegram integration whose secret is "correct".
    monkeypatch.setattr(
        user_admin,
        "configured_integrations",
        lambda entrypoint, provider="telegram": [{"id": "telegram.default", "enabled": True}],
    )

    async def _secret(entrypoint, *, provider, field, integration_id):
        return "correct-secret"

    monkeypatch.setattr(user_admin, "integration_secret_value", _secret)

    request = _FakeRequest(headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(user_admin._resolve_webhook_integration_id(object(), request=request))
    assert exc.value.status_code == 401
    assert exc.value.detail == "telegram_webhook_secret_invalid"


def test_webhook_accepts_matching_secret(monkeypatch) -> None:
    user_admin = _user_admin()
    monkeypatch.setattr(
        user_admin,
        "configured_integrations",
        lambda entrypoint, provider="telegram": [{"id": "telegram.default", "enabled": True}],
    )

    async def _secret(entrypoint, *, provider, field, integration_id):
        return "correct-secret"

    monkeypatch.setattr(user_admin, "integration_secret_value", _secret)

    request = _FakeRequest(headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"})
    resolved = asyncio.run(user_admin._resolve_webhook_integration_id(object(), request=request))
    assert resolved == "telegram.default"


# ── 3. a parsed update routes to the shared turn path ─────────────────────────

def _telegram_wiring():
    _name, module = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "telegram.py")
    return module


def test_handle_webhook_delegates_to_the_sdk(monkeypatch) -> None:
    wiring = _telegram_wiring()
    user_admin = _user_admin()
    seen: dict = {}

    async def _fake_handle(entrypoint, *, request=None, **update):
        seen["entrypoint"] = entrypoint
        seen["request"] = request
        seen["update"] = update
        return {"ok": True, "stage": "queued-turn"}

    monkeypatch.setattr(user_admin, "handle_webhook", _fake_handle)

    entrypoint = object()
    request = _FakeRequest(headers={"X-Telegram-Bot-Api-Secret-Token": "x"})
    update = {"update_id": 42, "message": {"text": "hello from telegram", "chat": {"id": 7}}}

    result = asyncio.run(wiring.handle_webhook(entrypoint, request=request, **update))

    assert result["ok"] is True
    assert seen["entrypoint"] is entrypoint
    assert seen["request"] is request
    # The parsed update is forwarded verbatim to the SDK, which turns it into
    # external_events[] and drives execute_core.
    assert seen["update"]["update_id"] == 42
    assert seen["update"]["message"]["text"] == "hello from telegram"


def test_run_turn_with_delivery_wraps_the_runner(monkeypatch) -> None:
    wiring = _telegram_wiring()
    user_admin = _user_admin()

    async def _fake_wrap(entrypoint, *, runner):
        # Mirror the SDK's browser-turn behavior: run the runner, return its result.
        return await runner()

    monkeypatch.setattr(user_admin, "run_with_queued_telegram_delivery", _fake_wrap)

    async def _runner():
        return {"answer": "42", "final_answer": "42"}

    result = asyncio.run(wiring.run_turn_with_delivery(object(), runner=_runner))
    assert result["final_answer"] == "42"

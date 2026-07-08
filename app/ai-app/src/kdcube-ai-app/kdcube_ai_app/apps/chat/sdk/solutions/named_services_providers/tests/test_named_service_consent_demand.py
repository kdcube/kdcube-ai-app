# SPDX-License-Identifier: MIT

"""In-chat named-service tools speak the demand-driven consent contract.

A provider consent error (gate 2: connected-account claims inside the realm)
raises the same ask as a direct tool attempt: the pending demand is recorded
and ONE scoped chat consent event goes out. The mapping runs both directions:
the banner lists the UNDERLYING provider claims (mail get → the gmail read
claim) while the turn-off spotlight targets the NAMESPACE entry the user sees
in the composer menu. The external MCP surface renders consent from the
response itself and stays untouched.
"""

from __future__ import annotations

from typing import Any

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube import consent_demand
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.tools import (
    _raise_named_service_consent_demand,
)


def _consent_error_payload() -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "needs_connected_account_consent",
            "message": "Connect Gmail and approve gmail:read.",
            "details": {
                "reason": "connect_required",
                "consent": {
                    "kind": "delegated_to_kdcube.connected_account",
                    "reason": "connect_required",
                    "provider_id": "google",
                    "connector_app_id": "gmail",
                    "claims": ["gmail:read"],
                    "url": "/widgets/connections_settings?tab=delegated_to_kdcube&provider_id=google&claims=gmail%3Aread",
                    "action_label": "Connect account",
                },
            },
        },
    }


def _record_announces(monkeypatch):
    announced: list[dict[str, Any]] = []

    async def fake_announce(**kwargs):
        announced.append(kwargs)
        return True

    monkeypatch.setattr(consent_demand, "announce_consent_demand", fake_announce)
    return announced


@pytest.mark.asyncio
async def test_named_service_consent_error_raises_the_scoped_demand(monkeypatch):
    announced = _record_announces(monkeypatch)

    await _raise_named_service_consent_demand(
        _consent_error_payload(), namespace="mail", tool_name="get_object",
    )

    assert len(announced) == 1
    demand = announced[0]
    # Underlying provider claims travel to the broker/plan…
    assert demand["provider_id"] == "google"
    assert demand["claims"] == ["gmail:read"]
    # …while the demand (and the banner's turn-off spotlight) names the
    # NAMESPACE entry the user sees in the composer menu.
    assert demand["tool_name"] == "mail"
    banner = demand["payload"]
    assert banner["error"]["code"] == "needs_connected_account_consent"
    assert banner["consent"]["claims"] == ["gmail:read"]
    assert banner["consent"]["tools"] == ["mail"]
    assert "tab=delegated_to_kdcube" in banner["consent"]["url"]


@pytest.mark.asyncio
async def test_scoped_namespace_maps_to_its_menu_entry(monkeypatch):
    announced = _record_announces(monkeypatch)
    await _raise_named_service_consent_demand(
        _consent_error_payload(), namespace="mail:inbox", tool_name="search_objects",
    )
    assert announced[0]["tool_name"] == "mail"
    assert announced[0]["payload"]["consent"]["tools"] == ["mail"]


@pytest.mark.asyncio
async def test_plain_errors_and_successes_raise_nothing(monkeypatch):
    announced = _record_announces(monkeypatch)

    await _raise_named_service_consent_demand({"ok": True}, namespace="mail", tool_name="get_object")
    await _raise_named_service_consent_demand(
        {"ok": False, "error": {"code": "named_service_not_found", "message": "…"}},
        namespace="mail",
        tool_name="get_object",
    )
    assert announced == []


@pytest.mark.asyncio
async def test_menu_inventory_renders_even_when_coverage_hangs(monkeypatch):
    """The '+' menu must render even when coverage computation stalls: the
    decoration runs under a budget; rows simply omit consent state and a
    warning names the miss."""
    import asyncio
    import time as clock
    from types import SimpleNamespace

    from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint import BaseEntrypoint
    from kdcube_ai_app.apps.chat.sdk.runtime import tool_config as tool_config_mod
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube import consent_demand as cd
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube.models import ToolClaimPolicy

    policy = ToolClaimPolicy.from_config("slack.search_slack", {
        "connected_accounts": [
            {"provider_id": "slack", "connector_app_id": "demo", "claims": ["slack:search"]},
        ],
    })
    monkeypatch.setattr(
        tool_config_mod,
        "agent_tool_config_from_bundle_props",
        lambda *a, **k: SimpleNamespace(tool_claim_policies=[policy]),
    )

    async def hanging_coverage(**kwargs):
        await asyncio.sleep(30)
        return {}

    monkeypatch.setattr(cd, "claim_coverage_for_policies", hanging_coverage)

    logged: list[tuple[str, str]] = []
    stub = SimpleNamespace(
        bundle_props={},
        logger=SimpleNamespace(log=lambda msg, level=None, **kw: logged.append((str(level), str(msg)))),
        CLAIM_COVERAGE_BUDGET_SECONDS=0.2,
        _agent_selection_identity=lambda: {"user_id": "u1", "bundle_id": "b1"},
        _bundle_root=lambda: None,
    )

    catalog = {"tools": [{"alias": "slack", "tools": [{"name": "search_slack"}]}], "named_services": []}
    started = clock.monotonic()
    out = await BaseEntrypoint._attach_claim_coverage(stub, dict(catalog), "main")
    elapsed = clock.monotonic() - started

    assert elapsed < 2.0, "the budget bounded the coverage decoration"
    assert out["tools"][0].get("consent") is None
    assert out["tools"][0]["tools"][0].get("consent") is None
    assert any("without consent state" in msg for _lvl, msg in logged)

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

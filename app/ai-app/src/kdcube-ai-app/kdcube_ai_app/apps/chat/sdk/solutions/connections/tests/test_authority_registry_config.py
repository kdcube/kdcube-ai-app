# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry_config import (
    authority_provider_instances,
    resolve_authority_provider_instance,
)


def _registry():
    return {
        "authorities": {
            "kdcube.platform": {
                "platform": True,
                "providers": {
                    "cognito": {
                        "type": "cognito",
                        "authenticator": {"type": "cognito_id_token"},
                    },
                    "versatile_telegram_session": {
                        "type": "bundle_session_login",
                        "host": {
                            "bundle_id": "versatile@2026-03-31-13-36",
                            "route": "public",
                            "operation": "auth_telegram_session",
                        },
                        "issuer": {
                            "type": "kdcube_session_token",
                            "ttl_seconds": 43200,
                        },
                        "grants": {"roles": ["kdcube:role:chat-user"]},
                    },
                    "disabled_provider": {
                        "type": "bundle_session_login",
                        "enabled": False,
                    },
                },
            },
            "telegram.kdcube_ref": {
                "platform": False,
                "providers": {
                    "telegram_bot_init_data": {
                        "type": "telegram_init_data",
                        "authenticator": {"secret_ref": "secret.ref"},
                    },
                },
            },
        },
    }


def test_authority_provider_instances_flatten_configured_instances():
    rows = authority_provider_instances(_registry())

    assert [
        (row["authority_id"], row["provider_id"], row["provider_type"], row["platform"])
        for row in rows
    ] == [
        ("kdcube.platform", "cognito", "cognito", True),
        ("kdcube.platform", "versatile_telegram_session", "bundle_session_login", True),
        ("telegram.kdcube_ref", "telegram_bot_init_data", "telegram_init_data", False),
    ]


def test_resolve_authority_provider_instance_by_host_operation():
    result = resolve_authority_provider_instance(
        _registry(),
        provider_type="bundle_session_login",
        host_bundle_id="versatile@2026-03-31-13-36",
        host_route="public",
        host_operation="auth_telegram_session",
    )

    assert result["ok"] is True
    assert result["authority_id"] == "kdcube.platform"
    assert result["provider_id"] == "versatile_telegram_session"
    assert result["provider"]["issuer"]["ttl_seconds"] == 43200


def test_resolve_authority_provider_instance_fails_closed_when_missing():
    result = resolve_authority_provider_instance(
        _registry(),
        provider_type="bundle_session_login",
        host_bundle_id="versatile@2026-03-31-13-36",
        host_route="public",
        host_operation="missing",
    )

    assert result == {"ok": False, "error": "authority_provider_not_found"}

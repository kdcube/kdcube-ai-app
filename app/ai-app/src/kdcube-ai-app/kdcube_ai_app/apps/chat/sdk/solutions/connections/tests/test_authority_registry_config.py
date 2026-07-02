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
                "role_bindings": {
                    "emails": {
                        "owner@example.com": {"roles": ["kdcube:role:super-admin"]}
                    }
                },
                "providers": {
                    "cognito": {
                        "type": "cognito",
                        "authenticator": {"type": "cognito_id_token"},
                    },
                    "versatile_google_session": {
                        "type": "bundle_session_login",
                        "entrypoints": {
                            "login": {
                                "bundle_id": "versatile@2026-03-31-13-36",
                                "route": "public",
                                "operation": "platform_login",
                            },
                            "session_issue": {
                                "bundle_id": "versatile@2026-03-31-13-36",
                                "route": "public",
                                "operation": "auth_google_session",
                            },
                            "consent": {
                                "bundle_id": "versatile@2026-03-31-13-36",
                                "route": "public",
                                "operation": "delegated_consent",
                            },
                        },
                        "input": {
                            "authenticator_ref": {
                                "authority_id": "google.accounts",
                                "provider_id": "google_oidc",
                            }
                        },
                        "issuer": {
                            "type": "kdcube_session_token",
                            "ttl_seconds": 43200,
                        },
                        "grants": {"roles": ["kdcube:role:registered"]},
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
            "google.accounts": {
                "providers": {
                    "google_oidc": {
                        "type": "google_id_token",
                        "authenticator": {"client_id": "client.apps.googleusercontent.com"},
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
        ("kdcube.platform", "versatile_google_session", "bundle_session_login", True),
        ("telegram.kdcube_ref", "telegram_bot_init_data", "telegram_init_data", False),
        ("google.accounts", "google_oidc", "google_id_token", False),
    ]


def test_resolve_authority_provider_instance_by_host_operation():
    result = resolve_authority_provider_instance(
        _registry(),
        provider_type="bundle_session_login",
        host_bundle_id="versatile@2026-03-31-13-36",
        host_route="public",
        host_operation="auth_google_session",
    )

    assert result["ok"] is True
    assert result["authority_id"] == "kdcube.platform"
    assert result["provider_id"] == "versatile_google_session"
    assert result["entrypoints"]["login"]["operation"] == "platform_login"
    assert result["entrypoints"]["consent"]["operation"] == "delegated_consent"
    assert result["provider"]["issuer"]["ttl_seconds"] == 43200
    assert result["authority"]["role_bindings"]["emails"]["owner@example.com"]["roles"] == ["kdcube:role:super-admin"]


def test_resolve_authority_provider_instance_by_consent_entrypoint():
    result = resolve_authority_provider_instance(
        _registry(),
        provider_type="bundle_session_login",
        host_bundle_id="versatile@2026-03-31-13-36",
        host_route="public",
        host_operation="delegated_consent",
    )

    assert result["ok"] is True
    assert result["authority_id"] == "kdcube.platform"
    assert result["provider_id"] == "versatile_google_session"


def test_resolve_authority_provider_instance_by_authority_and_provider_id():
    result = resolve_authority_provider_instance(
        _registry(),
        authority_id="google.accounts",
        provider_id="google_oidc",
    )

    assert result["ok"] is True
    assert result["provider_type"] == "google_id_token"
    assert result["provider"]["authenticator"]["client_id"] == "client.apps.googleusercontent.com"


def test_resolve_authority_provider_instance_fails_closed_when_missing():
    result = resolve_authority_provider_instance(
        _registry(),
        provider_type="bundle_session_login",
        host_bundle_id="versatile@2026-03-31-13-36",
        host_route="public",
        host_operation="missing",
    )

    assert result == {"ok": False, "error": "authority_provider_not_found"}

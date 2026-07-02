# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.infra.bundle_operations import (
    BundleOperationCall,
    bind_bundle_operation_caller,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry_client import AuthorityRegistryClient


class _Entrypoint:
    bundle_props = {"connections": {"connection_hub": {"bundle_id": "connection-hub@test"}}}

    def bundle_prop(self, path: str, default=None):
        current = self.bundle_props
        for part in path.split("."):
            if not isinstance(current, dict):
                return default
            current = current.get(part)
        return default if current is None else current


@pytest.mark.asyncio
async def test_authority_registry_client_resolves_public_provider_entrypoint():
    calls: list[BundleOperationCall] = []

    async def _caller(call: BundleOperationCall):
        calls.append(call)
        return {
            "authority_provider_entrypoint_resolve": {
                "ok": True,
                "url": "/api/integrations/bundles/t/p/versatile@2026-03-31-13-36/public/platform_login",
            }
        }

    with bind_bundle_operation_caller(_caller):
        result = await AuthorityRegistryClient(_Entrypoint()).resolve_provider_entrypoint(
            authority_id="kdcube.platform",
            provider_id="versatile_google_session",
            entrypoint="login",
        )

    assert result["ok"] is True
    assert result["url"].endswith("/public/platform_login")
    assert calls == [
        BundleOperationCall(
            bundle_id="connection-hub@test",
            operation="authority_provider_entrypoint_resolve",
            data={
                "authority_id": "kdcube.platform",
                "provider_id": "versatile_google_session",
                "provider_type": "",
                "entrypoint": "login",
            },
            tenant=None,
            project=None,
            route="public",
            http_method="POST",
        )
    ]

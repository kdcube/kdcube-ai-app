# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""SDK client for Connection Hub authority-registry operations."""

from __future__ import annotations

from typing import Any, Mapping

from kdcube_ai_app.apps.chat.sdk.infra.bundle_operations import call_bundle_operation
from kdcube_ai_app.apps.chat.sdk.solutions.connections.connection_edges import (
    DEFAULT_CONNECTION_HUB_BUNDLE_ID,
    connection_hub_bundle_id_from_entrypoint,
)


def _str(value: Any) -> str:
    return str(value or "").strip()


def _unwrap_operation_result(operation: str, result: Mapping[str, Any]) -> dict[str, Any]:
    if operation in result and isinstance(result.get(operation), Mapping):
        return dict(result.get(operation) or {})
    return dict(result)


class AuthorityRegistryClient:
    """Typed app-to-app client for Connection Hub authority registry lookups."""

    def __init__(
        self,
        entrypoint: Any,
        *,
        connection_hub_bundle_id: str | None = None,
        tenant: str | None = None,
        project: str | None = None,
    ) -> None:
        self.entrypoint = entrypoint
        self.bundle_id = (
            _str(connection_hub_bundle_id)
            or connection_hub_bundle_id_from_entrypoint(entrypoint)
            or DEFAULT_CONNECTION_HUB_BUNDLE_ID
        )
        self.tenant = _str(tenant) or None
        self.project = _str(project) or None

    async def resolve_provider(
        self,
        *,
        authority_id: str = "",
        provider_id: str = "",
        provider_type: str = "",
        host_bundle_id: str = "",
        host_route: str = "",
        host_operation: str = "",
    ) -> dict[str, Any]:
        operation = "authority_provider_resolve"
        result = await call_bundle_operation(
            bundle_id=self.bundle_id,
            operation=operation,
            data={
                "authority_id": _str(authority_id),
                "provider_id": _str(provider_id),
                "provider_type": _str(provider_type),
                "host_bundle_id": _str(host_bundle_id),
                "host_route": _str(host_route),
                "host_operation": _str(host_operation),
            },
            tenant=self.tenant,
            project=self.project,
            route="operations",
            http_method="POST",
        )
        return _unwrap_operation_result(operation, result)

    async def resolve_provider_entrypoint(
        self,
        *,
        authority_id: str = "",
        provider_id: str = "",
        provider_type: str = "",
        entrypoint: str = "login",
    ) -> dict[str, Any]:
        operation = "authority_provider_entrypoint_resolve"
        result = await call_bundle_operation(
            bundle_id=self.bundle_id,
            operation=operation,
            data={
                "authority_id": _str(authority_id),
                "provider_id": _str(provider_id),
                "provider_type": _str(provider_type),
                "entrypoint": _str(entrypoint) or "login",
            },
            tenant=self.tenant,
            project=self.project,
            route="public",
            http_method="POST",
        )
        return _unwrap_operation_result(operation, result)


__all__ = ["AuthorityRegistryClient"]

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""User-connected integration data models.

These models are intentionally storage- and transport-neutral. They describe the
Connection Hub-owned contract for external provider accounts connected by a
platform user. Raw provider credentials are not part of browser/MCP-facing
models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


CONNECTION_HUB_BUNDLE_ID = "connection-hub@1-0"
STATUS_CONNECTED = "connected"
STATUS_REVOKED = "revoked"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_str(value: Any) -> str:
    return str(value or "").strip()


def as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = as_str(value).lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def as_str_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.replace(",", " ").split() if part.strip())
    if isinstance(value, (list, tuple, set)):
        return tuple(as_str(part) for part in value if as_str(part))
    return ()


def as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class ProviderCapability:
    """One KDCube-normalized capability exposed by an external provider account."""

    capability_id: str
    label: str = ""
    description: str = ""
    provider_scopes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "label": self.label,
            "description": self.description,
            "provider_scopes": list(self.provider_scopes),
        }

    @classmethod
    def from_config(cls, capability_id: str, value: Any) -> "ProviderCapability":
        data = as_dict(value)
        return cls(
            capability_id=as_str(capability_id),
            label=as_str(data.get("label")),
            description=as_str(data.get("description")),
            provider_scopes=as_str_list(data.get("provider_scopes") or data.get("scopes")),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProviderCapability":
        data = dict(value or {})
        return cls(
            capability_id=as_str(data.get("capability_id") or data.get("id")),
            label=as_str(data.get("label")),
            description=as_str(data.get("description")),
            provider_scopes=as_str_list(data.get("provider_scopes") or data.get("scopes")),
        )


@dataclass(frozen=True)
class ConnectorApp:
    """Admin-configured connector application for one provider."""

    app_id: str
    provider_id: str
    label: str = ""
    enabled: bool = True
    client_id: str = ""
    client_secret_ref: str = ""
    redirect_uri: str = ""
    capability_ceiling: tuple[str, ...] = ()

    def to_dict(self, *, include_client_id: bool = False, include_secret_refs: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "app_id": self.app_id,
            "provider_id": self.provider_id,
            "label": self.label,
            "enabled": self.enabled,
            "redirect_uri": self.redirect_uri,
            "capability_ceiling": list(self.capability_ceiling),
        }
        if include_client_id:
            data["client_id"] = self.client_id
        if include_secret_refs and self.client_secret_ref:
            data["client_secret_ref"] = self.client_secret_ref
        return data

    @classmethod
    def from_config(cls, provider_id: str, app_id: str, value: Any) -> "ConnectorApp":
        data = as_dict(value)
        return cls(
            app_id=as_str(app_id),
            provider_id=as_str(provider_id),
            label=as_str(data.get("label")),
            enabled=as_bool(data.get("enabled"), default=True),
            client_id=as_str(data.get("client_id")),
            client_secret_ref=as_str(data.get("client_secret_ref")),
            redirect_uri=as_str(data.get("redirect_uri")),
            capability_ceiling=as_str_list(data.get("capability_ceiling") or data.get("capabilities")),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConnectorApp":
        data = dict(value or {})
        return cls(
            app_id=as_str(data.get("app_id")),
            provider_id=as_str(data.get("provider_id") or data.get("provider")),
            label=as_str(data.get("label")),
            enabled=as_bool(data.get("enabled"), default=True),
            client_id=as_str(data.get("client_id")),
            client_secret_ref=as_str(data.get("client_secret_ref")),
            redirect_uri=as_str(data.get("redirect_uri")),
            capability_ceiling=as_str_list(data.get("capability_ceiling") or data.get("capabilities")),
        )


@dataclass(frozen=True)
class IntegrationProvider:
    """Connection Hub provider registry row."""

    provider_id: str
    label: str = ""
    adapter: str = ""
    enabled: bool = True
    capabilities: dict[str, ProviderCapability] = field(default_factory=dict)
    connector_apps: dict[str, ConnectorApp] = field(default_factory=dict)

    def to_dict(self, *, include_client_ids: bool = False, include_secret_refs: bool = False) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "adapter": self.adapter,
            "enabled": self.enabled,
            "capabilities": {
                key: value.to_dict() for key, value in sorted(self.capabilities.items())
            },
            "connector_apps": {
                key: value.to_dict(include_client_id=include_client_ids, include_secret_refs=include_secret_refs)
                for key, value in sorted(self.connector_apps.items())
            },
        }

    @classmethod
    def from_config(cls, provider_id: str, value: Any) -> "IntegrationProvider":
        data = as_dict(value)
        capabilities = {
            as_str(key): ProviderCapability.from_config(as_str(key), raw)
            for key, raw in as_dict(data.get("capabilities")).items()
            if as_str(key)
        }
        apps = {
            as_str(key): ConnectorApp.from_config(provider_id, as_str(key), raw)
            for key, raw in as_dict(data.get("connector_apps") or data.get("apps")).items()
            if as_str(key)
        }
        return cls(
            provider_id=as_str(provider_id),
            label=as_str(data.get("label")),
            adapter=as_str(data.get("adapter") or data.get("adapter_id")),
            enabled=as_bool(data.get("enabled"), default=True),
            capabilities=capabilities,
            connector_apps=apps,
        )


@dataclass(frozen=True)
class UserIntegrationsConfig:
    """Parsed Connection Hub user-integrations config."""

    enabled: bool = False
    providers: dict[str, IntegrationProvider] = field(default_factory=dict)

    def provider(self, provider_id: str) -> IntegrationProvider | None:
        return self.providers.get(as_str(provider_id))

    def to_dict(self, *, include_client_ids: bool = False, include_secret_refs: bool = False) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "providers": {
                key: value.to_dict(include_client_ids=include_client_ids, include_secret_refs=include_secret_refs)
                for key, value in sorted(self.providers.items())
            },
        }

    @classmethod
    def from_config(cls, value: Any) -> "UserIntegrationsConfig":
        data = as_dict(value)
        providers = {
            as_str(key): IntegrationProvider.from_config(as_str(key), raw)
            for key, raw in as_dict(data.get("providers")).items()
            if as_str(key)
        }
        return cls(enabled=as_bool(data.get("enabled"), default=bool(providers)), providers=providers)


@dataclass(frozen=True)
class ConnectedAccount:
    """One external provider account connected by a platform user."""

    account_id: str
    provider_id: str
    connector_app_id: str = ""
    external_subject: str = ""
    display_name: str = ""
    email: str = ""
    workspace: str = ""
    capabilities: tuple[str, ...] = ()
    credential_id: str = ""
    status: str = STATUS_CONNECTED
    connected_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def connected(self) -> bool:
        return self.status == STATUS_CONNECTED and bool(self.credential_id)

    def allows(self, capability: str) -> bool:
        return as_str(capability) in set(self.capabilities)

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "provider_id": self.provider_id,
            "connector_app_id": self.connector_app_id,
            "external_subject": self.external_subject,
            "display_name": self.display_name,
            "email": self.email,
            "workspace": self.workspace,
            "capabilities": list(self.capabilities),
            "credential_id": self.credential_id,
            "status": self.status,
            "connected_at": self.connected_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata or {}),
        }

    def public_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        data["has_credential"] = bool(data.pop("credential_id", ""))
        return data

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ConnectedAccount":
        data = dict(value or {})
        return cls(
            account_id=as_str(data.get("account_id")),
            provider_id=as_str(data.get("provider_id") or data.get("provider")),
            connector_app_id=as_str(data.get("connector_app_id") or data.get("app_id")),
            external_subject=as_str(data.get("external_subject") or data.get("external_user_id")),
            display_name=as_str(data.get("display_name")),
            email=as_str(data.get("email")),
            workspace=as_str(data.get("workspace")),
            capabilities=as_str_list(data.get("capabilities") or data.get("scope")),
            credential_id=as_str(data.get("credential_id")),
            status=as_str(data.get("status")) or STATUS_CONNECTED,
            connected_at=as_str(data.get("connected_at")),
            updated_at=as_str(data.get("updated_at")),
            metadata=as_dict(data.get("metadata")),
        )


@dataclass(frozen=True)
class CredentialHandle:
    """Server-side result that authorizes provider use for one connected account."""

    provider_id: str
    account_id: str
    credential_id: str
    capabilities: tuple[str, ...]
    credential: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_credential: bool = False) -> dict[str, Any]:
        data = {
            "provider_id": self.provider_id,
            "account_id": self.account_id,
            "credential_id": self.credential_id,
            "capabilities": list(self.capabilities),
            "has_credential": bool(self.credential),
        }
        if include_credential:
            data["credential"] = dict(self.credential or {})
        return data


@dataclass(frozen=True)
class CapabilityResolution:
    """Result of broker.ensure_capability."""

    ok: bool
    provider_id: str
    capability: str
    account_id: str = ""
    credential: CredentialHandle | None = None
    error: str = ""
    message: str = ""
    connect_url: str = ""
    candidates: tuple[str, ...] = ()

    @property
    def consent_required(self) -> bool:
        return self.error == "consent_required"

    def to_dict(self, *, include_credential: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "ok": self.ok,
            "provider_id": self.provider_id,
            "capability": self.capability,
            "account_id": self.account_id,
        }
        if self.credential is not None:
            data["credential"] = self.credential.to_dict(include_credential=include_credential)
        if self.error:
            data["error"] = self.error
        if self.message:
            data["message"] = self.message
        if self.connect_url:
            data["connect_url"] = self.connect_url
        if self.candidates:
            data["candidates"] = list(self.candidates)
        return data


__all__ = [
    "CONNECTION_HUB_BUNDLE_ID",
    "STATUS_CONNECTED",
    "STATUS_REVOKED",
    "ProviderCapability",
    "ConnectorApp",
    "IntegrationProvider",
    "UserIntegrationsConfig",
    "ConnectedAccount",
    "CredentialHandle",
    "CapabilityResolution",
    "as_bool",
    "as_dict",
    "as_str",
    "as_str_list",
    "utc_now",
]

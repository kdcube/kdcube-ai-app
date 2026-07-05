# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Provider adapter registry for user-connected integrations.

Adapters are provider protocol mechanics only. They do not own platform
identity, policy, consent, or credential storage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import time
import httpx


class UserIntegrationAdapter(ABC):
    adapter_id: str = ""
    label: str = ""
    kind: str = ""
    authorize_url: str = ""
    token_url: str = ""
    oauth_default_scopes: tuple[str, ...] = ()

    @property
    def oauth_enabled(self) -> bool:
        return bool(self.authorize_url and self.token_url)

    def provider_scopes_for_capabilities(self, capabilities: list[str], capability_map: dict[str, Any]) -> list[str]:
        scopes: list[str] = []
        seen: set[str] = set()
        for capability in capabilities:
            raw = capability_map.get(str(capability or "").strip())
            provider_scopes = []
            if hasattr(raw, "provider_scopes"):
                provider_scopes = list(getattr(raw, "provider_scopes") or [])
            elif isinstance(raw, dict):
                provider_scopes = list(raw.get("provider_scopes") or raw.get("scopes") or [])
            for scope in provider_scopes:
                value = str(scope or "").strip()
                if value and value not in seen:
                    seen.add(value)
                    scopes.append(value)
        if not scopes:
            scopes.extend(self.oauth_default_scopes)
        return scopes

    def authorize_scope_param(self) -> str:
        return "scope"

    def authorize_extra_params(self) -> dict[str, Any]:
        return {}

    def extract_token(self, raw: dict[str, Any]) -> dict[str, Any]:
        return dict(raw or {})

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        if not self.token_url:
            raise ValueError(f"{self.adapter_id} does not support OAuth token exchange")
        if not client_id or not client_secret:
            raise ValueError(f"{self.adapter_id} OAuth client id/secret are not configured")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"{self.adapter_id} token exchange failed: {exc}") from exc
        try:
            parsed = response.json()
        except Exception:
            parsed = {}
        if response.status_code >= 400:
            message = ""
            if isinstance(parsed, dict):
                message = str(parsed.get("error_description") or parsed.get("error") or "")
            raise RuntimeError(message or f"{self.adapter_id} token exchange failed: HTTP {response.status_code}")
        token = self.extract_token(parsed if isinstance(parsed, dict) else {})
        if "expires_in" in token and "expires_at" not in token:
            try:
                token["expires_at"] = int(time.time()) + int(token["expires_in"])
            except Exception:
                pass
        return token

    async def fetch_profile(self, *, access_token: str, token: dict[str, Any] | None = None) -> dict[str, Any]:
        del access_token, token
        return {}

    @abstractmethod
    async def normalize_profile(self, credential: dict[str, Any]) -> dict[str, Any]:
        """Return normalized connected-account identity fields for a credential."""
        raise NotImplementedError


_ADAPTERS: dict[str, UserIntegrationAdapter] = {}


def register_adapter(adapter: UserIntegrationAdapter | type[UserIntegrationAdapter]) -> UserIntegrationAdapter:
    inst = adapter() if isinstance(adapter, type) else adapter
    adapter_id = str(getattr(inst, "adapter_id", "") or "").strip()
    if not adapter_id:
        raise ValueError("UserIntegrationAdapter.adapter_id is required")
    _ADAPTERS[adapter_id] = inst
    return inst


def adapter(adapter_id: str):
    def _decorator(cls: type[UserIntegrationAdapter]) -> type[UserIntegrationAdapter]:
        inst = cls()
        inst.adapter_id = str(adapter_id or getattr(inst, "adapter_id", "") or "").strip()
        register_adapter(inst)
        return cls

    return _decorator


def resolve_adapter(adapter_id: str) -> UserIntegrationAdapter:
    key = str(adapter_id or "").strip()
    try:
        return _ADAPTERS[key]
    except KeyError as exc:
        raise KeyError(f"unknown user integration adapter: {key!r}") from exc


def list_adapters() -> list[UserIntegrationAdapter]:
    return sorted(_ADAPTERS.values(), key=lambda item: getattr(item, "adapter_id", ""))


__all__ = [
    "UserIntegrationAdapter",
    "adapter",
    "list_adapters",
    "register_adapter",
    "resolve_adapter",
]

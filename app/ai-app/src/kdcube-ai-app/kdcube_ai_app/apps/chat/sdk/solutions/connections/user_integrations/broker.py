# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Credential broker for user-connected integrations."""

from __future__ import annotations

from typing import Any

from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.models import (
    CapabilityResolution,
    CredentialHandle,
    UserIntegrationsConfig,
    as_str,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.store import UserIntegrationStore


class UserIntegrationBroker:
    """Resolve provider capabilities for one platform user."""

    def __init__(self, *, config: UserIntegrationsConfig, store: UserIntegrationStore) -> None:
        self.config = config
        self.store = store

    async def ensure_capability(
        self,
        *,
        provider_id: str,
        capability: str,
        account_id: str | None = None,
        purpose: str = "",
    ) -> CapabilityResolution:
        provider_key = as_str(provider_id)
        capability_key = as_str(capability)
        account_key = as_str(account_id)
        provider = self.config.provider(provider_key)
        if not self.config.enabled or provider is None or not provider.enabled:
            return self._consent_required(
                provider_id=provider_key,
                capability=capability_key,
                account_id=account_key,
                message=f"Provider {provider_key or '<missing>'} is not enabled in Connection Hub.",
            )
        if capability_key not in provider.capabilities:
            return CapabilityResolution(
                ok=False,
                provider_id=provider_key,
                capability=capability_key,
                account_id=account_key,
                error="capability_not_configured",
                message=f"Capability {capability_key or '<missing>'} is not configured for provider {provider_key}.",
            )

        accounts = await self.store.list_accounts(provider_id=provider_key)
        if account_key:
            account = next((item for item in accounts if item.account_id == account_key), None)
            if account is None:
                return self._consent_required(
                    provider_id=provider_key,
                    capability=capability_key,
                    account_id=account_key,
                    message=f"Connected account {account_key} is not available.",
                )
        else:
            candidates = [item for item in accounts if item.connected and item.allows(capability_key)]
            if not candidates:
                return self._consent_required(
                    provider_id=provider_key,
                    capability=capability_key,
                    message=f"Connect {provider.label or provider.provider_id} and approve {capability_key}.",
                    candidates=tuple(item.account_id for item in accounts),
                )
            if len(candidates) > 1:
                return CapabilityResolution(
                    ok=False,
                    provider_id=provider_key,
                    capability=capability_key,
                    error="account_required",
                    message="Several connected accounts can satisfy this capability; choose an account_id.",
                    candidates=tuple(item.account_id for item in candidates),
                )
            account = candidates[0]

        if not account.connected:
            return self._consent_required(
                provider_id=provider_key,
                capability=capability_key,
                account_id=account.account_id,
                message="The connected account has no usable credential.",
            )
        if not account.allows(capability_key):
            return self._consent_required(
                provider_id=provider_key,
                capability=capability_key,
                account_id=account.account_id,
                message=f"The connected account has not approved {capability_key}.",
            )
        credential = await self.store.get_credential(account.credential_id)
        if not credential:
            return self._consent_required(
                provider_id=provider_key,
                capability=capability_key,
                account_id=account.account_id,
                message="The connected account credential is missing or expired.",
            )
        handle = CredentialHandle(
            provider_id=provider_key,
            account_id=account.account_id,
            credential_id=account.credential_id,
            capabilities=account.capabilities,
            credential=credential,
        )
        return CapabilityResolution(
            ok=True,
            provider_id=provider_key,
            capability=capability_key,
            account_id=account.account_id,
            credential=handle,
        )

    def _consent_required(
        self,
        *,
        provider_id: str,
        capability: str,
        account_id: str = "",
        message: str = "",
        candidates: tuple[str, ...] = (),
    ) -> CapabilityResolution:
        return CapabilityResolution(
            ok=False,
            provider_id=provider_id,
            capability=capability,
            account_id=account_id,
            error="consent_required",
            message=message,
            candidates=candidates,
        )


def broker_for_user(
    *,
    user_id: str,
    config: UserIntegrationsConfig,
    bundle_id: str = "",
    store: UserIntegrationStore | None = None,
) -> UserIntegrationBroker:
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.models import CONNECTION_HUB_BUNDLE_ID

    resolved_store = store or UserIntegrationStore(
        user_id=user_id,
        bundle_id=as_str(bundle_id) or CONNECTION_HUB_BUNDLE_ID,
    )
    return UserIntegrationBroker(config=config, store=resolved_store)


__all__ = ["UserIntegrationBroker", "broker_for_user"]

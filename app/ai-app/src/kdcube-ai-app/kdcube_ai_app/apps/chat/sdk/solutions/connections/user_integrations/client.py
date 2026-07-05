# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Application-facing client for user-connected integrations."""

from __future__ import annotations

from typing import Any

from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.broker import (
    UserIntegrationBroker,
    broker_for_user,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.config import (
    user_integrations_config_from_entrypoint,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.models import (
    CONNECTION_HUB_BUNDLE_ID,
    CapabilityResolution,
    ConnectedAccount,
    UserIntegrationsConfig,
    as_str,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.store import UserIntegrationStore


class UserIntegrationsClient:
    """Small facade applications/tools can use without reading Connection Hub storage."""

    def __init__(self, *, broker: UserIntegrationBroker) -> None:
        self._broker = broker

    @classmethod
    def from_user(
        cls,
        *,
        user_id: str,
        config: UserIntegrationsConfig,
        bundle_id: str = "",
        store: UserIntegrationStore | None = None,
    ) -> "UserIntegrationsClient":
        return cls(broker=broker_for_user(user_id=user_id, config=config, bundle_id=bundle_id, store=store))

    @classmethod
    def from_entrypoint(cls, entrypoint: Any, *, user_id: str, store: UserIntegrationStore | None = None) -> "UserIntegrationsClient":
        config = user_integrations_config_from_entrypoint(entrypoint)
        return cls.from_user(user_id=user_id, config=config, bundle_id=CONNECTION_HUB_BUNDLE_ID, store=store)

    async def catalog(self) -> dict[str, Any]:
        return self._broker.config.to_dict()

    async def list_accounts(self, provider_id: str = "") -> list[ConnectedAccount]:
        return await self._broker.store.list_accounts(provider_id=provider_id)

    async def ensure_capability(
        self,
        *,
        provider_id: str,
        capability: str,
        account_id: str | None = None,
        purpose: str = "",
    ) -> CapabilityResolution:
        return await self._broker.ensure_capability(
            provider_id=provider_id,
            capability=capability,
            account_id=account_id,
            purpose=purpose,
        )

    async def get_credential(self, *, account_id: str, capability: str) -> CapabilityResolution:
        account = await self._broker.store.get_account(account_id)
        if account is None:
            return CapabilityResolution(
                ok=False,
                provider_id="",
                capability=as_str(capability),
                account_id=as_str(account_id),
                error="account_not_found",
                message="Connected account not found.",
            )
        return await self.ensure_capability(
            provider_id=account.provider_id,
            capability=capability,
            account_id=account.account_id,
        )


__all__ = ["UserIntegrationsClient"]

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Connection Hub user-connected integrations SDK."""

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.adapters import (
    UserIntegrationAdapter,
    adapter,
    list_adapters,
    register_adapter,
    resolve_adapter,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.broker import (
    UserIntegrationBroker,
    broker_for_user,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.client import UserIntegrationsClient
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.config import (
    USER_INTEGRATIONS_CONFIG_KEY,
    user_integrations_config,
    user_integrations_config_from_entrypoint,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.models import (
    CONNECTION_HUB_BUNDLE_ID,
    STATUS_CONNECTED,
    STATUS_REVOKED,
    CapabilityResolution,
    ConnectedAccount,
    ConnectorApp,
    CredentialHandle,
    IntegrationProvider,
    ProviderCapability,
    UserIntegrationsConfig,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.oauth import (
    MemoryOAuthStateStore,
    OAuthStateStore,
    RedisOAuthStateStore,
    consume_oauth_state,
    create_oauth_state,
    peek_state_payload,
    sign_state,
    state_digest,
    verify_state,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.operations import (
    UserIntegrationsOperations,
    operations_for_user,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.store import (
    UserIntegrationStore,
    account_id_for,
    credential_id_for,
)

__all__ = [
    "CONNECTION_HUB_BUNDLE_ID",
    "STATUS_CONNECTED",
    "STATUS_REVOKED",
    "USER_INTEGRATIONS_CONFIG_KEY",
    "CapabilityResolution",
    "ConnectedAccount",
    "ConnectorApp",
    "CredentialHandle",
    "IntegrationProvider",
    "MemoryOAuthStateStore",
    "OAuthStateStore",
    "ProviderCapability",
    "RedisOAuthStateStore",
    "UserIntegrationAdapter",
    "UserIntegrationBroker",
    "UserIntegrationStore",
    "UserIntegrationsOperations",
    "UserIntegrationsClient",
    "UserIntegrationsConfig",
    "account_id_for",
    "adapter",
    "broker_for_user",
    "consume_oauth_state",
    "credential_id_for",
    "create_oauth_state",
    "list_adapters",
    "operations_for_user",
    "peek_state_payload",
    "register_adapter",
    "resolve_adapter",
    "sign_state",
    "state_digest",
    "user_integrations_config",
    "user_integrations_config_from_entrypoint",
    "verify_state",
]

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Config helpers for Connection Hub user-connected integrations."""

from __future__ import annotations

from typing import Any, Mapping

from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.models import (
    UserIntegrationsConfig,
    as_dict,
)

USER_INTEGRATIONS_CONFIG_KEY = "user_integrations"


def user_integrations_config(raw: Mapping[str, Any] | None) -> UserIntegrationsConfig:
    """Parse user-integrations config from a Connection Hub config mapping.

    Accepts either the whole Connection Hub config containing `user_integrations`
    or the `user_integrations` submapping itself.
    """
    data = as_dict(raw)
    section = data.get(USER_INTEGRATIONS_CONFIG_KEY) if USER_INTEGRATIONS_CONFIG_KEY in data else data
    return UserIntegrationsConfig.from_config(section)


def user_integrations_config_from_entrypoint(entrypoint: Any) -> UserIntegrationsConfig:
    """Read user-integrations config from an entrypoint's effective bundle props."""
    if entrypoint is None or not hasattr(entrypoint, "bundle_prop"):
        return UserIntegrationsConfig()
    return user_integrations_config(entrypoint.bundle_prop(USER_INTEGRATIONS_CONFIG_KEY, {}) or {})


__all__ = [
    "USER_INTEGRATIONS_CONFIG_KEY",
    "user_integrations_config",
    "user_integrations_config_from_entrypoint",
]

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Config helpers for Connection Hub delegated to KDCube."""

from __future__ import annotations

from typing import Any, Mapping

from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube.models import (
    DelegatedToKdcubeConfig,
    as_dict,
)

CONNECTIONS_CONFIG_KEY = "connections"
DELEGATED_TO_KDCUBE_CONFIG_KEY = "delegated_to_kdcube"


def delegated_to_kdcube_config(raw: Mapping[str, Any] | None) -> DelegatedToKdcubeConfig:
    """Parse delegated-to-kdcube config from a Connection Hub config mapping.

    Accepts the whole Connection Hub config containing
    `connections.delegated_to_kdcube`, a `connections` mapping containing
    `delegated_to_kdcube`, or the `delegated_to_kdcube` submapping itself.
    """
    data = as_dict(raw)
    if DELEGATED_TO_KDCUBE_CONFIG_KEY in data:
        section = data.get(DELEGATED_TO_KDCUBE_CONFIG_KEY)
    else:
        connections = as_dict(data.get(CONNECTIONS_CONFIG_KEY))
        section = (
            connections.get(DELEGATED_TO_KDCUBE_CONFIG_KEY)
            if DELEGATED_TO_KDCUBE_CONFIG_KEY in connections
            else data
        )
    return DelegatedToKdcubeConfig.from_config(section)


def delegated_to_kdcube_config_from_entrypoint(entrypoint: Any) -> DelegatedToKdcubeConfig:
    """Read delegated-to-kdcube config from an entrypoint's effective bundle props."""
    props = getattr(entrypoint, "bundle_props", None)
    if isinstance(props, Mapping):
        return delegated_to_kdcube_config(props)
    if entrypoint is None or not hasattr(entrypoint, "bundle_prop"):
        return DelegatedToKdcubeConfig()
    return delegated_to_kdcube_config(
        {
            CONNECTIONS_CONFIG_KEY: entrypoint.bundle_prop(CONNECTIONS_CONFIG_KEY, {}) or {},
        }
    )


__all__ = [
    "CONNECTIONS_CONFIG_KEY",
    "DELEGATED_TO_KDCUBE_CONFIG_KEY",
    "delegated_to_kdcube_config",
    "delegated_to_kdcube_config_from_entrypoint",
]

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Descriptor-backed Connection Hub authority registry helpers.

This module handles the static descriptor shape:

    authority_registry.authorities.<authority_id>.providers.<provider_id>

`provider_id` is a configured provider instance. `provider.type` is the
implementation type, for example `bundle_session_login` or `telegram_init_data`.
"""

from __future__ import annotations

from typing import Any, Mapping


def _str(value: Any) -> str:
    return str(value or "").strip()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _str(value).lower() in {"1", "true", "yes", "on", "enabled"}


def authority_registry_config(props: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return `authority_registry` from bundle props."""

    raw = _dict(props).get("authority_registry")
    return _dict(raw)


def authority_provider_instances(registry: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Flatten configured authority provider instances.

    Returned rows include normalized `authority_id`, `provider_id`,
    `provider_type`, `platform`, `authority`, and `provider` fields.
    """

    out: list[dict[str, Any]] = []
    authorities = _dict(_dict(registry).get("authorities"))
    for authority_id, authority_raw in authorities.items():
        authority = _dict(authority_raw)
        providers = _dict(authority.get("providers"))
        for provider_id, provider_raw in providers.items():
            provider = _dict(provider_raw)
            if provider.get("enabled") is False:
                continue
            out.append(
                {
                    "authority_id": _str(authority_id),
                    "provider_id": _str(provider_id),
                    "provider_type": _str(provider.get("type")),
                    "platform": _bool(authority.get("platform"), False),
                    "authority": {
                        key: value
                        for key, value in authority.items()
                        if key != "providers"
                    },
                    "provider": {
                        **provider,
                        "id": _str(provider_id),
                        "provider_id": _str(provider_id),
                        "type": _str(provider.get("type")),
                    },
                }
            )
    return out


def resolve_authority_provider_instance(
    registry: Mapping[str, Any] | None,
    *,
    authority_id: str = "",
    provider_id: str = "",
    provider_type: str = "",
    host_bundle_id: str = "",
    host_route: str = "",
    host_operation: str = "",
) -> dict[str, Any]:
    """Resolve one provider instance by id or by hosted operation."""

    wanted_authority = _str(authority_id)
    wanted_provider = _str(provider_id)
    wanted_type = _str(provider_type)
    wanted_bundle = _str(host_bundle_id)
    wanted_route = _str(host_route)
    wanted_operation = _str(host_operation)

    matches: list[dict[str, Any]] = []
    for row in authority_provider_instances(registry):
        if wanted_authority and row["authority_id"] != wanted_authority:
            continue
        if wanted_provider and row["provider_id"] != wanted_provider:
            continue
        if wanted_type and row["provider_type"] != wanted_type:
            continue

        provider = _dict(row.get("provider"))
        host = _dict(provider.get("host"))
        if wanted_bundle and _str(host.get("bundle_id") or host.get("app_id")) != wanted_bundle:
            continue
        if wanted_route and _str(host.get("route")) != wanted_route:
            continue
        if wanted_operation and _str(host.get("operation") or host.get("alias")) != wanted_operation:
            continue
        matches.append(row)

    if not matches:
        return {"ok": False, "error": "authority_provider_not_found"}
    if len(matches) > 1:
        return {
            "ok": False,
            "error": "authority_provider_ambiguous",
            "matches": [
                {
                    "authority_id": item["authority_id"],
                    "provider_id": item["provider_id"],
                    "provider_type": item["provider_type"],
                }
                for item in matches
            ],
        }
    return {"ok": True, **matches[0]}


__all__ = [
    "authority_provider_instances",
    "authority_registry_config",
    "resolve_authority_provider_instance",
]

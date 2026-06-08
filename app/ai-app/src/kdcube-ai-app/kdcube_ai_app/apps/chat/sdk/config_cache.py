# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Iterable

_SECRET_CACHE_TTL_SECONDS = 120.0
_SECRET_VALUE_CACHE: dict[tuple[str, ...], tuple[float, str | None]] = {}
_PLAIN_VALUE_CACHE: dict[tuple[str, int, int, str], Any] = {}


def clear_secret_cache(
    *,
    tenant: str | None = None,
    project: str | None = None,
    bundle_id: str | None = None,
    user_id: str | None = None,
    key: str | None = None,
    keys: Iterable[str] | None = None,
) -> int:
    """Clear central process-local secret lookup cache entries."""
    tenant_filter = str(tenant or "").strip()
    project_filter = str(project or "").strip()
    bundle_filter = str(bundle_id or "").strip()
    user_filter = str(user_id or "").strip()
    key_filter = {str(candidate).strip() for candidate in (keys or []) if str(candidate).strip()}
    if key:
        key_filter.add(str(key).strip())

    if not tenant_filter and not project_filter and not bundle_filter and not user_filter and not key_filter:
        cleared = len(_SECRET_VALUE_CACHE)
        _SECRET_VALUE_CACHE.clear()
        return cleared

    def _provider_matches(cache_key: tuple[str, ...]) -> bool:
        _scope, cache_tenant, cache_project, secret_key = cache_key
        if tenant_filter and cache_tenant != tenant_filter:
            return False
        if project_filter and cache_project != project_filter:
            return False
        if bundle_filter and not secret_key.startswith(f"bundles.{bundle_filter}.secrets."):
            return False
        if user_filter:
            return False
        if key_filter and not bundle_filter and secret_key not in key_filter:
            return False
        return True

    def _user_matches(cache_key: tuple[str, ...]) -> bool:
        _scope, cache_tenant, cache_project, cache_user, cache_bundle, secret_tail = cache_key
        full_key = (
            f"users.{cache_user}.bundles.{cache_bundle}.secrets.{secret_tail}"
            if cache_bundle
            else f"users.{cache_user}.secrets.{secret_tail}"
        )
        if tenant_filter and cache_tenant != tenant_filter:
            return False
        if project_filter and cache_project != project_filter:
            return False
        if bundle_filter and cache_bundle != bundle_filter:
            return False
        if user_filter and cache_user != user_filter:
            return False
        if key_filter and not bundle_filter and not user_filter and secret_tail not in key_filter and full_key not in key_filter:
            return False
        return True

    to_delete: list[tuple[str, ...]] = []
    for cache_key in _SECRET_VALUE_CACHE:
        if not cache_key:
            continue
        if cache_key[0] == "provider" and _provider_matches(cache_key):
            to_delete.append(cache_key)
        elif cache_key[0] == "user" and _user_matches(cache_key):
            to_delete.append(cache_key)
    for cache_key in to_delete:
        _SECRET_VALUE_CACHE.pop(cache_key, None)
    return len(to_delete)


def get_secret_cache(cache_key: tuple[str, ...]) -> tuple[bool, str | None]:
    cached = _SECRET_VALUE_CACHE.get(cache_key)
    if cached is None:
        return False, None
    expires_at, value = cached
    if expires_at > time.monotonic():
        return True, value
    _SECRET_VALUE_CACHE.pop(cache_key, None)
    return False, None


def set_secret_cache(cache_key: tuple[str, ...], value: str | None) -> str | None:
    resolved = value or None
    _SECRET_VALUE_CACHE[cache_key] = (time.monotonic() + _SECRET_CACHE_TTL_SECONDS, resolved)
    return resolved


def clear_plain_cache() -> int:
    cleared = len(_PLAIN_VALUE_CACHE)
    _PLAIN_VALUE_CACHE.clear()
    return cleared


def get_plain_cache(
    *,
    path: str,
    mtime_ns: int,
    size: int,
    dotted_path: str,
    loader: Callable[[], Any],
) -> Any:
    cache_key = (str(path), int(mtime_ns), int(size), str(dotted_path or ""))
    if cache_key in _PLAIN_VALUE_CACHE:
        return _PLAIN_VALUE_CACHE[cache_key]
    value = loader()
    _PLAIN_VALUE_CACHE[cache_key] = value
    return value


def clear_config_cache() -> int:
    return clear_secret_cache() + clear_plain_cache()

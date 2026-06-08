# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import asyncio

import pytest

from kdcube_ai_app.apps.middleware.simple_idp import SimpleIDP
from kdcube_ai_app.apps.middleware.simple_idp_registry import SimpleIDPRegistry
from kdcube_ai_app.auth.AuthManager import AuthenticationError


def _user(username: str) -> dict:
    return {
        "sub": f"sub-{username}",
        "username": username,
        "email": f"{username}@example.test",
        "name": username.title(),
        "roles": ["kdcube:role:chat-user"],
        "permissions": ["kdcube:*:chat:*;read"],
    }


@pytest.mark.asyncio
async def test_running_simple_idp_sees_registered_user_without_recreation(tmp_path):
    registry = SimpleIDPRegistry(
        tmp_path / "idp_users.json",
        default_users={},
        redis_url="",
        cache_ttl_seconds=60,
    )
    idp = SimpleIDP(registry=registry)

    with pytest.raises(AuthenticationError):
        await idp.authenticate("bridge-token")

    await idp.register_user("bridge-token", _user("bridge"))

    user = await idp.authenticate("bridge-token")
    assert user.username == "bridge"
    assert user.email == "bridge@example.test"
    assert user.roles == ["kdcube:role:chat-user"]


@pytest.mark.asyncio
async def test_registry_invalidate_refreshes_cached_external_write(tmp_path):
    path = tmp_path / "idp_users.json"
    reader = SimpleIDPRegistry(path, default_users={}, redis_url="", cache_ttl_seconds=60)
    writer = SimpleIDPRegistry(path, default_users={}, redis_url="", cache_ttl_seconds=60)

    assert await reader.get_user("external-token") is None
    await writer.upsert_user("external-token", _user("external"))

    assert await reader.get_user("external-token") is None
    await reader.invalidate()
    assert (await reader.get_user("external-token"))["username"] == "external"


@pytest.mark.asyncio
async def test_concurrent_file_backed_registrations_preserve_all_users(tmp_path):
    registry = SimpleIDPRegistry(
        tmp_path / "idp_users.json",
        default_users={},
        redis_url="",
        cache_ttl_seconds=60,
    )

    await asyncio.gather(
        *(registry.upsert_user(f"token-{idx}", _user(f"user{idx}")) for idx in range(8))
    )

    users = await registry.load_users(force=True)
    assert sorted(users) == [f"token-{idx}" for idx in range(8)]
    assert users["token-7"]["username"] == "user7"

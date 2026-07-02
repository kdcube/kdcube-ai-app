# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

import pytest

from kdcube_ai_app.auth.AuthManager import (
    AuthManager,
    AuthenticationError,
    REGISTERED_ROLE,
    RequireUser,
    User,
    ensure_platform_registered_role,
)


class _NoRolePlatformAuth(AuthManager):
    async def authenticate(self, token: str) -> User:
        if token != "ok":
            raise AuthenticationError("bad token")
        return User(username="user-1", roles=[], permissions=[])

    async def get_service_token(self) -> str:
        return "service"


def test_ensure_platform_registered_role_adds_baseline_role():
    user = ensure_platform_registered_role(User(username="user-1", roles=[]))

    assert user is not None
    assert user.roles == [REGISTERED_ROLE]


def test_ensure_platform_registered_role_preserves_existing_roles():
    user = ensure_platform_registered_role(
        User(username="admin", roles=["kdcube:role:super-admin"])
    )

    assert user is not None
    assert user.roles == ["kdcube:role:super-admin"]


@pytest.mark.asyncio
async def test_auth_manager_authorization_applies_baseline_platform_role():
    manager = _NoRolePlatformAuth(send_validation_error_details=True)

    user = await manager.authenticate_and_authorize("ok", RequireUser())

    assert user.roles == [REGISTERED_ROLE]

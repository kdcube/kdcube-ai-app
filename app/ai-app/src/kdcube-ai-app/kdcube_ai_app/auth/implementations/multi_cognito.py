# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import jwt

from kdcube_ai_app.auth.AuthManager import AuthManager, AuthenticationError, User
from kdcube_ai_app.auth.implementations.cognito import CognitoAuthManager
from kdcube_ai_app.apps.chat.sdk.config_scopes import CognitoTrustedProviderConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ResolvedProvider:
    alias: str
    issuer: str
    client_id: str
    manager: CognitoAuthManager


def _issuer(*, region: str, user_pool_id: str) -> str:
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"


def _unverified_claims(token: str | None) -> dict[str, Any]:
    if not token:
        raise AuthenticationError("Token is required")
    try:
        return jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
            },
        )
    except Exception as e:
        raise AuthenticationError(f"Token claims could not be decoded: {e}")


def _token_client_id(claims: dict[str, Any]) -> str:
    token_use = str(claims.get("token_use") or "").strip()
    if token_use == "access":
        return str(claims.get("client_id") or "").strip()
    aud = claims.get("aud")
    if isinstance(aud, list):
        return str(aud[0] if aud else "").strip()
    return str(aud or "").strip()


class MultiCognitoAuthManager(AuthManager):
    """Cognito verifier that trusts several configured user-pool/client pairs."""

    def __init__(
        self,
        providers: list[CognitoTrustedProviderConfig],
        *,
        send_validation_error_details: bool = False,
    ):
        super().__init__(send_validation_error_details)
        self._providers: list[_ResolvedProvider] = []
        for provider in providers:
            if (provider.kind or "cognito").lower() != "cognito":
                continue
            issuer = _issuer(region=provider.region, user_pool_id=provider.user_pool_id)
            self._providers.append(
                _ResolvedProvider(
                    alias=provider.alias,
                    issuer=issuer,
                    client_id=provider.app_client_id,
                    manager=CognitoAuthManager.from_values(
                        region=provider.region,
                        pool_id=provider.user_pool_id,
                        client_id=provider.app_client_id,
                        hosted_ui=provider.hosted_ui_domain,
                        provider_alias=provider.alias,
                        send_validation_error_details=send_validation_error_details,
                    ),
                )
            )
        if not self._providers:
            raise RuntimeError("MultiCognitoAuthManager requires at least one trusted Cognito provider")

    @property
    def provider_count(self) -> int:
        return len(self._providers)

    def _select_provider(self, token: str, *, expected_token_use: str | None = None) -> tuple[_ResolvedProvider, dict[str, Any]]:
        claims = _unverified_claims(token)
        token_use = str(claims.get("token_use") or "").strip()
        if expected_token_use and token_use != expected_token_use:
            raise AuthenticationError(f"Expected Cognito {expected_token_use} token")
        issuer = str(claims.get("iss") or "").strip()
        client_id = _token_client_id(claims)
        for provider in self._providers:
            if provider.issuer == issuer and provider.client_id == client_id:
                return provider, claims
        logger.info(
            "Multi-Cognito auth: no provider matched issuer=%s client_id=%s token_use=%s",
            issuer,
            client_id,
            token_use,
        )
        raise AuthenticationError("No trusted Cognito provider matched token issuer/client")

    async def authenticate(self, token: str) -> User:
        provider, _claims = self._select_provider(token)
        user = await provider.manager.authenticate(token)
        return self._stamp_user(user, provider)

    async def authenticate_with_both(self, access_token: str, id_token: Optional[str]) -> User:
        access_provider, access_claims = self._select_provider(access_token, expected_token_use="access")
        selected_id_token = id_token
        if selected_id_token:
            id_provider, id_claims = self._select_provider(selected_id_token, expected_token_use="id")
            if id_provider.alias != access_provider.alias:
                raise AuthenticationError("Access token and ID token came from different identity providers")
            access_sub = access_claims.get("sub")
            id_sub = id_claims.get("sub")
            if access_sub and id_sub and access_sub != id_sub:
                raise AuthenticationError("Token subjects don't match")
        user = await access_provider.manager.authenticate_with_both(access_token, selected_id_token)
        return self._stamp_user(user, access_provider)

    def _stamp_user(self, user: User, provider: _ResolvedProvider) -> User:
        if hasattr(user, "identity_provider"):
            user.identity_provider = provider.alias
        if hasattr(user, "issuer"):
            user.issuer = provider.issuer
        return user

    async def get_service_token(self) -> str:
        raise NotImplementedError("Service tokens are not issued by Cognito User Pools.")

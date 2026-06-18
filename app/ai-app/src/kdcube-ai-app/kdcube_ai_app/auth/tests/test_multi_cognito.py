import base64
import json

import pytest

from kdcube_ai_app.apps.chat.sdk.config_scopes import CognitoTrustedProviderConfig
from kdcube_ai_app.auth.AuthManager import AuthenticationError
from kdcube_ai_app.auth.implementations.cognito import CognitoAuthManager, CognitoUser
from kdcube_ai_app.auth.implementations.multi_cognito import MultiCognitoAuthManager


def _token(payload: dict) -> str:
    def enc(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return f"{enc({'alg': 'none'})}.{enc(payload)}."


def _manager() -> MultiCognitoAuthManager:
    return MultiCognitoAuthManager(
        [
            CognitoTrustedProviderConfig(
                alias="dev",
                region="eu-west-1",
                user_pool_id="dev-pool",
                app_client_id="dev-client",
            ),
            CognitoTrustedProviderConfig(
                alias="demo",
                region="eu-west-1",
                user_pool_id="demo-pool",
                app_client_id="demo-client",
            ),
        ],
        send_validation_error_details=True,
    )


@pytest.mark.asyncio
async def test_multi_cognito_selects_provider_from_access_and_id_claims(monkeypatch):
    async def fake_authenticate_with_both(self, access_token, id_token):
        return CognitoUser(
            sub="user-1",
            username="user@example.com",
            roles=["kdcube:role:chat-user"],
            identity_provider=self.provider_alias,
            issuer=self.oauth_config.OAUTH2_ISSUER,
        )

    monkeypatch.setattr(CognitoAuthManager, "authenticate_with_both", fake_authenticate_with_both)
    manager = _manager()

    access = _token(
        {
            "token_use": "access",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/demo-pool",
            "client_id": "demo-client",
            "sub": "user-1",
        }
    )
    ident = _token(
        {
            "token_use": "id",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/demo-pool",
            "aud": "demo-client",
            "sub": "user-1",
            "email": "user@example.com",
        }
    )

    user = await manager.authenticate_with_both(access, ident)

    assert user.identity_provider == "demo"
    assert user.issuer == "https://cognito-idp.eu-west-1.amazonaws.com/demo-pool"


@pytest.mark.asyncio
async def test_multi_cognito_rejects_access_and_id_from_different_providers(monkeypatch):
    async def fake_authenticate_with_both(self, access_token, id_token):
        raise AssertionError("delegate must not be called on provider mismatch")

    monkeypatch.setattr(CognitoAuthManager, "authenticate_with_both", fake_authenticate_with_both)
    manager = _manager()

    access = _token(
        {
            "token_use": "access",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/demo-pool",
            "client_id": "demo-client",
            "sub": "user-1",
        }
    )
    ident = _token(
        {
            "token_use": "id",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/dev-pool",
            "aud": "dev-client",
            "sub": "user-1",
        }
    )

    with pytest.raises(AuthenticationError, match="different identity providers"):
        await manager.authenticate_with_both(access, ident)


@pytest.mark.asyncio
async def test_multi_cognito_rejects_untrusted_issuer_client_pair():
    manager = _manager()
    access = _token(
        {
            "token_use": "access",
            "iss": "https://cognito-idp.eu-west-1.amazonaws.com/unknown-pool",
            "client_id": "demo-client",
            "sub": "user-1",
        }
    )

    with pytest.raises(AuthenticationError, match="No trusted Cognito provider"):
        await manager.authenticate_with_both(access, None)

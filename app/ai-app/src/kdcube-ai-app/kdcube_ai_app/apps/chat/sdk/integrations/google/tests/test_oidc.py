from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.integrations.google.oidc import (
    GoogleTokenInvalid,
    validate_google_claims,
    verify_google_id_token,
)


CLIENT_ID = "client.apps.googleusercontent.com"


def _claims(**overrides):
    data = {
        "iss": "https://accounts.google.com",
        "sub": "123",
        "aud": CLIENT_ID,
        "email": "USER@example.com",
        "email_verified": "true",
        "name": "User",
        "iat": 100,
        "exp": 200,
    }
    data.update(overrides)
    return data


def test_validate_google_claims_normalizes_trusted_claims():
    out = validate_google_claims(_claims(), client_id=CLIENT_ID, now=150)

    assert out["sub"] == "123"
    assert out["email"] == "user@example.com"
    assert out["email_verified"] is True


def test_validate_google_claims_rejects_wrong_audience():
    with pytest.raises(GoogleTokenInvalid, match="bad_audience"):
        validate_google_claims(_claims(aud="other"), client_id=CLIENT_ID, now=150)


def test_validate_google_claims_rejects_expired_token():
    with pytest.raises(GoogleTokenInvalid, match="expired"):
        validate_google_claims(_claims(exp=149), client_id=CLIENT_ID, now=150)


def test_verify_google_id_token_accepts_injected_decoder():
    def decoder(token: str, *, client_id: str, jwks_url: str):
        assert token == "token"
        assert client_id == CLIENT_ID
        assert jwks_url
        return _claims()

    out = verify_google_id_token("token", client_id=CLIENT_ID, now=150, decoder=decoder)

    assert out["sub"] == "123"


def test_verify_google_id_token_requires_client_id():
    with pytest.raises(GoogleTokenInvalid, match="client_id_required"):
        verify_google_id_token("token", client_id="")

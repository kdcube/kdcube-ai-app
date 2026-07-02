from __future__ import annotations

import time
from typing import Any, Callable, Mapping

import jwt
from jwt import PyJWKClient

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ACCOUNTS_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleTokenInvalid(ValueError):
    """Raised when a Google ID token cannot be trusted."""


def _str(value: Any) -> str:
    return str(value or "").strip()


def _client_id_matches(audience: Any, client_id: str) -> bool:
    wanted = _str(client_id)
    if not wanted:
        return False
    if isinstance(audience, str):
        return audience == wanted
    if isinstance(audience, (list, tuple, set)):
        return wanted in {_str(item) for item in audience}
    return False


def validate_google_claims(
    claims: Mapping[str, Any],
    *,
    client_id: str,
    now: int | None = None,
) -> dict[str, Any]:
    """Validate Google ID-token claims and return a normalized copy."""

    if not isinstance(claims, Mapping):
        raise GoogleTokenInvalid("google_id_token_claims_required")

    issuer = _str(claims.get("iss"))
    if issuer not in GOOGLE_ACCOUNTS_ISSUERS:
        raise GoogleTokenInvalid("google_id_token_bad_issuer")

    if not _client_id_matches(claims.get("aud"), client_id):
        raise GoogleTokenInvalid("google_id_token_bad_audience")

    subject = _str(claims.get("sub"))
    if not subject:
        raise GoogleTokenInvalid("google_id_token_subject_required")

    current = int(now if now is not None else time.time())
    try:
        expires_at = int(claims.get("exp") or 0)
    except Exception as exc:
        raise GoogleTokenInvalid("google_id_token_bad_exp") from exc
    if expires_at <= current:
        raise GoogleTokenInvalid("google_id_token_expired")

    issued_at_raw = claims.get("iat")
    if issued_at_raw is not None:
        try:
            issued_at = int(issued_at_raw)
        except Exception as exc:
            raise GoogleTokenInvalid("google_id_token_bad_iat") from exc
        if issued_at > current + 300:
            raise GoogleTokenInvalid("google_id_token_iat_in_future")

    email = _str(claims.get("email")).lower()
    email_verified = claims.get("email_verified")
    if isinstance(email_verified, str):
        email_verified = email_verified.lower() == "true"

    normalized = dict(claims)
    normalized["iss"] = issuer
    normalized["sub"] = subject
    normalized["email"] = email
    normalized["email_verified"] = bool(email_verified)
    normalized["name"] = _str(claims.get("name"))
    normalized["picture"] = _str(claims.get("picture"))
    normalized["aud"] = claims.get("aud")
    return normalized


def _decode_google_jwt(
    credential: str,
    *,
    client_id: str,
    jwks_url: str,
) -> dict[str, Any]:
    signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(credential)
    return jwt.decode(
        credential,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        options={"require": ["iss", "sub", "aud", "exp"]},
    )


def verify_google_id_token(
    credential: str,
    *,
    client_id: str,
    jwks_url: str = GOOGLE_JWKS_URL,
    now: int | None = None,
    decoder: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify a Google ID token and return normalized claims.

    `decoder` is injectable so unit tests can exercise validation without a
    network call to Google's JWKS endpoint.
    """

    token = _str(credential)
    wanted_client = _str(client_id)
    if not token:
        raise GoogleTokenInvalid("google_id_token_required")
    if not wanted_client:
        raise GoogleTokenInvalid("google_client_id_required")
    try:
        decode_fn = decoder or _decode_google_jwt
        claims = decode_fn(token, client_id=wanted_client, jwks_url=jwks_url)
    except GoogleTokenInvalid:
        raise
    except Exception as exc:
        raise GoogleTokenInvalid("google_id_token_verify_failed") from exc
    return validate_google_claims(claims, client_id=wanted_client, now=now)


__all__ = [
    "GOOGLE_ACCOUNTS_ISSUERS",
    "GOOGLE_JWKS_URL",
    "GoogleTokenInvalid",
    "validate_google_claims",
    "verify_google_id_token",
]

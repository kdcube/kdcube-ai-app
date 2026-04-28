# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from kdcube_ai_app.apps.chat.sdk.config import get_settings

router = APIRouter()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_placeholder(value: str | None) -> bool:
    raw = _text(value).strip("'\"")
    if not raw:
        return True
    lowered = raw.lower()
    if raw.upper() in {"TENANT_ID", "PROJECT_ID"}:
        return True
    if "<" in raw and ">" in raw:
        return True
    if "__set_" in lowered or "changeme" in lowered:
        return True
    return False


def _normalized_route_prefix(value: Any, default: str = "/chatbot") -> str:
    raw = _text(value) or default
    if raw == "/":
        return ""
    return "/" + raw.strip("/")


def _frontend_auth(settings: Any) -> dict[str, Any]:
    auth_mode = _text(settings.plain("auth.type")).lower()
    auth_provider = _text(getattr(settings, "AUTH_PROVIDER", "")).lower()
    company = _text(settings.plain("company")) or "KDCube"
    auth_cfg = getattr(settings, "AUTH", None)
    id_token_header = _text(getattr(auth_cfg, "ID_TOKEN_HEADER_NAME", "")) or "X-ID-Token"

    if auth_mode == "delegated":
        auth = {
            "authType": "delegated",
            "idTokenHeaderName": id_token_header,
            "totpAppName": _text(settings.plain("frontend.auth.totp_app_name")) or company,
            "totpIssuer": _text(settings.plain("frontend.auth.totp_issuer")) or company,
            "apiBase": _text(settings.plain("frontend.auth.api_base")) or "/auth/",
        }
    elif auth_mode == "cognito" or auth_provider == "cognito":
        region = _text(getattr(auth_cfg, "COGNITO_REGION", ""))
        user_pool_id = _text(getattr(auth_cfg, "COGNITO_USER_POOL_ID", ""))
        client_id = _text(getattr(auth_cfg, "COGNITO_APP_CLIENT_ID", ""))
        auth = {
            "authType": "oauth",
            "idTokenHeaderName": id_token_header,
            "oidcConfig": {
                "authority": (
                    f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
                    if region and user_pool_id
                    else ""
                ),
                "client_id": client_id,
            },
        }
    else:
        auth = {
            "authType": "hardcoded",
            "token": _text(settings.plain("frontend.auth.token")) or "test-admin-token-123",
        }

    turnstile_development_token = _text(settings.plain("auth.turnstile_development_token"))
    if not _is_placeholder(turnstile_development_token):
        auth["turnstileDevelopmentToken"] = turnstile_development_token

    return auth


def build_frontend_config() -> dict[str, Any]:
    settings = get_settings()
    payload: dict[str, Any] = {
        "auth": _frontend_auth(settings),
        "tenant": settings.TENANT,
        "project": settings.PROJECT,
        "routesPrefix": _normalized_route_prefix(settings.plain("proxy.route_prefix")),
    }

    api_base = _text(settings.plain("frontend.api_base"))
    if api_base:
        payload["apiBase"] = api_base

    support_email = _text(settings.plain("frontend.support_email"))
    if support_email:
        payload["supportEmail"] = support_email

    registration_bundle_id = _text(
        settings.plain("frontend.user_registration_bundle_id")
        or settings.plain("frontend.userRegistrationBundleId")
    )
    if registration_bundle_id:
        payload["userRegistrationBundleId"] = registration_bundle_id

    debug = settings.plain("frontend.debug")
    if isinstance(debug, dict) and debug:
        payload["debug"] = debug

    return payload


@router.get("/api/cp-frontend-config")
async def cp_frontend_config() -> JSONResponse:
    return JSONResponse(
        content=build_frontend_config(),
        headers={"Cache-Control": "no-store, no-cache"},
    )

from __future__ import annotations

import logging
from typing import Any, Mapping

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from kdcube_ai_app.apps.chat.sdk.config import get_settings
from kdcube_ai_app.apps.chat.sdk.integrations.telegram import widget_auth as telegram_widget_auth
from kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry_client import AuthorityRegistryClient
from kdcube_ai_app.auth.bundle import get_bundle_session_authority

log = logging.getLogger("kdcube.bundle.versatile.platform_session_issuer")


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item or "").strip() for item in value if str(item or "").strip()]


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _required_positive_int(config: Mapping[str, Any], key: str) -> int:
    try:
        value = int(config.get(key) or 0)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Authority provider issuer {key} must be an integer") from exc
    if value <= 0:
        raise HTTPException(status_code=500, detail=f"Authority provider issuer {key} must be positive")
    return value


async def _provider_for_host(entrypoint: Any, *, bundle_id: str) -> dict[str, Any]:
    result = await AuthorityRegistryClient(entrypoint).resolve_provider(
        provider_type="bundle_session_login",
        host_bundle_id=bundle_id,
        host_route="public",
        host_operation="auth_telegram_session",
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=500,
            detail=f"Connection Hub authority provider is not registered: {result.get('error') or 'not_found'}",
        )
    if not bool(result.get("platform")):
        raise HTTPException(status_code=500, detail="Registered authority provider is not platform-capable")
    provider = _dict(result.get("provider"))
    host = _dict(provider.get("host"))
    if str(host.get("bundle_id") or "").strip() != bundle_id:
        raise HTTPException(status_code=500, detail="Registered authority provider host does not match this bundle")
    return result


async def issue_telegram_session(
    entrypoint: Any,
    *,
    request: Any = None,
    telegram_init_data: str = "",
    payload: Mapping[str, Any] | None = None,
    bundle_id: str,
):
    del payload
    registry_provider = await _provider_for_host(entrypoint, bundle_id=bundle_id)
    provider_cfg = _dict(registry_provider.get("provider"))
    input_cfg = _dict(provider_cfg.get("input"))
    input_authenticator_ref = _dict(input_cfg.get("authenticator_ref"))
    issuer_cfg = _dict(provider_cfg.get("issuer"))
    grants_cfg = _dict(provider_cfg.get("grants"))

    provider = "telegram"
    authority_id = str(registry_provider.get("authority_id") or "").strip()
    provider_id = str(registry_provider.get("provider_id") or "").strip()
    integration_id = str(input_authenticator_ref.get("integration_id") or input_authenticator_ref.get("provider_id") or "").strip()
    ttl_seconds = _required_positive_int(issuer_cfg, "ttl_seconds")
    roles = _as_str_list(grants_cfg.get("roles"))
    if not roles:
        raise HTTPException(status_code=500, detail="Authority provider grants.roles are not configured")
    permissions = _as_str_list(grants_cfg.get("permissions"))

    identity = await telegram_widget_auth.resolve_identity(
        entrypoint,
        request=request,
        telegram_init_data=telegram_init_data,
        integration_id=integration_id,
        allowed_roles=(),
        create_if_missing=True,
    )
    provider_subject = str(identity.telegram_user_id or "").strip()
    if not provider_subject:
        raise HTTPException(status_code=401, detail="Telegram user id is required")

    username = str(identity.telegram_username or "").strip() or f"telegram_{provider_subject}"
    name = (
        str(identity.user.get("first_name") or "").strip()
        or str(identity.user.get("last_name") or "").strip()
        or username
    )
    sub = f"{provider}:{provider_subject}"
    grant = await get_bundle_session_authority().login_or_register(
        sub=sub,
        username=username,
        name=name,
        roles=roles,
        permissions=permissions,
        provider=provider,
        provider_subject=provider_subject,
        metadata={
            "issued_by_bundle_id": bundle_id,
            "source": "versatile.auth_telegram_session",
            "authority_id": authority_id,
            "authority_provider_id": provider_id,
            "integration_id": integration_id,
            "telegram_user_id": provider_subject,
            "telegram_username": username,
        },
        ttl_seconds=ttl_seconds,
    )

    auth_cfg = get_settings().AUTH
    cookie_cfg = dict(issuer_cfg.get("cookie") or {})
    secure = bool(cookie_cfg.get("secure", True))
    samesite = str(cookie_cfg.get("same_site") or cookie_cfg.get("samesite") or "lax").strip() or "lax"
    response = JSONResponse(
        {
            "ok": True,
            "auth_surface": "bundle_session",
            "issuer_bundle_id": bundle_id,
            "authority_id": authority_id,
            "authority_provider_id": provider_id,
            "provider": provider,
            "provider_subject": provider_subject,
            "sub": sub,
            "session_id": grant.session_id,
            "expires_at": grant.expires_at,
            "roles": roles,
            "permissions": permissions,
        }
    )
    for cookie_name in {
        str(auth_cfg.AUTH_TOKEN_COOKIE_NAME or "").strip(),
        str(auth_cfg.ID_TOKEN_COOKIE_NAME or "").strip(),
    }:
        if not cookie_name:
            continue
        response.set_cookie(
            cookie_name,
            grant.token,
            path="/",
            secure=secure,
            httponly=True,
            samesite=samesite,
        )
    log.info(
        "[platform_session_issuer] issued authority=%s authority_provider=%s provider=%s provider_subject=%s sub=%s roles=%s session_id=%s",
        authority_id,
        provider_id,
        provider,
        provider_subject,
        sub,
        roles,
        grant.session_id,
    )
    return response

"""Connection Hub identity-family resolver.

This module answers a different question than request authentication:

    "Given the current actor/platform user, which linked identities belong to
    the same person for product-level aggregation?"

The first consumer is user memories: a linked Telegram actor should be able to
see memories created under both the Telegram actor id and the platform user id,
without every app reimplementing provider-specific parsing.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry import CredentialEnvelope

from kdcube_ai_app.apps.chat.sdk.solutions.connections.hub.edges import (
    ConnectionEdgeStore,
    edge_actor,
    edge_target,
)


IDENTITY_SCOPE_GRANTOR = "grantor"
IDENTITY_SCOPE_GRANTOR_FAMILY = "grantor_identity_family"
IDENTITY_SCOPE_SELECTED_IDENTITIES = "selected_identities"
DEFAULT_DELEGATED_IDENTITY_SCOPE = IDENTITY_SCOPE_GRANTOR
PLATFORM_AUTHORITY_ID = "platform"
DELEGATED_ECONOMICS_AUTHORITY_ID = PLATFORM_AUTHORITY_ID
IDENTITY_FAMILY_GRANT = "identity:family"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in (_clean(part) for part in value.replace(",", " ").split()) if item]
    if isinstance(value, (list, tuple, set)):
        return [item for item in (_clean(part) for part in value) if item]
    return []


def _safe_optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _clean(value).lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return None


def _identity_ref(provider: str, subject: str) -> str:
    provider = _clean(provider)
    subject = _clean(subject)
    return f"{provider}:{subject}" if provider and subject else ""


def normalize_delegated_identity_scope(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"family", "identity_family", "grantor_family", "grantor_identity_family"}:
        return IDENTITY_SCOPE_GRANTOR_FAMILY
    if text in {"selected", "selected_identity", "selected_identities"}:
        return IDENTITY_SCOPE_SELECTED_IDENTITIES
    if text in {"", "grantor", "owner", "primary"}:
        return IDENTITY_SCOPE_GRANTOR
    return IDENTITY_SCOPE_GRANTOR


def actor_user_id_for_identity(provider: str, subject: str, *, metadata: Optional[Mapping[str, Any]] = None) -> str:
    """Return the canonical runtime actor user id for a provider identity.

    Telegram actors are already standardized in KDCube runtime as
    ``telegram_<id>``. For generic future providers, use the provider-subject
    ref form (`provider:subject`) until that provider registers a stronger
    convention.
    """

    provider = _clean(provider).lower()
    subject = _clean(subject)
    meta = _safe_mapping(metadata)
    explicit = _clean(meta.get("actor_user_id") or meta.get("user_id"))
    if explicit:
        return explicit
    if provider == "telegram" and subject:
        return f"telegram_{subject}"
    return _identity_ref(provider, subject)


def parse_actor_user_id(user_id: str) -> dict[str, str]:
    """Best-effort parse of a runtime user id into provider identity fields."""

    text = _clean(user_id)
    if not text:
        return {}
    if text.startswith("telegram_") and len(text) > len("telegram_"):
        return {
            "provider": "telegram",
            "provider_subject": text[len("telegram_"):],
            "identity_ref": _identity_ref("telegram", text[len("telegram_"):]),
        }
    if ":" in text:
        provider, subject = text.split(":", 1)
        provider = _clean(provider).lower()
        subject = _clean(subject)
        if provider and subject:
            return {
                "provider": provider,
                "provider_subject": subject,
                "identity_ref": _identity_ref(provider, subject),
            }
    return {}


def _edge_metadata(edge: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _safe_mapping(edge.get("metadata"))
    return {
        "source": _clean(metadata.get("source")),
        "authority_id": _clean(metadata.get("authority_id")),
        "integration_id": _clean(metadata.get("connection_id") or metadata.get("integration_id")),
        "authenticator_id": _clean(metadata.get("selected_authenticator") or metadata.get("authenticator_id")),
    }


def _identity_from_edge(edge: Mapping[str, Any]) -> dict[str, Any]:
    source = edge_actor(edge)
    target = edge_target(edge)
    provider = _clean(source.get("provider")).lower()
    subject = _clean(source.get("subject"))
    metadata = _edge_metadata(edge)
    user_id = _clean(source.get("user_id")) or actor_user_id_for_identity(provider, subject, metadata=edge.get("metadata"))
    return {
        "kind": "integration",
        "provider": provider,
        "provider_subject": subject,
        "identity_ref": _clean(source.get("identity_ref")) or _identity_ref(provider, subject),
        "user_id": user_id,
        "authority_id": metadata.get("authority_id") or "",
        "integration_id": metadata.get("integration_id") or "",
        "authenticator_id": metadata.get("authenticator_id") or "",
        "platform_user_id": _clean(target.get("user_id")),
        "label": _clean(edge.get("label")) or _clean(source.get("label")) or subject,
        "status": _clean(edge.get("status")) or "active",
        "source": metadata.get("source") or "connection_edge",
        "edge_id": _clean(edge.get("edge_id")),
        "grants": _safe_list(edge.get("grants")),
    }


def _platform_identity(platform_user_id: str) -> dict[str, Any]:
    user = _clean(platform_user_id)
    return {
        "kind": "authority",
        "authority_id": "platform",
        "provider": "platform",
        "provider_subject": user,
        "identity_ref": _identity_ref("platform", user),
        "user_id": user,
        "platform_user_id": user,
        "label": "KDCube platform user",
        "status": "linked",
        "source": "platform",
    }


def _dedupe_user_ids(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        user_id = _clean(value)
        if user_id and user_id not in seen:
            seen.add(user_id)
            out.append(user_id)
    return out


def _delegated_provenance(envelope: CredentialEnvelope, *, grantor_user_id: str, identity_scope: str) -> dict[str, Any]:
    attrs = _safe_mapping(envelope.attrs)
    return {
        "schema": "connection_hub.delegated_actor_provenance.v1",
        "actor_identity": _clean(envelope.subject),
        "delegate_identity": _clean(envelope.subject),
        "grantor_user_id": grantor_user_id,
        "credential_id": _clean(envelope.credential_id),
        "credential_kind": _clean(envelope.credential_kind),
        "issuer_authority_id": _clean(envelope.issuer_authority_id),
        "issuer_authenticator_id": _clean(envelope.issuer_authenticator_id),
        "client_id": _clean(attrs.get("client_id")),
        "resource": _clean(attrs.get("resource")),
        "grants": _safe_list(attrs.get("scopes") or attrs.get("grants")),
        "tools": _safe_list(attrs.get("tools")),
        "identity_scope": identity_scope,
    }


def _delegated_economics_projection(
    envelope: CredentialEnvelope,
    *,
    grantor_user_id: str,
    identity_scope: str,
    grantor_authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    attrs = _safe_mapping(envelope.attrs)
    authority = _safe_mapping(grantor_authority)
    roles = _safe_list(authority.get("grantor_roles") or authority.get("platform_roles") or authority.get("roles"))
    permissions = _safe_list(
        authority.get("grantor_permissions")
        or authority.get("platform_permissions")
        or authority.get("permissions")
    )
    budget_bypass = _safe_optional_bool(
        authority.get("economics_budget_bypass")
        if "economics_budget_bypass" in authority
        else authority.get("budget_bypass")
    )
    out = {
        "schema": "connection_hub.economics_projection.v1",
        "authority_id": DELEGATED_ECONOMICS_AUTHORITY_ID,
        "user_id": grantor_user_id,
        "subject_user_id": grantor_user_id,
        "source": "delegation_edge",
        "charge_to": "grantor",
        "actor_identity": _clean(envelope.subject),
        "grantor_user_id": grantor_user_id,
        "provenance": _delegated_provenance(
            envelope,
            grantor_user_id=grantor_user_id,
            identity_scope=identity_scope,
        ),
    }
    if roles:
        out["roles"] = roles
    if permissions:
        out["permissions"] = permissions
    if budget_bypass is not None:
        out["budget_bypass"] = budget_bypass
    return {
        key: value for key, value in out.items() if value not in ("", None, [], {})
    }


def delegated_primary_user_id(credential: CredentialEnvelope | Mapping[str, Any] | None) -> str:
    """Return the data-owner identity for a delegated credential.

    Delegated clients are representatives, not the grantor identity itself. The
    primary user for product data is therefore the grantor recorded on the
    delegation edge. If a future credential kind has no grantor, fall back to
    the credential subject so callers remain fail-closed to their own actor.
    """

    envelope = CredentialEnvelope.coerce(credential)
    attrs = _safe_mapping(envelope.attrs)
    return _clean(attrs.get("grantor_subject") or attrs.get("grantor_user_id") or envelope.subject)


def _delegation_identity(envelope: CredentialEnvelope, *, grantor_user_id: str, identity_scope: str) -> dict[str, Any]:
    attrs = _safe_mapping(envelope.attrs)
    return {
        "schema": "connection_hub.delegation_edge.v1",
        "delegate_identity": _clean(envelope.subject),
        "grantor_user_id": grantor_user_id,
        "authority_id": _clean(envelope.issuer_authority_id),
        "authenticator_id": _clean(envelope.issuer_authenticator_id),
        "credential_kind": _clean(envelope.credential_kind),
        "client_id": _clean(attrs.get("client_id")),
        "resource": _clean(attrs.get("resource")),
        "grants": _safe_list(attrs.get("scopes") or attrs.get("grants")),
        "tools": _safe_list(attrs.get("tools")),
        "identity_scope": identity_scope,
        "selected_identity_refs": _safe_list(attrs.get("selected_identity_refs")),
    }


def resolve_delegated_authority_projection(
    *,
    credential: CredentialEnvelope | Mapping[str, Any],
    grantor_authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve authority/economics projection for a delegated credential.

    Delegated-client tokens represent the external client as actor. KDCube
    economics are still platform-owned, so the currently supported projection
    charges the grantor platform user while keeping delegate provenance explicit.
    Future custom authorities can extend this shape without changing consumers.
    """

    envelope = CredentialEnvelope.coerce(credential)
    attrs = _safe_mapping(envelope.attrs)
    grantor_user_id = delegated_primary_user_id(envelope)
    identity_scope = normalize_delegated_identity_scope(attrs.get("identity_scope"))
    delegation = _delegation_identity(envelope, grantor_user_id=grantor_user_id, identity_scope=identity_scope)

    if not grantor_user_id:
        return {
            "ok": False,
            "schema": "connection_hub.delegated_authority_projection.v1",
            "error": "delegated_authority_projection_missing_grantor",
            "delegation": delegation,
        }

    economics = _delegated_economics_projection(
        envelope,
        grantor_user_id=grantor_user_id,
        identity_scope=identity_scope,
        grantor_authority=grantor_authority,
    )
    return {
        "ok": True,
        "schema": "connection_hub.delegated_authority_projection.v1",
        "delegate_identity": delegation["delegate_identity"],
        "actor_identity": delegation["delegate_identity"],
        "grantor_user_id": grantor_user_id,
        "authority_projections": [
            {
                "authority_id": PLATFORM_AUTHORITY_ID,
                "identity_ref": _identity_ref(PLATFORM_AUTHORITY_ID, grantor_user_id),
                "user_id": grantor_user_id,
                "purposes": ["grantor", "economics"],
                "source": "delegation_edge",
            }
        ],
        "economics": economics,
        "provenance": economics["provenance"],
        "delegation": delegation,
    }


def resolve_delegated_identity_scope(
    store: ConnectionEdgeStore,
    *,
    credential: CredentialEnvelope | Mapping[str, Any],
    grantor_authority: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the data-owner scope allowed by a delegated credential.

    This answers the question product surfaces need:

        "Given a delegated external-client identity, which user ids may this
        request read for this consented resource?"

    The credential subject remains the delegate actor. The grantor and
    identity-scope fields define whether reads stay on the grantor only or may
    expand to the grantor's linked identity family.
    """

    envelope = CredentialEnvelope.coerce(credential)
    attrs = _safe_mapping(envelope.attrs)
    grantor_user_id = delegated_primary_user_id(envelope)
    identity_scope = normalize_delegated_identity_scope(attrs.get("identity_scope"))
    delegation = _delegation_identity(envelope, grantor_user_id=grantor_user_id, identity_scope=identity_scope)
    projection = resolve_delegated_authority_projection(
        credential=envelope,
        grantor_authority=grantor_authority,
    )

    if not grantor_user_id:
        return {
            "ok": False,
            "schema": "connection_hub.delegated_identity_scope.v1",
            "error": "delegated_identity_scope_missing_grantor",
            "delegation": delegation,
        }

    if identity_scope in {IDENTITY_SCOPE_GRANTOR_FAMILY, IDENTITY_SCOPE_SELECTED_IDENTITIES}:
        family = resolve_identity_family(
            store,
            input_user_id=grantor_user_id,
            actor_user_id=grantor_user_id,
            platform_user_id=grantor_user_id,
        )
        identities = list(family.get("identities") or [])
        memory_user_ids = list(family.get("memory_user_ids") or family.get("user_ids") or [])
        if identity_scope == IDENTITY_SCOPE_SELECTED_IDENTITIES:
            selected = {
                _clean(value)
                for value in _safe_list(attrs.get("selected_identity_refs") or attrs.get("selected_user_ids"))
                if _clean(value)
            }
            if selected:
                identities = [
                    item for item in identities
                    if _clean(item.get("identity_ref")) in selected or _clean(item.get("user_id")) in selected
                ]
                memory_user_ids = [
                    _clean(item.get("user_id"))
                    for item in identities
                    if _clean(item.get("user_id"))
                ]
        memory_user_ids = _dedupe_user_ids([grantor_user_id] + memory_user_ids)
    else:
        identities = [_platform_identity(grantor_user_id)]
        memory_user_ids = [grantor_user_id]

    return {
        "ok": True,
        "schema": "connection_hub.delegated_identity_scope.v1",
        "delegation": delegation,
        "delegate_identity": delegation["delegate_identity"],
        "grantor_user_id": grantor_user_id,
        "identity_scope": identity_scope,
        "identities": identities,
        "user_ids": list(memory_user_ids),
        "memory_user_ids": list(memory_user_ids),
        "authority_projections": list(projection.get("authority_projections") or []),
        "economics": _safe_mapping(projection.get("economics")),
        "provenance": _safe_mapping(projection.get("provenance")),
    }


def resolve_identity_family(
    store: ConnectionEdgeStore,
    *,
    input_user_id: str = "",
    actor_user_id: str = "",
    platform_user_id: str = "",
) -> dict[str, Any]:
    """Resolve the linked identity family for a platform or actor user id."""

    requested_user_id = _clean(input_user_id or actor_user_id or platform_user_id)
    current_actor = _clean(actor_user_id or requested_user_id)
    current_platform = _clean(platform_user_id)
    parsed = parse_actor_user_id(requested_user_id)
    requested_edge: dict[str, Any] = {}

    family_platform_user_id = current_platform
    if parsed:
        edge = store.resolve_edge(
            from_provider=parsed.get("provider", ""),
            from_subject=parsed.get("provider_subject", ""),
        )
        requested_edge = _safe_mapping(edge)
        edge_grants = set(_safe_list(requested_edge.get("grants")))
        family_platform_user_id = (
            (_clean(edge_target(requested_edge).get("user_id")) or family_platform_user_id)
            if IDENTITY_FAMILY_GRANT in edge_grants
            else ""
        )
    elif requested_user_id and requested_user_id != "anonymous":
        family_platform_user_id = requested_user_id

    identities: list[dict[str, Any]] = []
    if family_platform_user_id:
        identities.append(_platform_identity(family_platform_user_id))
        for edge in store.list_edges(target_user_id=family_platform_user_id):
            identities.append(_identity_from_edge(edge))
    elif parsed:
        identities.append({
            "kind": "integration",
            "provider": parsed.get("provider", ""),
            "provider_subject": parsed.get("provider_subject", ""),
            "identity_ref": parsed.get("identity_ref", ""),
            "user_id": actor_user_id_for_identity(parsed.get("provider", ""), parsed.get("provider_subject", "")),
            "platform_user_id": "",
            "label": parsed.get("provider_subject", ""),
            "status": "unlinked",
            "source": "actor_user_id",
        })

    user_ids = _dedupe_user_ids([_clean(identity.get("user_id")) for identity in identities])

    return {
        "ok": True,
        "schema": "connection_hub.identity_family.v1",
        "input": {
            "user_id": requested_user_id,
            "actor_user_id": current_actor,
            "platform_user_id": current_platform,
            **({"provider": parsed.get("provider", ""), "provider_subject": parsed.get("provider_subject", "")} if parsed else {}),
        },
        "linked": bool(family_platform_user_id),
        "platform_user_id": family_platform_user_id,
        "authority": _platform_identity(family_platform_user_id) if family_platform_user_id else {},
        "identities": identities,
        "user_ids": user_ids,
        "memory_user_ids": list(user_ids),
        "requested_connection_edge": requested_edge,
    }


__all__ = [
    "DEFAULT_DELEGATED_IDENTITY_SCOPE",
    "IDENTITY_SCOPE_GRANTOR",
    "IDENTITY_SCOPE_GRANTOR_FAMILY",
    "IDENTITY_SCOPE_SELECTED_IDENTITIES",
    "actor_user_id_for_identity",
    "delegated_primary_user_id",
    "normalize_delegated_identity_scope",
    "parse_actor_user_id",
    "resolve_delegated_authority_projection",
    "resolve_delegated_identity_scope",
    "resolve_identity_family",
]

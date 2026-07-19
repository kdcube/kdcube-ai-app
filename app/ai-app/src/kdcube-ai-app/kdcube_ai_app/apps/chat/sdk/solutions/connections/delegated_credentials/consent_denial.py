# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The consent breakdown ANY KDCube-served MCP surface returns on a per-agent
grant miss.

A surface guarded by the delegated-client boundary denies an operation whose
grants the caller's bearer lacks. The denial is a CONTRACT, uniform across
surfaces: it names the exact missing grants, and for a hosted-agent caller
(`kdcube-agent:<app>:<agent>`) it carries the full consent block — agent
identity, the granted resource, the claims, and the one-click
`delegated_agent_grant_create` action — so the caller's chat surface raises
the scoped demand without knowing anything about the specific service. The
agent identity and resource come from the REQUEST's own bound credential
(the grant record's client id, or the delegate subject; the credential's
granted resource), so every surface answers identically with one call.

External OAuth clients (Claude Code) keep the reconnect / incremental-consent
guidance instead — their consent loop is the OAuth journey, not a chat banner.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

LOGGER = logging.getLogger(__name__)

AGENT_CLIENT_PREFIX = "kdcube-agent:"
CONSENT_NEEDED_CODE = "connections.consent_needed"
DELEGATED_CONSENT_REQUIRED = "delegated_consent_required"


def _grant_record(request: Any) -> Mapping[str, Any]:
    delegated = getattr(getattr(request, "state", None), "delegated_credential", None)
    if not isinstance(delegated, Mapping):
        return {}
    record = delegated.get("grant_record")
    return record if isinstance(record, Mapping) else {}


def _credential(request: Any) -> Mapping[str, Any]:
    delegated = getattr(getattr(request, "state", None), "delegated_credential", None)
    if not isinstance(delegated, Mapping):
        return {}
    credential = delegated.get("credential")
    return credential if isinstance(credential, Mapping) else {}


def agent_client_id_from_request(request: Any) -> str:
    """The caller's ``kdcube-agent:<app>:<agent>`` identity, or "".

    The grant record's ``client_id`` is authoritative; a projection without it
    still names the agent in the delegate subject
    (``integration:kdcube-agent:<app>:<agent>:<user>``)."""
    record = _grant_record(request)
    client_id = str(record.get("client_id") or "").strip()
    if client_id.startswith(AGENT_CLIENT_PREFIX):
        return client_id
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry import (
        CredentialEnvelope,
    )

    subject = str(CredentialEnvelope.coerce(_credential(request)).subject or "")
    parts = subject.split(":")
    if len(parts) >= 4 and parts[0] == "integration" and parts[1] == AGENT_CLIENT_PREFIX.rstrip(":"):
        return ":".join(parts[1:4])
    return ""


def granted_resource_from_request(request: Any) -> str:
    """The delegated-resource id this bearer was granted under, or "".

    An OAuth client carries a single ``attrs.resource``; an agent client carries
    a ``resource_grants`` map (one key per delegated resource — for the
    named-services door, the single door resource that covers every namespace).
    Read both, in the credential envelope AND the token-bound grant record."""
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry import (
        CredentialEnvelope,
    )

    def _from_attrs(attrs: Mapping[str, Any]) -> str:
        resource = str(attrs.get("resource") or "").strip()
        if resource:
            return resource
        grants = attrs.get("resource_grants")
        if isinstance(grants, Mapping) and grants:
            return str(next(iter(grants.keys())) or "").strip()
        return ""

    # 1. The credential envelope (where an agent bearer stores resource_grants).
    resource = _from_attrs(CredentialEnvelope.coerce(_credential(request)).attrs or {})
    if resource:
        return resource
    # 2. The grant record, top level and via its embedded credential.
    record = _grant_record(request)
    grants = record.get("resource_grants")
    if isinstance(grants, Mapping) and grants:
        return str(next(iter(grants.keys())) or "").strip()
    nested = record.get("credential")
    if isinstance(nested, Mapping):
        return _from_attrs(CredentialEnvelope.coerce(nested).attrs or {})
    return ""


def connection_hub_grant_url(
    *,
    tenant: str,
    project: str,
    client_id: str,
    resource: str,
    claims: Sequence[str],
    hub_bundle_id: str = "connection-hub@1-0",
) -> str:
    """An absolute Connection Hub deep link that lands on the Delegated by
    KDCube tab with THIS client's access request focused (the pending pane:
    missing claims pre-checked, one-click grant).

    Openable outside the app origin — an external agent (Claude Code) relays
    it verbatim; the user signs in with their platform credentials and sees the
    focused card. Empty when the deployment's public base URL is unknown."""
    from urllib.parse import quote, urlencode

    from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube.public_base import (
        connection_hub_public_base_url,
    )

    base = connection_hub_public_base_url()
    if not base or not tenant or not project or not client_id or not resource:
        return ""
    params = urlencode({
        "tab": "delegated_by_kdcube",
        "pending_agent_grant": "1",
        "agent_client_id": client_id,
        "resource": resource,
        "claims": ",".join(str(c) for c in claims if str(c or "").strip()),
    })
    return (
        f"{base}/api/integrations/bundles/"
        f"{quote(str(tenant), safe='')}/{quote(str(project), safe='')}/"
        f"{quote(hub_bundle_id, safe='')}/widgets/connections_settings?{params}"
    )


def agent_grant_consent_denial(
    request: Any,
    *,
    namespace: str,
    tool: str,
    operation: str,
    required: Sequence[str],
    missing: Sequence[str],
    available: Sequence[str],
    message: str = "",
    tenant: str = "",
    project: str = "",
) -> dict[str, Any]:
    """The uniform per-agent grant denial for a KDCube-served MCP surface.

    Always names the exact grants; a hosted-agent caller additionally gets the
    full consent block + Connection Hub next step, other client families get
    the reconnect guidance."""
    missing_list = sorted({str(c) for c in missing if str(c or "").strip()})
    denial: dict[str, Any] = {
        "ok": False,
        "error": DELEGATED_CONSENT_REQUIRED,
        "message": message or (
            f"'{tool}' on '{namespace}' requires additional delegated consent."
        ),
        "namespace": namespace,
        "tool": tool,
        "operation": operation,
        "required_grants": sorted({str(c) for c in required if str(c or "").strip()}),
        "missing_grants": missing_list,
        "available_grants": sorted({str(c) for c in available if str(c or "").strip()}),
        "next_step": (
            "Reconnect this MCP resource and approve the missing grant if the "
            "client supports incremental consent. Otherwise connect a resource "
            "whose initial consent includes this grant."
        ),
    }
    client_id = agent_client_id_from_request(request)
    external_client_id = ""
    if not client_id:
        # Any OTHER delegated client (an external app connected via OAuth —
        # Claude Code) gets the SAME focused path: the hub deep link below
        # lands on its card with the missing claims pre-checked.
        external_client_id = str(_grant_record(request).get("client_id") or "").strip()
    resource = granted_resource_from_request(request)
    hub_url = connection_hub_grant_url(
        tenant=tenant,
        project=project,
        client_id=client_id or external_client_id,
        resource=resource,
        claims=missing_list,
    )
    if not client_id and not external_client_id:
        LOGGER.info(
            "[agent-consent-denial] caller carries no delegated client identity; "
            "reconnect guidance kept (namespace=%s tool=%s)",
            namespace, tool,
        )
        return denial
    denial["code"] = CONSENT_NEEDED_CODE
    consent: dict[str, Any] = {
        "kind": "delegated_agent_grant",
        "reason": DELEGATED_CONSENT_REQUIRED,
        "agent_client_id": client_id or external_client_id,
        "resource": resource,
        "claims": missing_list,
        "tool_name": namespace,
    }
    if hub_url:
        consent["connection_hub_url"] = hub_url
        denial["connection_hub_url"] = hub_url
    if client_id:
        # The one-click grant action rides only for hosted agents today; an
        # external client's approval flows through the hub link (its record
        # extension is the hub's own operation).
        consent["grant"] = {
            "operation": "delegated_agent_grant_create",
            "payload": {"client_id": client_id, "resource": resource, "claims": missing_list},
        }
        denial["next_step"] = (
            "The user extends this agent's grant with the missing access in "
            "Connection Hub (Delegated by KDCube); the chat consent card carries "
            "the one-click grant."
        )
    else:
        denial["next_step"] = (
            "Give the user this link: they sign in with their platform account "
            "and approve the missing access for this client in Connection Hub "
            "(Delegated by KDCube). Reconnecting with incremental consent also "
            "works when this client supports it."
            if hub_url
            else denial["next_step"]
        )
        denial["instructions"] = (
            f"Ask the user to open {hub_url} and approve: {', '.join(missing_list)}. "
            "Then retry the same call."
        ) if hub_url else denial.get("instructions", "")
    denial["consent"] = consent
    if not resource:
        LOGGER.warning(
            "[agent-consent-denial] consent block has NO resource (client=%s namespace=%s) — "
            "the caller must fill it from its connection declaration",
            client_id or external_client_id, namespace,
        )
    return denial


__all__ = [
    "agent_client_id_from_request",
    "agent_grant_consent_denial",
    "granted_resource_from_request",
    "CONSENT_NEEDED_CODE",
    "DELEGATED_CONSENT_REQUIRED",
]

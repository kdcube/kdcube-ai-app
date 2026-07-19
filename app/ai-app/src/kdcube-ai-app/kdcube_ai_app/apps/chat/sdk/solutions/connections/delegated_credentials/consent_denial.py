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
    """The delegated-resource id this bearer was granted under, or ""."""
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.authority_registry import (
        CredentialEnvelope,
    )

    attrs = CredentialEnvelope.coerce(_credential(request)).attrs or {}
    resource = str(attrs.get("resource") or "").strip()
    if resource:
        return resource
    resource_grants = _grant_record(request).get("resource_grants")
    if isinstance(resource_grants, Mapping) and resource_grants:
        return str(next(iter(resource_grants.keys())) or "")
    return ""


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
    if not client_id:
        LOGGER.info(
            "[agent-consent-denial] caller is not a kdcube-agent; reconnect guidance kept "
            "(namespace=%s tool=%s)",
            namespace, tool,
        )
        return denial
    resource = granted_resource_from_request(request)
    denial["code"] = CONSENT_NEEDED_CODE
    denial["consent"] = {
        "kind": "delegated_agent_grant",
        "reason": DELEGATED_CONSENT_REQUIRED,
        "agent_client_id": client_id,
        "resource": resource,
        "claims": missing_list,
        "tool_name": namespace,
        "grant": {
            "operation": "delegated_agent_grant_create",
            "payload": {"client_id": client_id, "resource": resource, "claims": missing_list},
        },
    }
    denial["next_step"] = (
        "The user extends this agent's grant with the missing access in "
        "Connection Hub (Delegated by KDCube); the chat consent card carries "
        "the one-click grant."
    )
    if not resource:
        LOGGER.warning(
            "[agent-consent-denial] consent block has NO resource (client=%s namespace=%s) — "
            "the caller must fill it from its connection declaration",
            client_id, namespace,
        )
    return denial


__all__ = [
    "agent_client_id_from_request",
    "agent_grant_consent_denial",
    "granted_resource_from_request",
    "CONSENT_NEEDED_CODE",
    "DELEGATED_CONSENT_REQUIRED",
]

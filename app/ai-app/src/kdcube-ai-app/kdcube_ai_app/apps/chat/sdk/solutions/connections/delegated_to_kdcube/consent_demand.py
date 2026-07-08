# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Demand-driven consent bookkeeping.

Which tools a turn needs only becomes clear as the agent works, so consent
raises at the ATTEMPT: the tool invocation that hits an unmet claim records a
consent demand here and the chat renders the scoped banner. The record is one
small user-prop per user+bundle holding the LAST conversation's pending
demands — the next turn's transition check reads it, resolves ONLY those
tools' claims, and announces the ones the user satisfied
(``[CONNECTED ACCOUNTS UPDATE]``). Transition detection matters within one
conversation, so a new conversation simply overwrites the record.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger("kdcube.connections.delegated_to_kdcube")

# One record per user+bundle: {"conversation_id": …, "providers": [group…]}
# where a group is {provider_id, provider_label?, connector_app_id?, claims,
# tools} — the same shape the ANNOUNCE composer reads.
PENDING_CONSENT_KEY = "delegated_to_kdcube.blocked_snapshot"


def read_pending_consent(*, user_id: str, bundle_id: str, conversation_id: str) -> list:
    """The conversation's pending consent-demand groups (empty otherwise)."""
    if not user_id or not bundle_id or not conversation_id:
        return []
    try:
        from kdcube_ai_app.apps.chat.sdk import config as sdk_config

        raw = sdk_config.get_user_prop(
            PENDING_CONSENT_KEY, user_id=user_id, bundle_id=bundle_id, default=None,
        )
    except Exception:
        return []
    if not isinstance(raw, dict) or str(raw.get("conversation_id") or "") != conversation_id:
        return []
    providers = raw.get("providers")
    return [g for g in providers if isinstance(g, dict)] if isinstance(providers, list) else []


def write_pending_consent(*, user_id: str, bundle_id: str, conversation_id: str, providers: list) -> None:
    if not user_id or not bundle_id or not conversation_id:
        return
    try:
        from kdcube_ai_app.apps.chat.sdk import config as sdk_config

        if providers:
            sdk_config.set_user_prop(
                PENDING_CONSENT_KEY,
                {"conversation_id": conversation_id, "providers": providers},
                user_id=user_id,
                bundle_id=bundle_id,
            )
        else:
            sdk_config.delete_user_prop(PENDING_CONSENT_KEY, user_id=user_id, bundle_id=bundle_id)
    except Exception:
        LOGGER.debug("pending-consent write unavailable", exc_info=True)


def record_consent_demand(
    *,
    user_id: str,
    bundle_id: str,
    conversation_id: str,
    provider_id: str,
    connector_app_id: str = "",
    provider_label: str = "",
    claims: list | tuple = (),
    tool_name: str = "",
) -> bool:
    """Record one attempted tool's consent demand.

    Returns True when this (provider, claims, tool) is NEW for the
    conversation — the caller emits the chat consent event exactly once per
    demand; retries of the same tool in the same conversation stay quiet
    server-side (the banner reducer's signature dedupe covers client replays).
    """
    provider_key = str(provider_id or "").strip()
    tool_key = str(tool_name or "").strip()
    claim_list = [str(c).strip() for c in (claims or []) if str(c or "").strip()]
    if not provider_key or not tool_key:
        return False
    pending = read_pending_consent(user_id=user_id, bundle_id=bundle_id, conversation_id=conversation_id)
    for group in pending:
        if str(group.get("provider_id") or "") != provider_key:
            continue
        known_tools = {str(t) for t in (group.get("tools") or [])}
        known_claims = {str(c) for c in (group.get("claims") or [])}
        if tool_key in known_tools and set(claim_list) <= known_claims:
            return False
        group["tools"] = sorted(known_tools | {tool_key})
        group["claims"] = sorted(known_claims | set(claim_list))
        if provider_label and not group.get("provider_label"):
            group["provider_label"] = provider_label
        write_pending_consent(
            user_id=user_id, bundle_id=bundle_id, conversation_id=conversation_id, providers=pending,
        )
        return True
    pending.append({
        "provider_id": provider_key,
        "provider_label": str(provider_label or "").strip(),
        "connector_app_id": str(connector_app_id or "").strip(),
        "claims": sorted(set(claim_list)),
        "tools": [tool_key],
    })
    write_pending_consent(
        user_id=user_id, bundle_id=bundle_id, conversation_id=conversation_id, providers=pending,
    )
    return True


async def announce_consent_demand(
    *,
    comm: Any = None,
    payload: Any,
    provider_id: str,
    connector_app_id: str = "",
    claims: list | tuple = (),
    tool_name: str = "",
    identity: Any = None,
) -> bool:
    """Record one attempted tool's consent demand and emit the scoped chat
    consent event ONCE per (provider, claims, tool) demand per conversation.

    ``tool_name`` is the entry as the user sees it in the composer menu
    (``alias.tool`` for python tools, the bare namespace for named-service
    tools) — the banner's turn-off spotlight targets exactly that. Identity
    (user / bundle / conversation) comes from the bound request context;
    ``comm`` defaults to the context communicator. Best-effort: never raises.
    """
    try:
        from kdcube_ai_app.apps.chat.sdk.runtime.comm_ctx import (
            get_comm,
            get_current_user_identity,
        )

        if identity is None:
            identity = get_current_user_identity() or {}
        user_id = str(identity.get("user_id") or "").strip()
        bundle_id = str(identity.get("bundle_id") or "").strip()
        conversation_id = str(identity.get("conversation_id") or "").strip()
        provider_key = str(provider_id or "").strip()
        newly_recorded = record_consent_demand(
            user_id=user_id,
            bundle_id=bundle_id,
            conversation_id=conversation_id,
            provider_id=provider_key,
            connector_app_id=str(connector_app_id or "").strip(),
            provider_label=(provider_key[:1].upper() + provider_key[1:]) if provider_key else "",
            claims=list(claims or []),
            tool_name=str(tool_name or "").strip(),
        )
        if not newly_recorded:
            return False
        communicator = comm if comm is not None else get_comm()
        event = getattr(communicator, "event", None) if communicator is not None else None
        if not callable(event):
            return False
        result = event(
            agent="connection-hub",
            type="chat.step",
            route="chat.step",
            title="Account consent needed",
            step="delegated_to_kdcube.consent",
            data=dict(payload or {}),
            status="completed",
            broadcast=False,
        )
        if hasattr(result, "__await__"):
            await result
        return True
    except Exception:
        LOGGER.debug("consent demand announce unavailable", exc_info=True)
        return False


async def claim_coverage_for_policies(
    *,
    user_id: str,
    policies: list,
    connection_hub_bundle_id: str = "",
) -> dict:
    """READ-ONLY per-tool claim coverage for a picker UI.

    Answers "which of this tool's declared claims does the user's connected
    account set already hold" from the account records alone — zero credential
    reads, zero consent events, zero health probes (a menu render must ask
    nothing). A claim counts covered when ANY connected account of the
    requirement's provider (and connector app, when named) holds it; the
    consent plan and the tool attempt stay the authorities on health and
    account choice.

    Returns {tool_name: {provider_id, connector_app_id, claims, unmet,
    covered}} for every policy carrying connected-account requirements.
    """
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube.models import (
        CONNECTION_HUB_BUNDLE_ID,
    )
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube.store import (
        DelegatedToKdcubeStore,
    )

    clean_user = str(user_id or "").strip()
    coverage: dict = {}
    if not clean_user:
        return coverage
    store = DelegatedToKdcubeStore(
        user_id=clean_user,
        bundle_id=str(connection_hub_bundle_id or "").strip() or CONNECTION_HUB_BUNDLE_ID,
    )
    try:
        accounts = await store.list_accounts()
    except Exception:
        LOGGER.debug("claim coverage account read unavailable", exc_info=True)
        return coverage
    for policy in policies or []:
        tool_name = str(getattr(policy, "tool_name", "") or "").strip()
        requirements = list(getattr(policy, "connected_accounts", ()) or ())
        if not tool_name or not requirements:
            continue
        declared: list = []
        unmet: list = []
        provider_id = ""
        connector_app_id = ""
        for requirement in requirements:
            provider_id = provider_id or str(getattr(requirement, "provider_id", "") or "")
            connector_app_id = connector_app_id or str(getattr(requirement, "connector_app_id", "") or "")
            req_provider = str(getattr(requirement, "provider_id", "") or "")
            req_connector = str(getattr(requirement, "connector_app_id", "") or "")
            eligible = [
                account for account in accounts
                if account.provider_id == req_provider
                and account.connected
                and (not req_connector or not account.connector_app_id or account.connector_app_id == req_connector)
            ]
            for claim in getattr(requirement, "claims", ()) or ():
                claim_key = str(claim or "").strip()
                if not claim_key or claim_key in declared:
                    continue
                declared.append(claim_key)
                if not any(account.allows(claim_key) for account in eligible):
                    unmet.append(claim_key)
        coverage[tool_name] = {
            "provider_id": provider_id,
            "connector_app_id": connector_app_id,
            "claims": declared,
            "unmet": unmet,
            "covered": not unmet,
        }
    return coverage


def pending_consent_delta(previous: list, current: list) -> list:
    """Provider groups whose tools left the pending set (consent satisfied)."""
    pending_now: dict = {}
    for group in current or []:
        if isinstance(group, dict):
            key = str(group.get("provider_id") or "")
            pending_now.setdefault(key, set()).update(
                str(t) for t in (group.get("tools") or []) if str(t or "").strip()
            )
    satisfied: list = []
    for group in previous or []:
        if not isinstance(group, dict):
            continue
        key = str(group.get("provider_id") or "")
        freed = [
            str(t) for t in (group.get("tools") or [])
            if str(t or "").strip() and str(t) not in pending_now.get(key, set())
        ]
        if freed:
            satisfied.append({**group, "tools": freed})
    return satisfied

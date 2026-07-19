# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# ── tools_mcp.py ── the "tools, both ways" seam (thin over the SDK) ──
#
# The preserved agent binds PLAIN LangChain tools (solution/tools.py) — "bring your
# own tools", external to the host and, running no accounted model calls, unmetered.
# This module adds the SECOND way: bind a KDCube-served MCP endpoint's tools as
# LangChain tools.
#
# The mechanism is now SHARED SDK, reused by any hosted LangGraph/LangChain agent:
#   - `solutions/connections/delegated_mcp.resolve_mcp_server_map` — framework-neutral:
#     turn the agent's `kind: mcp` connections into an MCP server map, minting a
#     per-user DELEGATED bearer for any connection marked `delegated: true` (the same
#     `@mcp`-surface auth platform bundles use) and injecting it; static connections
#     keep their declared headers.
#   - `frameworks/langchain/mcp.load_mcp_tools_from_server_map` — bind that map as
#     LangChain tools via `langchain-mcp-adapters` (degrades to none when absent).
#
# This bundle file is the thin adapter: pass the agent's connection list + this
# turn's user, get LangChain tools.
#
# ACCOUNTING (the honest rule — "marked = counted"): binding a tool via MCP does not
# by itself make it accounted; a tool whose KDCube-side implementation runs a marked
# model call IS metered, a plain lookup is not.

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Mapping, Optional

from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_mcp import (
    resolve_mcp_server_map,
    delegated_client_id_for_agent,
    is_delegated_connection,
    connection_resource,
    DROP_CONSENT_PENDING,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.mcp_consent import (
    MCPConsentRequired,
    mcp_consent_from_denial,
)
from kdcube_ai_app.apps.chat.sdk.frameworks.langchain.mcp import (
    load_mcp_server_instructions,
    load_mcp_tools_from_server_map,
    load_error_looks_like_denial,
    mcp_adapters_available,  # re-exported for callers/tests
)

logger = logging.getLogger(__name__)

__all__ = [
    "mcp_connections",
    "load_mcp_tools_for_connections",
    "consent_request_tools",
    "mcp_adapters_available",
    "wrap_tools_with_user_delivery",
]


def consent_request_tools(
    consents: List[MCPConsentRequired],
    *,
    announce: Any,
) -> List[Any]:
    """One consent-gated STUB tool per pending delegated connection.

    Consent is demand-driven per tool: a turn's build cannot know which
    capabilities the turn will use, so a pending connection must NOT raise a
    turn-start demand. Instead it binds a stub carrying the connection's name
    and claims; when the MODEL decides the user's request needs that
    capability, calling the stub raises exactly that connection's consent
    demand in chat (via ``announce``) and returns the agent-explainable consent
    result — the same attempt-time semantics connected-account tools have.
    Once the user grants, the next build binds the real tools and the stub
    disappears. Returns ``[]`` when LangChain is unavailable."""
    try:
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field
    except Exception:  # pragma: no cover - langchain-less environments
        return []

    class _ConsentRequestArgs(BaseModel):
        reason: str = Field(
            default="",
            description="One line on what the user asked for that needs this capability.",
        )

    tools: List[Any] = []
    for c in consents:
        alias = str((getattr(c, "consent", {}) or {}).get("tool_name") or "").strip() or "restricted_capability"
        claims = ", ".join(getattr(c, "claims", []) or []) or "the required access"

        async def _request(reason: str = "", _consent: MCPConsentRequired = c) -> Dict[str, Any]:
            del reason
            try:
                await announce(_consent)
            except Exception:
                logger.info("consent stub: announce failed (non-fatal)", exc_info=True)
            return _consent.to_tool_result()

        tools.append(StructuredTool.from_function(
            coroutine=_request,
            name=alias,
            description=(
                f"{alias}: this capability needs the user's consent to {claims}. "
                "Call it when the user's request needs this capability — the call "
                "raises a consent request in chat for the user to approve and "
                "returns the consent status. After the user grants, the real "
                f"{alias} tools become available on the next turn."
            ),
            args_schema=_ConsentRequestArgs,
        ))
    return tools


def _conn_alias(conn: Mapping[str, Any]) -> str:
    return str(conn.get("alias") or conn.get("name") or "").strip()


_POSTPROCESS_MARKERS = ('"download"', '"delegated_consent_required"', '"consent"')


def _postprocessable(text: str) -> Any | None:
    """Parse an MCP tool's text content when it can carry a file delivery or a
    consent denial."""
    raw = str(text or "").strip()
    if not raw.startswith("{") or not any(marker in raw for marker in _POSTPROCESS_MARKERS):
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _consent_result(
    parsed: Dict[str, Any],
    *,
    agent_client_id: str,
    fallback_resource: str,
    resource_candidates: Optional[List[Mapping[str, Any]]] = None,
) -> Dict[str, Any] | None:
    """When a door result is a per-agent consent denial, raise the chat consent
    demand and return the agent-explainable consent result; None otherwise.

    The door (a KDCube @mcp named-services surface) denies an op whose grants
    the agent's consented bearer lacks with `delegated_consent_required` and —
    for hosted-agent callers — a full consent block (agent identity, resource,
    missing claims, one-click grant action). The tool result alone reaches only
    the model; announcing turns it into the standard scoped banner, so the user
    sees exactly what is asked (e.g. mail:read) with the one-click grant, and
    the Connection Hub landing offers the pending-claims pane."""
    if str(parsed.get("error") or "") != "delegated_consent_required":
        return None
    block = parsed.get("consent") if isinstance(parsed.get("consent"), Mapping) else {}
    claims = [str(c) for c in (block.get("claims") or parsed.get("missing_grants") or []) if str(c or "").strip()]
    if not claims:
        logger.warning("[mcp-wrap] consent denial with NO claims — cannot announce: %s", parsed)
        return None
    client_id = str(block.get("agent_client_id") or agent_client_id or "").strip()
    resource = str(
        block.get("resource")
        or fallback_resource
        or _resource_for_claims(claims, list(resource_candidates or []))
        or ""
    ).strip()
    if not client_id or not resource:
        logger.warning(
            "[mcp-wrap] consent denial not announceable: client=%r resource=%r claims=%s "
            "(block=%s fallback_resource=%r)",
            client_id, resource, claims, dict(block or {}), fallback_resource,
        )
        return None
    logger.info(
        "[mcp-wrap] consent denial -> announcing demand: client=%s resource=%s claims=%s tool=%s",
        client_id, resource, claims, str(block.get("tool_name") or parsed.get("namespace") or ""),
    )
    from kdcube_ai_app.apps.chat.sdk.solutions.connections.mcp_consent import (
        announce_agent_consent,
    )

    consent = mcp_consent_from_denial(
        {"status": 403, "reason": "authority_mismatch"},
        resource=resource,
        claims=claims,
        tool_name=str(block.get("tool_name") or parsed.get("namespace") or ""),
        agent_client_id=client_id,
    )
    await announce_agent_consent(consent)
    return consent.to_tool_result()


def _resource_for_claims(
    claims: List[str],
    candidates: List[Mapping[str, Any]],
) -> str:
    """The declared delegated connection whose scopes cover the denial's claims.

    With several delegated connections the single-connection fallback cannot
    decide; the connection that DECLARED the missing claims in its scopes is
    the one whose resource the grant rides. Anything beyond that is the
    SERVER's to say: every KDCube-served MCP surface names its own resource in
    the denial's consent block, and that block always wins over this
    fallback."""
    matches = [
        str(c.get("resource") or "")
        for c in candidates
        if set(claims) <= {str(s) for s in (c.get("scopes") or [])}
    ]
    return matches[0] if len(matches) == 1 else ""


def wrap_tools_with_user_delivery(
    tools: List[Any],
    *,
    agent_client_id: str = "",
    fallback_resource: str = "",
    resource_candidates: Optional[List[Mapping[str, Any]]] = None,
) -> List[Any]:
    """Post-process MCP tool results for the chat surface, both directions.

    * File deliveries go to the USER: a result carrying a file object with an
      out-of-band download URL (the turn-less contract) becomes a chat file
      card (object ref, click-time resolution); the model-visible result keeps
      a delivery note in place of the URL — a signed link the model would
      otherwise re-type into its message, corrupting it some fraction of the
      time.
    * Consent denials go to the USER too: a door op denied for missing
      per-agent grants raises the scoped chat consent banner (the missing
      claims + one-click grant), and the model gets the explainable consent
      result instead of a bare error.

    Mutates each tool's coroutine in place; tools without one pass through."""
    from kdcube_ai_app.apps.chat.sdk.solutions.widgets.send_to_user import (
        deliver_result_files,
    )

    async def _process_dict(parsed: Dict[str, Any]) -> Dict[str, Any] | None:
        consent = await _consent_result(
            parsed,
            agent_client_id=agent_client_id,
            fallback_resource=fallback_resource,
            resource_candidates=resource_candidates,
        )
        if consent is not None:
            return consent
        delivered = await deliver_result_files(parsed)
        return delivered if delivered is not parsed else None

    async def _process_text(text: str) -> str | None:
        parsed = _postprocessable(text)
        if parsed is None:
            return None
        replaced = await _process_dict(parsed)
        return json.dumps(replaced, ensure_ascii=False) if replaced is not None else None

    async def _process_content(content: Any) -> Any | None:
        # langchain-mcp-adapters tools are `content_and_artifact`: content is a
        # STRING (single text block) or a LIST of content blocks
        # ({"type": "text", "text": ...}); plain dict/str cover direct callers.
        if isinstance(content, str):
            return await _process_text(content)
        if isinstance(content, dict):
            return await _process_dict(content)
        if isinstance(content, list):
            changed = False
            out: List[Any] = []
            for item in content:
                replacement = None
                if isinstance(item, str):
                    replacement = await _process_text(item)
                elif isinstance(item, Mapping) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    new_text = await _process_text(item["text"])
                    if new_text is not None:
                        replacement = {**item, "text": new_text}
                if replacement is not None:
                    out.append(replacement)
                    changed = True
                else:
                    out.append(item)
            return out if changed else None
        return None

    def _unprocessed_sentinel(result: Any) -> None:
        # The silent-failure guard: a result that CARRIES a consent denial or a
        # download URL but was not post-processed means the user saw nothing —
        # no banner, no file card. That must never be quiet. (A result without
        # the markers is the normal case and stays unlogged.)
        raw = repr(result)
        for marker in ("delegated_consent_required", "download_token"):
            if marker in raw:
                logger.warning(
                    "mcp tool result carries %r but was NOT post-processed "
                    "(unhandled shape %s) — no banner/file card reached the user",
                    marker, type(result).__name__,
                )
                return

    def _wrap(orig: Any) -> Any:
        async def run(*args: Any, **kwargs: Any) -> Any:
            result = await orig(*args, **kwargs)
            try:
                if isinstance(result, tuple) and len(result) == 2:
                    replaced = await _process_content(result[0])
                    if replaced is not None:
                        return (replaced, result[1])
                else:
                    replaced = await _process_content(result)
                    if replaced is not None:
                        return replaced
                _unprocessed_sentinel(result)
            except Exception:  # pragma: no cover - post-processing is best-effort
                logger.warning("mcp tool result post-process failed (non-fatal)", exc_info=True)
            return result

        return run

    wrapped = 0
    for tool in tools or []:
        orig = getattr(tool, "coroutine", None)
        if callable(orig):
            try:
                tool.coroutine = _wrap(orig)
                wrapped += 1
            except Exception:
                logger.info("mcp tool %s: delivery wrap failed (non-fatal)", getattr(tool, "name", "?"))
        else:
            logger.warning(
                "[mcp-wrap] tool %s has no coroutine — consent/delivery post-processing will NOT run for it",
                getattr(tool, "name", "?"),
            )
    if tools:
        logger.info(
            "[mcp-wrap] %d/%d tools wrapped for consent+delivery post-processing (client=%s fallback_resource=%r)",
            wrapped, len(tools), agent_client_id, fallback_resource,
        )
    return tools


def mcp_connections(
    connections: List[Dict[str, Any]],
    disabled_map: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """The `kind: mcp` entries of the agent's declared tool-connection list, minus
    any the user opted OUT of this turn (whole-tool opt-out `{alias: true}` from the
    capabilities picker deny-map) — the same admin-ceiling ∩ user-enabled narrowing
    the plain/code-exec tools get, so MCP tools are governed too ("which agent")."""
    disabled = disabled_map or {}
    out: List[Dict[str, Any]] = []
    for c in connections or []:
        if not (isinstance(c, dict) and str(c.get("kind") or "").strip().lower() == "mcp"):
            continue
        if disabled.get(_conn_alias(c)) is True:
            continue
        out.append(c)
    return out


async def load_mcp_tools_for_connections(
    connections: List[Dict[str, Any]],
    *,
    user_sub: Optional[str] = None,
    disabled_map: Optional[Mapping[str, Any]] = None,
    application: str = "",
    agent_id: str = "",
    bearer_provider: Optional[Any] = None,
    instructions_sink: Optional[Dict[str, str]] = None,
) -> tuple[List[Any], List[MCPConsentRequired]]:
    """Bind the agent's declared, user-enabled `kind: mcp` connections as LangChain
    tools for THIS turn's user, AS this agent.

    The agent is a "Delegated By KDCube" entity keyed by `application` + `agent_id`,
    so consent is per-agent. When ``bearer_provider`` is supplied (the recommended
    path), a delegated connection uses the token the user's per-agent grant already
    bound — so the KDCube `@mcp` guard passes; a connection with NO consented grant
    is dropped and surfaces as a consent demand. Without a provider the resolver
    falls back to a fresh mint (unbound → the guard denies until consent exists),
    which still yields the same consent demand.

    Returns ``(tools, consent_demands)``: when a KDCube `@mcp` load is denied for
    missing consent (a 403 at connect time), the tools are absent and a
    ``MCPConsentRequired`` is returned for each delegated connection so the caller
    can bubble it into chat and explain it to the agent. Never raises."""
    conns = mcp_connections(connections, disabled_map)
    if not conns:
        return [], []
    client_id = delegated_client_id_for_agent(application, agent_id)
    drop_sink: Dict[str, str] = {}
    server_map = await resolve_mcp_server_map(
        conns, user_sub=user_sub, client_id=client_id, bearer_provider=bearer_provider,
        drop_sink=drop_sink,
    )
    error_sink: Dict[str, Any] = {}
    tools = await load_mcp_tools_from_server_map(server_map, error_sink=error_sink)
    # The fallback resource for in-result consent denials: with ONE delegated
    # connection its resource id is authoritative; with several, the door's own
    # consent block names it, or the candidate whose declared scopes cover the
    # denial's claims decides (memories vs the named-services door).
    delegated_conns = [c for c in conns if is_delegated_connection(c)]
    tools = wrap_tools_with_user_delivery(
        tools,
        agent_client_id=client_id,
        fallback_resource=connection_resource(delegated_conns[0]) if len(delegated_conns) == 1 else "",
        resource_candidates=[
            {
                "resource": connection_resource(c),
                "scopes": (c.get("scopes") or c.get("claims") or []),
            }
            for c in delegated_conns
        ],
    )

    # An MCP server may publish an operating guide in its initialize result —
    # what MCP-native clients (e.g. Claude connectors) show their model. The
    # LangChain tool loader drops it, so recover it here for the system prompt.
    # Only when tools actually loaded (a consent-denied door would just 403).
    if instructions_sink is not None and tools:
        try:
            instructions_sink.update(await load_mcp_server_instructions(server_map))
        except Exception:
            logger.info("mcp server-instructions fetch failed (non-fatal)", exc_info=True)

    # A delegated connection the user hasn't granted THIS agent surfaces as a
    # consent demand, whichever way the block manifested:
    #   * dropped BEFORE any server contact (the consented-token path returned no
    #     bearer -> DROP_CONSENT_PENDING in drop_sink) — no transport error exists;
    #   * denied AT connect time (an unbound bearer met the @mcp guard's 403).
    load_error = error_sink.get("_load_error")
    denied_at_load = load_error is not None and load_error_looks_like_denial(load_error) and not tools
    consents: List[MCPConsentRequired] = []
    for c in conns:
        if not is_delegated_connection(c):
            continue
        server_id = str(c.get("server_id") or c.get("server") or c.get("name") or "").strip()
        dropped_pending = drop_sink.get(server_id) == DROP_CONSENT_PENDING
        if not dropped_pending and not (denied_at_load and server_id in server_map):
            continue
        claims = c.get("scopes") or c.get("claims") or []
        if isinstance(claims, str):
            claims = [claims]
        consents.append(mcp_consent_from_denial(
            {"status": 403, "reason": "authority_mismatch"},
            # The connection's declared delegated-resource id (its `resource`,
            # falling back to the url) — the SAME key the grant is created and
            # looked up under. A deployment whose configured resource is a
            # wildcard pattern declares it via `resource`, so the demand's
            # one-click grant validates against the catalog.
            resource=connection_resource(c),
            claims=claims,
            tool_name=str(c.get("alias") or c.get("name") or ""),
            agent_client_id=client_id,
        ))
    return tools, consents

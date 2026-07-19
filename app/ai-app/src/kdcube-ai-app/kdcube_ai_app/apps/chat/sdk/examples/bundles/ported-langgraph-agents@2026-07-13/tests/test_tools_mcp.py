"""The "tools, both ways" seam (platform/tools_mcp.py) — thin over the SDK.

The mechanism moved to SDK: `solutions/connections/delegated_mcp` resolves the
per-user MCP server map (minting a delegated bearer for delegated connections)
and `frameworks/langchain/mcp` binds it as LangChain tools. This bundle module
is the thin adapter (connection list + turn user -> LangChain tools). Asserts:
only `kind: mcp` connections are considered, and clean degradation (no MCP
connections / adapter absent -> [] , the agent still builds with plain tools).
Fully offline.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _mcp_module():
    _name, module = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "tools_mcp.py")
    return module


_PLAIN_CONNS = [
    {"name": "calc", "kind": "python", "alias": "calc", "allowed": ["calc"]},
    {"name": "code_exec", "kind": "python", "alias": "code_exec", "allowed": ["run_python"]},
]
_MCP_CONN = {"name": "memory", "kind": "mcp", "url": "https://h/api/mcp/mem", "delegated": True, "scopes": ["memories:read"]}


def test_mcp_connections_filters_by_kind() -> None:
    m = _mcp_module()
    assert m.mcp_connections(_PLAIN_CONNS) == []
    assert m.mcp_connections(_PLAIN_CONNS + [_MCP_CONN]) == [_MCP_CONN]


def test_no_mcp_connection_returns_empty() -> None:
    m = _mcp_module()
    # No kind:mcp declared -> no MCP tools (the agent still builds with plain tools).
    tools, consents = asyncio.run(m.load_mcp_tools_for_connections(_PLAIN_CONNS, user_sub="u"))
    assert tools == [] and consents == []


def test_mcp_connection_degrades_to_empty_when_adapter_absent() -> None:
    m = _mcp_module()
    # langchain-mcp-adapters is not installed in the test env: the delegated MCP
    # connection resolves a server map but binding degrades to [] — never a crash.
    # (No user -> the delegated server is dropped before any bind is attempted.)
    tools, consents = asyncio.run(m.load_mcp_tools_for_connections([_MCP_CONN], user_sub=None))
    assert tools == [] and consents == []


def test_consent_pending_drop_raises_a_demand_not_a_silent_gap() -> None:
    # REGRESSION (surfaced live 2026-07-17): with the consented-token path, a
    # connection whose user hasn't granted THIS agent is dropped BEFORE any
    # server contact — no 403 ever happens. The demand must come from the drop,
    # otherwise the agent silently loses the tool and tells the user the
    # capability does not exist.
    m = _mcp_module()

    async def no_grant(conn, user_sub):
        return None  # consent pending for this agent

    tools, consents = asyncio.run(m.load_mcp_tools_for_connections(
        [_MCP_CONN], user_sub="u1",
        application="ported-langgraph-agents@2026-07-13", agent_id="lg-react",
        bearer_provider=no_grant,
    ))
    assert tools == []
    assert len(consents) == 1
    c = consents[0]
    assert c.claims == ["memories:read"]
    # The demand is actionable: it carries the one-click grant for THIS agent.
    grant = c.consent["grant"]
    assert grant["payload"]["client_id"] == "kdcube-agent:ported-langgraph-agents@2026-07-13:lg-react"
    assert grant["payload"]["resource"] == "https://h/api/mcp/mem"


def test_demand_keys_on_the_declared_resource_id_not_the_url() -> None:
    # A deployment's delegated-resource catalog often configures a WILDCARD
    # pattern; the connection declares it via `resource` while `url` stays the
    # concrete endpoint. The demand (and its one-click grant payload) must key
    # on the pattern — the grant is created, validated, and looked up under
    # that exact id, and the guard fnmatches the request URL against it.
    m = _mcp_module()
    conn = {
        **_MCP_CONN,
        "resource": "*/api/integrations/bundles/*/*/user-memories@2026-06-26/public/mcp/memories*",
    }

    async def no_grant(c, user_sub):
        return None

    tools, consents = asyncio.run(m.load_mcp_tools_for_connections(
        [conn], user_sub="u1", application="app", agent_id="lg-react", bearer_provider=no_grant,
    ))
    assert tools == [] and len(consents) == 1
    c = consents[0]
    assert c.resource == conn["resource"]
    assert c.consent["grant"]["payload"]["resource"] == conn["resource"]


def test_consent_stub_raises_the_demand_at_the_ATTEMPT_not_at_build() -> None:
    # Consent is demand-driven per tool (surfaced live: asking about memories
    # raised the SLACK demand, because every pending connection announced at
    # build — a turn-start claim union). Pending connections bind consent-gated
    # stubs instead: nothing announces at build; CALLING the stub announces
    # exactly that connection's demand and returns the consent tool-result.
    m = _mcp_module()

    async def no_grant(conn, user_sub):
        return None

    _tools, consents = asyncio.run(m.load_mcp_tools_for_connections(
        [_MCP_CONN], user_sub="u1", application="app", agent_id="lg-react",
        bearer_provider=no_grant,
    ))
    announced: list = []

    async def announce(c):
        announced.append(c)

    stubs = m.consent_request_tools(consents, announce=announce)
    assert len(stubs) == 1
    stub = stubs[0]
    assert stub.name == "memory"                       # the connection's alias
    assert "consent" in stub.description.lower()
    assert announced == []                             # nothing at build

    result = asyncio.run(stub.coroutine(reason="user asked about cities"))
    assert announced == consents                       # the ATTEMPT announced it
    assert result["ok"] is False
    assert result["consent"]["grant"]["payload"]["claims"] == ["memories:read"]


def test_no_user_drop_stays_silent() -> None:
    # An anonymous turn cannot grant; the delegated connection is dropped with
    # no demand (nothing for the user to act on).
    m = _mcp_module()

    async def boom(conn, user_sub):  # must not even be called without a user
        raise AssertionError("bearer provider must not run without a user")

    tools, consents = asyncio.run(m.load_mcp_tools_for_connections(
        [_MCP_CONN], user_sub=None, application="a", agent_id="b", bearer_provider=boom,
    ))
    assert tools == [] and consents == []


def test_user_opt_out_drops_the_mcp_connection() -> None:
    m = _mcp_module()
    # The picker deny-map opts the whole MCP tool out this turn -> it is not bound
    # (governance: admin-declared ∩ user-enabled, same as plain/code-exec tools).
    # _MCP_CONN's name/alias is "memory".
    assert m.mcp_connections([_MCP_CONN], None) == [_MCP_CONN]          # not opted out -> kept
    assert m.mcp_connections([_MCP_CONN], {"memory": True}) == []       # opted out -> dropped
    assert m.mcp_connections([_MCP_CONN], {"other": True}) == [_MCP_CONN]  # unrelated opt-out ignored


def test_wrap_tools_delivers_files_to_user_and_strips_the_url(monkeypatch) -> None:
    # A named-service MCP result carrying a signed download URL: the wrap
    # emits the file to the USER as a chat.files card (object ref, no URL)
    # and the MODEL-visible result keeps a delivery note instead of the URL —
    # a hand-typed signed link is how the corrupted-token 403 happened.
    import json as _json

    m = _mcp_module()

    slack_ref = "slack:acct:file:F123"
    raw = _json.dumps({
        "ok": True,
        "object": {
            "ref": slack_ref, "object_ref": slack_ref, "object_kind": "slack.file",
            "name": "img.png", "mimetype": "image/png", "size": 75,
            "download": {"encoding": "url", "url": "http://h/dl?download_token=SIGNED"},
        },
    })

    class _Tool:
        name = "named_services_action"

        async def _run(self) -> str:
            return raw

    tool = _Tool()
    tool.coroutine = tool._run

    events: list = []

    class _Comm:
        async def event(self, **kwargs):
            events.append(kwargs)

    from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx
    monkeypatch.setattr(comm_ctx, "get_comm", lambda: _Comm())

    m.wrap_tools_with_user_delivery([tool])
    out = asyncio.run(tool.coroutine())

    assert len(events) == 1
    assert events[0]["type"] == "chat.files"
    assert events[0]["data"]["items"][0]["object_ref"] == slack_ref
    assert "download_token" not in str(events[0])

    parsed = _json.loads(out)
    assert parsed["object"]["download"]["delivered"] is True
    assert "download_token" not in out


def test_wrap_tools_without_chat_lane_keeps_the_url(monkeypatch) -> None:
    # Turn-less (no communicator): the URL contract stays for clients that
    # fetch out-of-band; nothing is emitted, nothing rewritten.
    import json as _json

    m = _mcp_module()
    raw = _json.dumps({
        "ok": True,
        "object": {"ref": "slack:a:file:F1", "name": "f.bin",
                   "download": {"encoding": "url", "url": "http://h/dl?t=S"}},
    })

    class _Tool:
        name = "named_services_get"

        async def _run(self) -> str:
            return raw

    tool = _Tool()
    tool.coroutine = tool._run

    from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx
    monkeypatch.setattr(comm_ctx, "get_comm", lambda: None)

    m.wrap_tools_with_user_delivery([tool])
    assert asyncio.run(tool.coroutine()) == raw


def test_wrap_tools_announces_the_doors_consent_denial(monkeypatch) -> None:
    # The door denies a mail op the agent's bearer lacks grants for
    # (delegated_consent_required + consent block). The wrap raises the scoped
    # chat consent demand — the USER sees exactly what is asked (mail:read,
    # one-click grant) — and the MODEL gets the explainable consent result
    # instead of a bare error. Regression: the denial reached only the model,
    # so no mail banner rose and the hub landing showed no pending claims.
    import json as _json

    m = _mcp_module()
    client = "kdcube-agent:ported-langgraph-agents@2026-07-13:lg-react"
    resource = "*/api/integrations/bundles/*/*/kdcube-services@1-0/public/mcp/named_services*"
    raw = _json.dumps({
        "ok": False,
        "error": "delegated_consent_required",
        "namespace": "mail",
        "missing_grants": ["mail:read"],
        "code": "connections.consent_needed",
        "consent": {
            "kind": "delegated_agent_grant",
            "agent_client_id": client,
            "resource": resource,
            "claims": ["mail:read"],
            "tool_name": "mail",
        },
    })

    class _Tool:
        name = "named_services_search"

        async def _run(self) -> str:
            return raw

    tool = _Tool()
    tool.coroutine = tool._run

    announced: list = []

    async def fake_announce(consent):
        announced.append(consent)

    from kdcube_ai_app.apps.chat.sdk.solutions.connections import mcp_consent as consent_mod
    monkeypatch.setattr(consent_mod, "announce_agent_consent", fake_announce)

    m.wrap_tools_with_user_delivery([tool], agent_client_id=client, fallback_resource=resource)
    out = _json.loads(asyncio.run(tool.coroutine()))

    assert len(announced) == 1
    assert announced[0].claims == ["mail:read"]
    assert announced[0].resource == resource

    assert out["ok"] is False
    assert out["consent"]["grant"]["payload"] == {
        "client_id": client, "resource": resource, "claims": ["mail:read"],
    }
    assert "mail:read" in out["error"]["message"]


def test_wrap_tools_consent_denial_without_block_uses_connection_context(monkeypatch) -> None:
    # An older door returns the bare denial (no consent block): the wrap still
    # raises the demand from its own connection context (this agent's client id
    # + the single delegated connection's resource) and the missing grants.
    import json as _json

    m = _mcp_module()
    client = "kdcube-agent:app:agent"
    raw = _json.dumps({
        "ok": False, "error": "delegated_consent_required",
        "namespace": "mail", "missing_grants": ["mail:read"],
    })

    class _Tool:
        name = "named_services_get"

        async def _run(self) -> str:
            return raw

    tool = _Tool()
    tool.coroutine = tool._run

    announced: list = []

    async def fake_announce(consent):
        announced.append(consent)

    from kdcube_ai_app.apps.chat.sdk.solutions.connections import mcp_consent as consent_mod
    monkeypatch.setattr(consent_mod, "announce_agent_consent", fake_announce)

    m.wrap_tools_with_user_delivery([tool], agent_client_id=client, fallback_resource="https://h/api/mcp/ns")
    out = _json.loads(asyncio.run(tool.coroutine()))
    assert len(announced) == 1
    assert out["consent"]["grant"]["payload"]["claims"] == ["mail:read"]
    assert out["consent"]["grant"]["payload"]["resource"] == "https://h/api/mcp/ns"

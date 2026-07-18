# SPDX-License-Identifier: MIT

"""Fork reconstruction on the conversation read path.

The store carries the fork relationship in both directions (the parent
turn's ``forks`` descriptors on its turn log; the child conversation's
``forked_from`` backref on its timeline). These tests pin how the read
path surfaces them: per-turn ``forks`` and conversation-level
``forked_from`` on fetch, ``forked_from`` on list rows, and the ingress
router passing all of it through — a child conversation is fetched through
the same endpoint by the same user.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.ingress.conversations import conversations
from kdcube_ai_app.apps.chat.sdk.solutions.conversation.ctx_rag import ContextRAGClient

FORKED_FROM = {"conversation_id": "conv_parent", "turn_id": "turn_parent"}
FORKS = [{
    "child_conversation_id": "sub_abc",
    "charter_goal": "Research X",
    "forked_at": "2026-07-12T10:00:00Z",
}]


# ------------------------------------------------------------- ctx_rag level


def _client(*, idx=None):
    return ContextRAGClient(
        conv_idx=idx or SimpleNamespace(),
        store=SimpleNamespace(),
        model_service=SimpleNamespace(),
    )


def _timeline_text(**extra):
    return json.dumps({
        "conversation_title": "T",
        "conversation_started_at": "2026-07-12T09:00:00Z",
        "last_activity_at": "2026-07-12T10:05:00Z",
        "blocks_count": 1,
        "sources_pool_count": 0,
        "sources_pool": [],
        "turn_ids": ["turn_parent"],
        **extra,
    })


@pytest.mark.asyncio
async def test_fetch_conversation_artifacts_surfaces_turn_forks_and_forked_from():
    async def _turn_tags(**kwargs):
        return [{
            "turn_id": "turn_parent",
            "ts": "2026-07-12T10:00:00Z",
            "tags": [],
            "mid": "m1",
            "hosted_uri": None,
            "bundle_id": "bundle@1",
        }]

    client = _client(idx=SimpleNamespace(get_conversation_turn_ids_from_tags=_turn_tags))

    async def _recent(**kwargs):
        return {"items": [{
            "text": _timeline_text(forked_from=FORKED_FROM),
            "bundle_id": "bundle@1",
        }]}

    async def _materialize_turn(**kwargs):
        return {"turn_log": {
            "meta": {},
            "bundle_id": "bundle@1",
            "payload": {
                "turn_id": kwargs.get("turn_id"),
                "ts": "2026-07-12T10:00:00Z",
                "blocks": [],
                "forks": FORKS,
            },
        }}

    client.recent = _recent
    client.materialize_turn = _materialize_turn

    data = await client.fetch_conversation_artifacts(
        user_id="user_1", conversation_id="conv_parent", ctx={},
    )
    assert data["forked_from"] == FORKED_FROM
    turn = data["turns"][0]
    assert turn["turn_id"] == "turn_parent"
    assert turn["forks"] == FORKS


@pytest.mark.asyncio
async def test_fetch_conversation_artifacts_without_forks_stays_shapeless():
    """A turn without delegations carries no forks key; a conversation that
    is not a fork carries no forked_from key."""
    async def _turn_tags(**kwargs):
        return [{
            "turn_id": "turn_1",
            "ts": "2026-07-12T10:00:00Z",
            "tags": [],
            "mid": "m1",
            "hosted_uri": None,
            "bundle_id": "bundle@1",
        }]

    client = _client(idx=SimpleNamespace(get_conversation_turn_ids_from_tags=_turn_tags))

    async def _recent(**kwargs):
        return {"items": [{"text": _timeline_text(), "bundle_id": "bundle@1"}]}

    async def _materialize_turn(**kwargs):
        return {"turn_log": {
            "meta": {},
            "payload": {"turn_id": kwargs.get("turn_id"), "ts": "2026-07-12T10:00:00Z", "blocks": []},
        }}

    client.recent = _recent
    client.materialize_turn = _materialize_turn

    data = await client.fetch_conversation_artifacts(
        user_id="user_1", conversation_id="conv_plain", ctx={},
    )
    assert "forked_from" not in data
    assert "forks" not in data["turns"][0]


@pytest.mark.asyncio
async def test_list_conversations_exposes_forked_from_on_child_rows():
    async def _fetch_recent(**kwargs):
        return [
            {
                "conversation_id": "sub_abc",
                "ts": "2026-07-12T10:05:00Z",
                "text": _timeline_text(forked_from=FORKED_FROM),
            },
            {
                "conversation_id": "conv_parent",
                "ts": "2026-07-12T10:06:00Z",
                "text": _timeline_text(),
            },
        ]

    client = _client(idx=SimpleNamespace(fetch_recent=_fetch_recent))
    data = await client.list_conversations("user_1", ctx={})
    rows = {item["conversation_id"]: item for item in data["items"]}
    # the child row appears (never hard-excluded) and carries its backref
    assert rows["sub_abc"]["forked_from"] == FORKED_FROM
    assert "forked_from" not in rows["conv_parent"]


# ------------------------------------------------------------ ingress router


class _FakeBrowser:
    def __init__(self):
        self.calls = []

    async def get_conversation_details(self, **kwargs):
        self.calls.append(("get_conversation_details", kwargs))
        return {
            "user_id": kwargs["user_id"],
            "conversation_id": kwargs["conversation_id"],
            "turns": [{"turn_id": "turn_c1", "artifacts": []}],
        }

    async def fetch_conversation_artifacts(self, **kwargs):
        self.calls.append(("fetch_conversation_artifacts", kwargs))
        conversation_id = kwargs["conversation_id"]
        if conversation_id == "sub_abc":
            # a child conversation: same endpoint, forked_from backref
            return {
                "user_id": kwargs["user_id"],
                "conversation_id": conversation_id,
                "conversation_title": "Child",
                "forked_from": FORKED_FROM,
                "turns": [{"turn_id": "turn_c1", "artifacts": []}],
            }
        return {
            "user_id": kwargs["user_id"],
            "conversation_id": conversation_id,
            "conversation_title": "Parent",
            "turns": [{"turn_id": "turn_parent", "forks": FORKS, "artifacts": []}],
        }

    async def list_conversations(self, **kwargs):
        self.calls.append(("list_conversations", kwargs))
        return {
            "user_id": kwargs["user_id"],
            "items": [
                {
                    "conversation_id": "sub_abc",
                    "last_activity_at": "2026-07-12T10:05:00Z",
                    "started_at": "2026-07-12T09:00:00Z",
                    "forked_from": FORKED_FROM,
                },
                {
                    "conversation_id": "conv_parent",
                    "last_activity_at": "2026-07-12T10:06:00Z",
                    "started_at": "2026-07-12T08:00:00Z",
                },
            ],
        }


@pytest.fixture
def _router_state(monkeypatch):
    browser = _FakeBrowser()
    monkeypatch.setattr(
        conversations.router,
        "state",
        SimpleNamespace(conversation_browser=browser),
        raising=False,
    )

    async def _load_registry(runtime_ctx, tenant, project):
        return SimpleNamespace(bundles={"bundle@1": object()})

    monkeypatch.setattr(
        conversations, "load_persisted_registry_from_runtime_ctx", _load_registry,
    )
    return browser


@pytest.mark.asyncio
async def test_fetch_passes_through_turn_forks(_router_state):
    session = SimpleNamespace(user_id="user_1")
    resp = await conversations.fetch_conversation(
        tenant="tenant-a",
        project="project-a",
        conversation_id="conv_parent",
        req=conversations.ConversationFetchRequest(),
        bundle_id=None,
        agent_id=None,
        session=session,
    )
    assert resp["turns"][0]["forks"] == FORKS


@pytest.mark.asyncio
async def test_child_conversation_fetches_through_the_same_endpoint(_router_state):
    session = SimpleNamespace(user_id="user_1")
    resp = await conversations.fetch_conversation(
        tenant="tenant-a",
        project="project-a",
        conversation_id="sub_abc",
        req=conversations.ConversationFetchRequest(),
        bundle_id=None,
        agent_id=None,
        session=session,
    )
    assert resp["conversation_id"] == "sub_abc"
    assert resp["forked_from"] == FORKED_FROM
    # scope check + fetch both ran against the child conversation id
    assert [c[1]["conversation_id"] for c in _router_state.calls] == ["sub_abc", "sub_abc"]


@pytest.mark.asyncio
async def test_list_response_model_keeps_forked_from(monkeypatch, _router_state):
    async def _resolve_default(runtime_ctx, tenant, project):
        return "bundle@1"

    monkeypatch.setattr(
        conversations, "resolve_default_bundle_id_from_runtime_ctx", _resolve_default,
    )
    session = SimpleNamespace(user_id="user_1")
    data = await conversations.list_conversations(
        tenant="tenant-a",
        project="project-a",
        last_n=None,
        started_after=None,
        days=365,
        include_titles=True,
        bundle_id=None,
        agent_id=None,
        session=session,
    )
    # the declared response model keeps the fork marker on child rows
    model = conversations.ConversationListResponse(**data)
    by_id = {item.conversation_id: item for item in model.items}
    assert by_id["sub_abc"].forked_from == FORKED_FROM
    assert by_id["conv_parent"].forked_from is None

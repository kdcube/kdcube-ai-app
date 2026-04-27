from types import SimpleNamespace
import json

import pytest

from kdcube_ai_app.apps.chat.sdk.context.retrieval.ctx_rag import ContextRAGClient


@pytest.mark.asyncio
async def test_fetch_turns_with_feedbacks_ignores_ctx_bundle_filter_and_infers_bundle_id(monkeypatch):
    client = ContextRAGClient(
        conv_idx=SimpleNamespace(),
        store=SimpleNamespace(),
        model_service=None,
    )

    calls = []

    async def _search(**kwargs):
        calls.append(("search", kwargs["bundle_id"], dict(kwargs["ctx"] or {})))
        assert kwargs["bundle_id"] is None
        assert "bundle_id" not in (kwargs["ctx"] or {})
        assert "app_bundle_id" not in (kwargs["ctx"] or {})
        if kwargs["kinds"] == ("artifact:turn.log.reaction",):
            return {"items": [{"turn_id": "turn-1"}]}
        if kwargs["kinds"] == ("artifact:turn.log",):
            return {"items": []}
        raise AssertionError(f"unexpected search call: {kwargs}")

    async def _materialize_turn(**kwargs):
        calls.append(("materialize_turn", kwargs["bundle_id"], dict(kwargs["ctx"] or {})))
        assert kwargs["bundle_id"] is None
        assert "bundle_id" not in (kwargs["ctx"] or {})
        assert "app_bundle_id" not in (kwargs["ctx"] or {})
        return {
            "turn_log": {
                "bundle_id": "bundle.from.db",
                "message_id": "turn-log-1",
                "payload": {
                    "blocks": [
                        {"type": "stage.feedback", "ts": "2026-04-01T09:00:00Z", "text": "Looks good"}
                    ]
                },
            },
            "assistant": {
                "bundle_id": "bundle.from.db",
                "payload": {"text": "assistant"},
            },
            "user": {
                "bundle_id": "bundle.from.db",
                "payload": {"text": "user"},
            },
        }

    async def _recent(**kwargs):
        calls.append(("recent", kwargs["bundle_id"], dict(kwargs["ctx"] or {})))
        assert kwargs["bundle_id"] is None
        assert "bundle_id" not in (kwargs["ctx"] or {})
        assert "app_bundle_id" not in (kwargs["ctx"] or {})
        return {"items": []}

    monkeypatch.setattr(client, "search", _search)
    monkeypatch.setattr(client, "materialize_turn", _materialize_turn)
    monkeypatch.setattr(client, "recent", _recent)

    result = await client.fetch_turns_with_feedbacks(
        user_id="user-1",
        conversation_id="conv-1",
        ctx={
            "user_id": "ctx-user",
            "conversation_id": "ctx-conv",
            "bundle_id": "bundle.ctx",
            "app_bundle_id": "bundle.ctx.app",
        },
    )

    assert result["user_id"] == "user-1"
    assert result["conversation_id"] == "conv-1"
    assert result["bundle_id"] == "bundle.from.db"
    assert result["bundle_ids"] == ["bundle.from.db"]
    assert result["turns"] == [
        {
            "turn_id": "turn-1",
            "bundle_id": "bundle.from.db",
            "turn_log": {
                "blocks": [
                    {"type": "stage.feedback", "ts": "2026-04-01T09:00:00Z", "text": "Looks good"}
                ]
            },
            "assistant": {
                "bundle_id": "bundle.from.db",
                "payload": {"text": "assistant"},
            },
            "user": {
                "bundle_id": "bundle.from.db",
                "payload": {"text": "user"},
            },
            "feedbacks": [{"ts": "2026-04-01T09:00:00Z", "text": "Looks good"}],
            "reactions": [],
        }
    ]
    assert calls


@pytest.mark.asyncio
async def test_fetch_conversation_artifacts_ignores_ctx_bundle_filter_and_infers_bundle_id(monkeypatch):
    idx = SimpleNamespace()
    client = ContextRAGClient(
        conv_idx=idx,
        store=SimpleNamespace(),
        model_service=None,
    )

    calls = []

    async def _get_conversation_turn_ids_from_tags(**kwargs):
        calls.append(("turn_ids", kwargs["bundle_id"], dict(kwargs["ctx"] or {})))
        assert kwargs["bundle_id"] is None
        assert "bundle_id" not in (kwargs["ctx"] or {})
        assert "app_bundle_id" not in (kwargs["ctx"] or {})
        return [
            {
                "turn_id": "turn-1",
                "ts": "2026-04-01T09:00:00Z",
                "tags": ["turn:turn-1", "artifact:conv.artifacts.stream"],
                "mid": "m-1",
                "hosted_uri": "index_only",
                "bundle_id": "bundle.from.db",
            }
        ]

    idx.get_conversation_turn_ids_from_tags = _get_conversation_turn_ids_from_tags

    async def _recent(**kwargs):
        calls.append(("recent", kwargs["bundle_id"], dict(kwargs["ctx"] or {})))
        assert kwargs["bundle_id"] is None
        assert "bundle_id" not in (kwargs["ctx"] or {})
        assert "app_bundle_id" not in (kwargs["ctx"] or {})
        return {"items": []}

    async def _materialize_turn(**kwargs):
        calls.append(("materialize_turn", kwargs["bundle_id"], dict(kwargs["ctx"] or {})))
        assert kwargs["bundle_id"] is None
        assert "bundle_id" not in (kwargs["ctx"] or {})
        assert "app_bundle_id" not in (kwargs["ctx"] or {})
        return {
            "turn_log": {},
            "assistant": None,
            "user": None,
        }

    monkeypatch.setattr(client, "recent", _recent)
    monkeypatch.setattr(client, "materialize_turn", _materialize_turn)

    result = await client.fetch_conversation_artifacts(
        user_id="user-1",
        conversation_id="conv-1",
        materialize=False,
        ctx={
            "user_id": "ctx-user",
            "conversation_id": "ctx-conv",
            "bundle_id": "bundle.ctx",
            "app_bundle_id": "bundle.ctx.app",
        },
    )

    assert result["user_id"] == "user-1"
    assert result["conversation_id"] == "conv-1"
    assert result["bundle_id"] == "bundle.from.db"
    assert result["bundle_ids"] == ["bundle.from.db"]
    assert result["turns"] == [
        {
            "turn_id": "turn-1",
            "artifacts": [
                {
                    "message_id": "m-1",
                    "type": "artifact:conv.artifacts.stream",
                    "ts": "2026-04-01T09:00:00Z",
                    "hosted_uri": "index_only",
                    "bundle_id": "bundle.from.db",
                }
            ],
        }
    ]
    assert calls


@pytest.mark.asyncio
async def test_fetch_conversation_artifacts_materializes_multi_entry_turn_in_order(monkeypatch):
    idx = SimpleNamespace()
    client = ContextRAGClient(
        conv_idx=idx,
        store=SimpleNamespace(),
        model_service=None,
    )

    async def _get_conversation_turn_ids_from_tags(**kwargs):
        return [
            {
                "turn_id": "turn-1",
                "ts": "2026-04-01T09:00:00Z",
                "tags": ["turn:turn-1"],
                "mid": "m-1",
                "hosted_uri": "index_only",
                "bundle_id": "bundle.from.db",
            }
        ]

    idx.get_conversation_turn_ids_from_tags = _get_conversation_turn_ids_from_tags

    async def _recent(**kwargs):
        return {"items": []}

    async def _materialize_turn(**kwargs):
        return {
            "turn_log": {
                "bundle_id": "bundle.from.db",
                "message_id": "turn-log-1",
                "payload": {
                    "blocks": [
                        {
                            "type": "user.prompt",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:00:00Z",
                            "path": "ar:turn-1.user.prompt",
                            "text": "Initial prompt",
                        },
                        {
                            "type": "user.followup",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:01:00Z",
                            "path": "ar:turn-1.external.followup.msg-1",
                            "text": "Extra constraint",
                            "meta": {"message_id": "msg-1", "sequence": 2, "event_kind": "followup"},
                        },
                        {
                            "type": "user.attachment.meta",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:01:00Z",
                            "path": "fi:turn-1.external.followup.attachments/msg-1/brief.txt",
                            "meta": {
                                "filename": "brief.txt",
                                "mime": "text/plain",
                                "hosted_uri": "s3://bucket/brief.txt",
                                "continuation_kind": "followup",
                                "event_kind": "followup",
                                "message_id": "msg-1",
                                "sequence": 2,
                            },
                            "text": "{}",
                        },
                        {
                            "type": "assistant.completion",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:02:00Z",
                            "path": "ar:turn-1.assistant.completion.1",
                            "text": "Draft answer",
                        },
                        {
                            "type": "react.tool.result",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:03:00Z",
                            "mime": "application/json",
                            "text": json.dumps({
                                "visibility": "external",
                                "kind": "file",
                                "artifact_path": "fi:turn-1.files/report.pdf",
                                "hosted_uri": "s3://bucket/report.pdf",
                                "filename": "report.pdf",
                                "mime": "application/pdf",
                                "tool_id": "write",
                            }),
                        },
                        {
                            "type": "assistant.completion",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:04:00Z",
                            "path": "ar:turn-1.assistant.completion",
                            "text": "Final answer",
                        },
                    ]
                },
            },
            "assistant": None,
            "user": None,
        }

    monkeypatch.setattr(client, "recent", _recent)
    monkeypatch.setattr(client, "materialize_turn", _materialize_turn)

    result = await client.fetch_conversation_artifacts(
        user_id="user-1",
        conversation_id="conv-1",
        materialize=True,
        ctx={},
    )

    artifacts = result["turns"][0]["artifacts"]
    assert [item["type"] for item in artifacts] == [
        "chat:user",
        "chat:user",
        "artifact:user.attachment",
        "chat:assistant",
        "artifact:assistant.file",
        "chat:assistant",
    ]
    assert artifacts[1]["data"]["continuation_kind"] == "followup"
    assert artifacts[1]["data"]["meta"]["message_id"] == "msg-1"
    assert artifacts[1]["data"]["meta"]["path"] == "ar:turn-1.external.followup.msg-1"
    assert artifacts[2]["ts"] == "2026-04-01T09:01:00Z"
    assert artifacts[2]["data"]["payload"]["artifact_path"] == "fi:turn-1.external.followup.attachments/msg-1/brief.txt"
    assert artifacts[2]["data"]["meta"]["message_id"] == "msg-1"
    assert artifacts[4]["ts"] == "2026-04-01T09:03:00Z"
    assert artifacts[4]["data"]["payload"]["artifact_path"] == "fi:turn-1.files/report.pdf"
    assert artifacts[5]["data"]["meta"]["path"] == "ar:turn-1.assistant.completion"


@pytest.mark.asyncio
async def test_fetch_conversation_artifacts_preserves_turn_log_chat_timestamps(monkeypatch):
    idx = SimpleNamespace()
    client = ContextRAGClient(
        conv_idx=idx,
        store=SimpleNamespace(),
        model_service=None,
    )

    async def _get_conversation_turn_ids_from_tags(**kwargs):
        return [
            {
                "turn_id": "turn-1",
                "ts": "2026-04-01T09:00:00Z",
                "tags": ["turn:turn-1"],
                "mid": "m-1",
                "hosted_uri": "index_only",
                "bundle_id": "bundle.from.db",
            }
        ]

    idx.get_conversation_turn_ids_from_tags = _get_conversation_turn_ids_from_tags

    async def _recent(**kwargs):
        return {"items": []}

    async def _materialize_turn(**kwargs):
        return {
            "turn_log": {
                "bundle_id": "bundle.from.db",
                "message_id": "turn-log-1",
                "payload": {
                    "blocks": [
                        {
                            "type": "user.prompt",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:00:00Z",
                            "path": "ar:turn-1.user.prompt",
                            "text": "Start",
                            "meta": {"message_id": "m0"},
                        },
                        {
                            "type": "assistant.completion",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:00:00.767000Z",
                            "path": "ar:turn-1.assistant.completion.1",
                            "text": "First streamed answer",
                        },
                        {
                            "type": "user.followup",
                            "turn_id": "turn-1",
                            "ts": "2026-04-01T09:00:01Z",
                            "path": "ar:turn-1.external.followup.msg-1",
                            "text": "Followup",
                            "meta": {"message_id": "msg-1", "sequence": 2, "event_kind": "followup"},
                        },
                    ]
                },
            },
            "assistant": None,
            "user": None,
        }

    monkeypatch.setattr(client, "recent", _recent)
    monkeypatch.setattr(client, "materialize_turn", _materialize_turn)

    result = await client.fetch_conversation_artifacts(
        user_id="user-1",
        conversation_id="conv-1",
        materialize=True,
        ctx={},
    )

    artifacts = result["turns"][0]["artifacts"]
    assert [(item["type"], item["ts"]) for item in artifacts] == [
        ("chat:user", "2026-04-01T09:00:00Z"),
        ("chat:assistant", "2026-04-01T09:00:00.767000Z"),
        ("chat:user", "2026-04-01T09:00:01Z"),
    ]
    assert artifacts[1]["data"]["meta"]["path"] == "ar:turn-1.assistant.completion.1"
    assert artifacts[2]["data"]["meta"]["path"] == "ar:turn-1.external.followup.msg-1"

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import json
import uuid
from typing import Any, Awaitable, Callable, Mapping, Optional


class NamedServiceSearchResultsWidget:
    """Emit named-service search hits as context-compatible subsystem data."""

    def __init__(
        self,
        *,
        emit_delta: Callable[..., Awaitable[None]],
        agent: str = "named_services.search",
        title: str = "Named service search results",
        artifact_name: str = "named_service.search_results",
        search_id: Optional[str] = None,
    ):
        self.emit_delta = emit_delta
        self.agent = agent
        self.title = title
        self.artifact_name = artifact_name
        self.search_id = search_id or f"ns_{uuid.uuid4().hex[:12]}"
        self.idx = 0

    async def send_search_results(
        self,
        *,
        namespace: str,
        search_scope: str,
        query: str,
        filters: Mapping[str, Any] | None,
        result: Mapping[str, Any],
    ) -> None:
        ret = _mapping(result.get("ret"))
        raw_items = _list(ret.get("items")) or _list(result.get("items"))
        payload = {
            "type": "named_service.search_results",
            "namespace": namespace,
            "search_scope": search_scope,
            "query": query,
            "filters": dict(filters or {}),
            "items": [
                item
                for item in (
                    _context_item_from_search_item(raw_item, namespace=namespace, search_scope=search_scope, index=index)
                    for index, raw_item in enumerate(raw_items)
                )
                if item
            ],
            "raw_count": len(raw_items),
            "attrs": _mapping(ret.get("attrs")),
        }
        await self.emit_delta(
            json.dumps(payload, ensure_ascii=True),
            index=self.idx,
            marker="subsystem",
            agent=self.agent,
            title=self.title,
            format="json",
            artifact_name=f"{self.artifact_name}.{self.search_id}",
            sub_type="named_service.search_results",
            search_id=self.search_id,
            namespace=namespace,
            search_scope=search_scope,
        )
        self.idx += 1


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _first(*values: Any) -> str:
    for value in values:
        text = _string(value)
        if text:
            return text
    return ""


def _nested(record: Mapping[str, Any], key: str) -> dict[str, Any]:
    return _mapping(record.get(key))


def _context_item_from_search_item(
    item: Any,
    *,
    namespace: str,
    search_scope: str,
    index: int,
) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    record = dict(item)
    identity = _nested(record, "identity")
    body = _nested(record, "body")
    meta = _nested(record, "meta")
    attrs = _nested(record, "attrs")
    data = _nested(record, "data")
    object_ref = _first(
        record.get("object_ref"),
        identity.get("object_ref"),
        attrs.get("object_ref"),
        data.get("object_ref"),
        record.get("ref"),
        record.get("uri"),
        record.get("canonical_uri"),
        record.get("event_ref"),
    )
    label = _first(
        record.get("label"),
        record.get("title"),
        body.get("title"),
        identity.get("label"),
        identity.get("title"),
        record.get("name"),
        body.get("name"),
        object_ref,
        f"{search_scope or namespace}:{index + 1}",
    )
    summary = _first(
        record.get("summary"),
        body.get("summary"),
        record.get("description"),
        body.get("description"),
        attrs.get("summary"),
    )
    object_kind = _first(
        record.get("object_kind"),
        identity.get("object_kind"),
        attrs.get("object_kind"),
        data.get("object_kind"),
    )
    item_namespace = _first(
        record.get("namespace"),
        identity.get("namespace"),
        attrs.get("namespace"),
        namespace,
    )
    mime = _first(record.get("mime"), meta.get("mime"), attrs.get("mime"), data.get("mime"))
    filename = _first(record.get("filename"), body.get("filename"), attrs.get("filename"), data.get("filename"))
    ref = object_ref or _first(record.get("hosted_uri"), record.get("logical_path"), record.get("logicalPath"))
    if not ref:
        return None
    context = {
        "id": _first(record.get("id"), object_ref, ref),
        "kind": "object.ref",
        "cardType": object_kind or "named_service.object",
        "label": label,
        "title": label,
        "summary": summary,
        "ref": ref,
        "object_ref": object_ref or ref,
        "namespace": item_namespace,
        "search_scope": search_scope,
        "object_kind": object_kind,
        "event_source_id": f"named_services.{namespace}" if namespace else "named_services",
        "mime": mime,
        "filename": filename,
        "data": {
            "source": "named_services.search_result",
            "namespace": item_namespace,
            "search_scope": search_scope,
            "object_kind": object_kind,
            "object_ref": object_ref or ref,
            "mime": mime,
            "filename": filename,
        },
    }
    score = record.get("score", record.get("relevance", record.get("rank_score")))
    if isinstance(score, (int, float)):
        context["score"] = score
        context["data"]["score"] = score
    return {key: value for key, value in context.items() if value not in (None, "")}

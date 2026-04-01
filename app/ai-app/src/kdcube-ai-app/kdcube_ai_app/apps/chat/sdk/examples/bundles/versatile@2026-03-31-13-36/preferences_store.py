from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from kdcube_ai_app.apps.chat.sdk.storage.ai_bundle_storage import AIBundleStorage


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_preferences_storage(
    *,
    tenant: str,
    project: str,
    bundle_id: str,
    storage_uri: str | None = None,
) -> AIBundleStorage:
    return AIBundleStorage(
        tenant=str(tenant or "unknown"),
        project=str(project or "unknown"),
        ai_bundle_id=str(bundle_id or "versatile"),
        storage_uri=storage_uri,
    )


def _safe_user_id(user_id: str | None) -> str:
    raw = (user_id or "anonymous").strip() or "anonymous"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)


def _canonical_preference_key(key: str | None) -> str:
    raw = str(key or "").strip()
    if raw.startswith("[p]_"):
        raw = raw[4:]
    return raw


def ensure_preferences_root(storage: AIBundleStorage | None = None) -> str:
    return "preferences/"


def _user_root(user_id: str | None) -> str:
    return f"{ensure_preferences_root()[:-1]}/users/{_safe_user_id(user_id)}"


def _current_key(user_id: str | None) -> str:
    return f"{_user_root(user_id)}/current.json"


def _events_key(user_id: str | None) -> str:
    return f"{_user_root(user_id)}/events.jsonl"


def current_preferences_path(storage: AIBundleStorage, user_id: str | None) -> str:
    return _current_key(user_id)


def _storage_object_path(storage: AIBundleStorage, key: str) -> str:
    return storage._join(storage._bundle_root, storage._normalize_key(key))  # noqa: SLF001


def _load_json_text(raw: str, default: Any) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return default


def _load_json(storage: AIBundleStorage, key: str, default: Any) -> Any:
    try:
        if not storage.exists(key):
            return default
        return _load_json_text(str(storage.read(key, as_text=True)), default)
    except Exception:
        return default


def _write_current_preferences(
    storage: AIBundleStorage,
    user_id: str | None,
    current: Dict[str, Dict[str, Any]],
) -> None:
    storage.write(
        _current_key(user_id),
        json.dumps(current, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        mime="application/json",
    )


def _write_preference_events(
    storage: AIBundleStorage,
    user_id: str | None,
    events: List[Dict[str, Any]],
) -> None:
    content = ""
    if events:
        content = "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n"
    storage.write(
        _events_key(user_id),
        content,
        mime="application/x-ndjson",
    )


def load_current_preferences(
    storage: AIBundleStorage,
    user_id: str | None,
) -> Dict[str, Dict[str, Any]]:
    return _load_json(storage, _current_key(user_id), {})


def load_preference_events(
    storage: AIBundleStorage,
    user_id: str | None,
) -> List[Dict[str, Any]]:
    try:
        if not storage.exists(_events_key(user_id)):
            return []
        raw = str(storage.read(_events_key(user_id), as_text=True))
    except Exception:
        return []

    items: List[Dict[str, Any]] = []
    for raw_line in raw.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            item = json.loads(raw_line)
        except Exception:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items


def _build_preference_event(
    *,
    key: str,
    value: Any,
    source: str,
    origin: str,
    evidence: str | None = None,
    captured_at: str | None = None,
) -> Dict[str, Any]:
    return {
        "captured_at": captured_at or _utc_now(),
        "key": _canonical_preference_key(key),
        "value": value,
        "source": str(source).strip() or "bundle",
        "origin": str(origin).strip() or "manual",
        "evidence": (evidence or "").strip(),
    }


def append_preference_event(
    storage: AIBundleStorage,
    user_id: str | None,
    *,
    key: str,
    value: Any,
    source: str,
    origin: str,
    evidence: str | None = None,
) -> Dict[str, Any]:
    event = _build_preference_event(
        key=key,
        value=value,
        source=source,
        origin=origin,
        evidence=evidence,
    )
    events = load_preference_events(storage, user_id)
    events.append(event)
    _write_preference_events(storage, user_id, events)

    current = load_current_preferences(storage, user_id)
    if value is None:
        current.pop(event["key"], None)
    else:
        current[event["key"]] = {
            "value": value,
            "updated_at": event["captured_at"],
            "source": event["source"],
            "origin": event["origin"],
            "evidence": event["evidence"],
        }
    _write_current_preferences(storage, user_id, current)
    return event


def _is_metadata_entry(value: Any) -> bool:
    return isinstance(value, dict) and any(
        key in value for key in ("value", "updated_at", "source", "origin", "evidence")
    )


def _public_current_view(current: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    public: Dict[str, Dict[str, Any]] = {}
    for raw_key, raw_value in (current or {}).items():
        key = _canonical_preference_key(raw_key)
        if not key:
            continue
        if isinstance(raw_value, dict):
            normalized = {
                "value": raw_value.get("value"),
                "updated_at": raw_value.get("updated_at"),
                "source": raw_value.get("source"),
                "origin": raw_value.get("origin"),
                "evidence": raw_value.get("evidence", ""),
            }
        else:
            normalized = {
                "value": raw_value,
                "updated_at": None,
                "source": None,
                "origin": None,
                "evidence": "",
            }

        previous = public.get(key)
        if previous is None:
            public[key] = normalized
            continue

        prev_ts = str(previous.get("updated_at") or "")
        new_ts = str(normalized.get("updated_at") or "")
        if new_ts >= prev_ts:
            public[key] = normalized
    return public


def _public_event_view(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for event in events or []:
        item = dict(event)
        item["key"] = _canonical_preference_key(item.get("key"))
        out.append(item)
    return out


def get_preferences_snapshot(
    storage: AIBundleStorage,
    user_id: str | None,
) -> Dict[str, Any]:
    return {
        "current": _public_current_view(load_current_preferences(storage, user_id)),
        "items": _public_event_view(load_preference_events(storage, user_id)),
    }


def _modified_timestamp(storage: AIBundleStorage, key: str) -> float | None:
    try:
        return storage.backend.get_modified_time(_storage_object_path(storage, key)).timestamp()
    except Exception:
        return None


def build_preferences_canvas_document(
    storage: AIBundleStorage,
    user_id: str | None,
) -> Dict[str, Any]:
    current = get_preferences_snapshot(storage, user_id)["current"]
    key = current_preferences_path(storage, user_id)
    return {
        "user_id": user_id or "anonymous",
        "path": key,
        "document_format": "json",
        "document_text": json.dumps(
            current,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        ) + "\n",
        "last_modified": _modified_timestamp(storage, key),
    }


def _normalize_canvas_entry(
    *,
    raw_value: Any,
    previous: Dict[str, Any] | None,
    updated_at: str,
) -> Dict[str, Any]:
    previous = previous if isinstance(previous, dict) else {}

    if _is_metadata_entry(raw_value):
        entry = dict(raw_value)
        normalized_value = entry.get("value")
        changed = (
            previous.get("value") != normalized_value
            or previous.get("source") != entry.get("source")
            or previous.get("origin") != entry.get("origin")
            or previous.get("evidence") != entry.get("evidence")
        )
        return {
            "value": normalized_value,
            "updated_at": entry.get("updated_at")
            or (updated_at if changed else previous.get("updated_at") or updated_at),
            "source": entry.get("source") or previous.get("source") or "preferences_canvas",
            "origin": entry.get("origin") or previous.get("origin") or "user_canvas",
            "evidence": entry.get("evidence")
            if "evidence" in entry
            else previous.get("evidence", ""),
        }

    if previous.get("value") == raw_value:
        return {
            "value": raw_value,
            "updated_at": previous.get("updated_at") or updated_at,
            "source": previous.get("source") or "preferences_canvas",
            "origin": previous.get("origin") or "user_canvas",
            "evidence": previous.get("evidence", ""),
        }

    return {
        "value": raw_value,
        "updated_at": updated_at,
        "source": "preferences_canvas",
        "origin": "user_canvas",
        "evidence": "Saved from collaborative preferences canvas",
    }


def save_preferences_canvas_document(
    storage: AIBundleStorage,
    user_id: str | None,
    *,
    document_text: str,
) -> Dict[str, Any]:
    try:
        parsed = json.loads(document_text)
    except Exception as exc:
        raise ValueError(f"Canvas document must be valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Canvas document must be a top-level JSON object.")

    current = _public_current_view(load_current_preferences(storage, user_id))
    updated_at = _utc_now()
    normalized: Dict[str, Dict[str, Any]] = {}
    changed_keys: List[str] = []
    removed_keys: List[str] = []

    for raw_key, raw_value in parsed.items():
        key = _canonical_preference_key(raw_key)
        if not key:
            continue
        previous = current.get(key)
        normalized_entry = _normalize_canvas_entry(
            raw_value=raw_value,
            previous=previous,
            updated_at=updated_at,
        )
        normalized[key] = normalized_entry
        if previous != normalized_entry:
            changed_keys.append(key)

    for key in current.keys():
        if key not in normalized:
            removed_keys.append(str(key))

    events = load_preference_events(storage, user_id)
    for key in changed_keys:
        entry = normalized[key]
        events.append(
            _build_preference_event(
                key=key,
                value=entry.get("value"),
                source=entry.get("source") or "preferences_canvas",
                origin=entry.get("origin") or "user_canvas",
                evidence=entry.get("evidence") or "Saved from collaborative preferences canvas",
                captured_at=str(entry.get("updated_at") or updated_at),
            )
        )

    for key in removed_keys:
        events.append(
            _build_preference_event(
                key=key,
                value=None,
                source="preferences_canvas",
                origin="user_canvas_remove",
                evidence="Removed from collaborative preferences canvas",
                captured_at=updated_at,
            )
        )

    _write_current_preferences(storage, user_id, normalized)
    _write_preference_events(storage, user_id, events)

    document = build_preferences_canvas_document(storage, user_id)
    document.update(
        {
            "changed_keys": changed_keys,
            "removed_keys": removed_keys,
        }
    )
    return document


_AUTO_PATTERNS: List[tuple[re.Pattern[str], str | None]] = [
    (re.compile(r"\bcall me\s+(?P<value>[^.?!\n]+)", re.IGNORECASE), "preferred_name"),
    (re.compile(r"\bi prefer\s+(?P<value>[^.?!\n]+)", re.IGNORECASE), "preference"),
    (
        re.compile(
            r"\bmy favorite (?P<key>[a-zA-Z0-9 _-]{2,40}) is (?P<value>[^.?!\n]+)",
            re.IGNORECASE,
        ),
        None,
    ),
    (re.compile(r"\bi like\s+(?P<value>[^.?!\n]+)", re.IGNORECASE), "likes"),
    (re.compile(r"\bi dislike\s+(?P<value>[^.?!\n]+)", re.IGNORECASE), "dislikes"),
]


def auto_capture_preferences(
    storage: AIBundleStorage,
    user_id: str | None,
    *,
    text: str,
    source: str = "chat",
) -> List[Dict[str, Any]]:
    raw_text = (text or "").strip()
    if not raw_text:
        return []

    captured: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pattern, fixed_key in _AUTO_PATTERNS:
        for match in pattern.finditer(raw_text):
            value = (match.groupdict().get("value") or "").strip(" .,:;")
            if not value:
                continue
            key = fixed_key or (match.groupdict().get("key") or "").strip().lower().replace(" ", "_")
            if not key:
                key = "preference"
            dedupe_key = (key, value.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            captured.append(
                append_preference_event(
                    storage,
                    user_id,
                    key=key,
                    value=value,
                    source=source,
                    origin="auto_capture",
                    evidence=raw_text,
                )
            )
    return captured


def _normalize_keywords(kwords: Any) -> List[str]:
    if not kwords:
        return []
    if isinstance(kwords, str):
        parts = re.split(r"[,;\n]+", kwords)
    elif isinstance(kwords, Iterable):
        parts = [str(item) for item in kwords]
    else:
        parts = [str(kwords)]
    return [part.strip().lower() for part in parts if str(part).strip()]


def get_preferences_view(
    storage: AIBundleStorage,
    user_id: str | None,
    *,
    recency: int = 10,
    kwords: Any = None,
) -> Dict[str, Any]:
    snapshot = get_preferences_snapshot(storage, user_id)
    current = snapshot["current"]
    events = snapshot["items"]
    keywords = _normalize_keywords(kwords)

    def _matches_keywords(haystack: str) -> bool:
        if not keywords:
            return True
        lowered = haystack.lower()
        return any(keyword in lowered for keyword in keywords)

    def _matches(event: Dict[str, Any]) -> bool:
        haystack = " ".join(
            [
                str(event.get("key") or ""),
                str(event.get("value") or ""),
                str(event.get("evidence") or ""),
            ]
        )
        return _matches_keywords(haystack)

    matched = [event for event in reversed(events) if _matches(event)]
    limited = matched[: max(1, int(recency or 10))]
    current_subset = {
        key: value
        for key, value in current.items()
        if _matches_keywords(f"{key} {value.get('value', '')}")
    }
    return {
        "current": current_subset,
        "items": limited,
        "keywords": keywords,
        "matched_count": len(matched),
        "has_any_preferences": bool(current or events),
    }


def build_widget_payload(storage: AIBundleStorage, user_id: str | None) -> Dict[str, Any]:
    view = get_preferences_view(storage, user_id, recency=15)
    return {
        "user_id": user_id or "anonymous",
        "current": view["current"],
        "recent": view["items"],
        "matched_count": view["matched_count"],
    }

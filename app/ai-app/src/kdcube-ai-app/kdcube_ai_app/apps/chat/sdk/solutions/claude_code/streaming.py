# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

from __future__ import annotations

from typing import Any

from kdcube_ai_app.infra.accounting.usage import _norm_usage_dict

CLAUDE_CODE_PROVIDER = "anthropic"

_CLAUDE_CODE_MODEL_ALIASES = {
    "sonnet": "claude-sonnet-4-6",
    "claude-sonnet": "claude-sonnet-4-6",
    "sonnet-4.6": "claude-sonnet-4-6",
    "sonnet-4-6": "claude-sonnet-4-6",
    "claude-sonnet-4.6": "claude-sonnet-4-6",
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
    "best": "claude-opus-4-6",
    "claude-opus": "claude-opus-4-6",
    "opus-4.6": "claude-opus-4-6",
    "opus-4-6": "claude-opus-4-6",
    "claude-opus-4.6": "claude-opus-4-6",
    "claude-opus-4-6": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5-20251001",
    "claude-haiku": "claude-haiku-4-5-20251001",
    "haiku-4.5": "claude-haiku-4-5-20251001",
    "haiku-4-5": "claude-haiku-4-5-20251001",
    "claude-haiku-4.5": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
}


def extract_text_from_claude_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(part for part in (extract_text_from_claude_content(item) for item in value) if part)
    if not isinstance(value, dict):
        return ""

    if isinstance(value.get("text"), str):
        return value["text"]

    for key in ("content", "message", "delta", "result"):
        if key in value:
            text = extract_text_from_claude_content(value[key])
            if text:
                return text
    return ""


def extract_text_from_claude_event(value: Any) -> str:
    if not isinstance(value, dict):
        return ""

    for key in ("text", "completion", "message", "delta", "result", "content"):
        if key in value:
            text = extract_text_from_claude_content(value[key])
            if text:
                return text
    return ""


def compute_incremental_chunk(previous_snapshot: str, new_text: str) -> tuple[str, str]:
    if not new_text:
        return previous_snapshot, ""
    if not previous_snapshot:
        return new_text, new_text
    if new_text.startswith(previous_snapshot):
        return new_text, new_text[len(previous_snapshot):]

    common_prefix = 0
    for prev_char, next_char in zip(previous_snapshot, new_text):
        if prev_char != next_char:
            break
        common_prefix += 1
    return new_text, new_text[common_prefix:]


def accumulate_transcript(
    transcript: str,
    previous_snapshot: str,
    new_text: str,
    *,
    separator: str = "\n\n",
) -> tuple[str, str, str]:
    """
    Maintain a full transcript across Claude Code partial snapshots.

    Claude Code often emits cumulative snapshots for one logical assistant
    message. Sometimes it emits a new logical message whose text no longer
    extends the previous snapshot. In that case we keep the previous snapshot
    in the transcript and start a new live snapshot instead of replacing the
    whole output.

    Returns:
    - updated transcript
    - updated live snapshot
    - incremental chunk to emit to the UI
    """
    if not new_text:
        return transcript, previous_snapshot, ""

    if not previous_snapshot:
        return transcript, new_text, new_text

    if new_text.startswith(previous_snapshot):
        return transcript, new_text, new_text[len(previous_snapshot):]

    base = transcript
    if previous_snapshot:
        base = f"{base}{separator}{previous_snapshot}" if base else previous_snapshot

    emit_prefix = separator if base else ""
    return base, new_text, f"{emit_prefix}{new_text}"


def normalize_claude_code_model(value: Any) -> str | None:
    if not value:
        return None
    model = str(value).strip()
    if not model:
        return None
    lowered = model.lower()
    return _CLAUDE_CODE_MODEL_ALIASES.get(lowered, model)


def extract_model_from_claude_event(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None

    candidates = [value.get("model")]
    message = value.get("message")
    if isinstance(message, dict):
        candidates.append(message.get("model"))
    result = value.get("result")
    if isinstance(result, dict):
        candidates.append(result.get("model"))

    for candidate in candidates:
        normalized = normalize_claude_code_model(candidate)
        if normalized:
            return normalized
    return None


def extract_usage_from_claude_event(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    candidates: list[Any] = [value.get("usage")]
    message = value.get("message")
    if isinstance(message, dict):
        candidates.append(message.get("usage"))
    result = value.get("result")
    if isinstance(result, dict):
        candidates.append(result.get("usage"))

    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return None


def extract_result_metrics_from_claude_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    result_dict = value.get("result") if isinstance(value.get("result"), dict) else None
    container = result_dict if result_dict is not None else value

    out: dict[str, Any] = {}
    for key in ("duration_ms", "duration_api_ms", "api_duration_ms"):
        metric = container.get(key)
        if metric is not None:
            try:
                out[key] = int(metric)
            except Exception:
                pass

    for key in ("total_cost_usd", "cost_usd", "cost"):
        raw = container.get(key)
        if raw is None:
            continue
        try:
            out["cost_usd"] = float(raw)
            break
        except Exception:
            continue

    return out


def is_usage_bearing_message_event(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    event_type = str(value.get("type") or "").strip().lower()
    return event_type in {"assistant", "user"}


def is_result_event(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    event_type = str(value.get("type") or "").strip().lower()
    return event_type == "result"


def accumulate_usage(
    current: dict[str, Any] | None,
    usage_payload: dict[str, Any],
    *,
    default_requests: int = 1,
) -> dict[str, Any]:
    current = dict(current or {})
    normalized = _norm_usage_dict(usage_payload or {})

    current["input_tokens"] = int(current.get("input_tokens", 0) or 0) + int(normalized.get("input_tokens", 0) or 0)
    current["output_tokens"] = int(current.get("output_tokens", 0) or 0) + int(normalized.get("output_tokens", 0) or 0)
    current["thinking_tokens"] = int(current.get("thinking_tokens", 0) or 0) + int(normalized.get("thinking_tokens", 0) or 0)
    current["cache_creation_tokens"] = int(current.get("cache_creation_tokens", 0) or 0) + int(normalized.get("cache_creation_input_tokens", 0) or 0)
    current["cache_read_tokens"] = int(current.get("cache_read_tokens", 0) or 0) + int(normalized.get("cache_read_input_tokens", 0) or 0)
    current["total_tokens"] = int(current.get("total_tokens", 0) or 0) + int(normalized.get("total_tokens", 0) or 0)

    current_cache_creation = current.get("cache_creation")
    if not isinstance(current_cache_creation, dict):
        current_cache_creation = {}
    new_cache_creation = normalized.get("cache_creation")
    if isinstance(new_cache_creation, dict):
        for key, raw in new_cache_creation.items():
            try:
                current_cache_creation[key] = int(current_cache_creation.get(key, 0) or 0) + int(raw or 0)
            except Exception:
                continue
    if current_cache_creation:
        current["cache_creation"] = current_cache_creation

    if "cost_usd" in usage_payload and usage_payload.get("cost_usd") is not None:
        try:
            current["cost_usd"] = float(current.get("cost_usd", 0.0) or 0.0) + float(usage_payload.get("cost_usd") or 0.0)
        except Exception:
            pass

    requests = usage_payload.get("requests")
    try:
        requests_int = int(requests) if requests is not None else int(default_requests)
    except Exception:
        requests_int = int(default_requests)
    current["requests"] = int(current.get("requests", 0) or 0) + max(requests_int, 0)

    return current

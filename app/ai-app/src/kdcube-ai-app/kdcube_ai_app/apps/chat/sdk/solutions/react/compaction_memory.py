from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List

MAX_PROMOTED_INTERNAL_NOTES = 32
MAX_PREFERENCE_DIGEST_LINES = 12

_NOTE_TAG_RE = re.compile(r"^\[(?P<tag>[A-Z])\]\s*")


@dataclass(frozen=True)
class InternalNoteCompactionResult:
    preserved_blocks: List[Dict[str, Any]]
    summary_text: str


def _clone_preserved_internal_note_block(
    *,
    block: Dict[str, Any],
    preserved_path: str,
    source_path: str,
) -> Dict[str, Any]:
    cloned = dict(block or {})
    meta = dict(cloned.get("meta") or {})
    meta.pop("replacement_text", None)
    meta["source_path"] = source_path
    meta["preserved_by_compaction"] = True
    cloned["type"] = "react.note.preserved"
    cloned["path"] = preserved_path
    cloned["hidden"] = False
    cloned.pop("replacement_text", None)
    cloned["meta"] = meta
    return cloned


def _parse_note_tag(text: str) -> str:
    match = _NOTE_TAG_RE.match(text or "")
    return (match.group("tag") if match else "").strip().upper()


def _strip_note_tag(text: str) -> str:
    return _NOTE_TAG_RE.sub("", text or "", count=1).strip()


def _normalize_digest_text(text: str) -> str:
    compact = " ".join((text or "").split()).strip()
    if len(compact) <= 220:
        return compact
    return compact[:217].rstrip() + "..."


def _build_preference_digest_block(entries: List[Dict[str, Any]]) -> str:
    if not entries:
        return ""
    lines: List[str] = []
    seen: set[str] = set()
    for entry in reversed(entries):
        body = _normalize_digest_text(str(entry.get("body") or ""))
        if not body or body in seen:
            continue
        seen.add(body)
        lines.append(f"- {body}")
        if len(lines) >= MAX_PREFERENCE_DIGEST_LINES:
            break
    if not lines:
        return ""
    return "\n".join(
        [
            "[INTERNAL MEMORY DIGEST]",
            "Active conversation preferences:",
            *lines,
        ]
    )


def _merge_summary_with_preference_digest(summary_text: str, digest_block: str) -> str:
    summary_clean = (summary_text or "").strip()
    digest_clean = (digest_block or "").strip()
    if not digest_clean:
        return summary_clean
    if not summary_clean:
        return digest_clean
    if digest_clean in summary_clean:
        return summary_clean
    return f"{summary_clean}\n\n{digest_clean}"


def build_internal_note_compaction_result(
    *,
    blocks: List[Dict[str, Any]],
    turn_id: str,
    summary_text: str,
    max_promoted_notes: int = MAX_PROMOTED_INTERNAL_NOTES,
) -> InternalNoteCompactionResult:
    entries: Dict[str, Dict[str, Any]] = {}
    for order, blk in enumerate(blocks or []):
        if not isinstance(blk, dict):
            continue
        btype = (blk.get("type") or "").strip()
        if btype not in {"react.note", "react.note.preserved"}:
            continue
        text = (blk.get("text") or "").strip() if isinstance(blk.get("text"), str) else ""
        if not text:
            continue
        meta = blk.get("meta") if isinstance(blk.get("meta"), dict) else {}
        source_path = (meta.get("source_path") or blk.get("path") or "").strip()
        key = source_path or text
        entries[key] = {
            "order": order,
            "block": blk,
            "source_path": source_path,
            "tag": _parse_note_tag(text),
            "body": _strip_note_tag(text),
        }

    if not entries:
        return InternalNoteCompactionResult(
            preserved_blocks=[],
            summary_text=(summary_text or "").strip(),
        )

    ordered = sorted(entries.values(), key=lambda item: int(item.get("order") or 0))
    capped = ordered[-max_promoted_notes:] if max_promoted_notes > 0 else []

    preserved: List[Dict[str, Any]] = []
    for idx, entry in enumerate(capped, start=1):
        blk = entry.get("block") if isinstance(entry.get("block"), dict) else None
        if not blk:
            continue
        preserved_path = f"ar:{turn_id}.react.note.preserved.{idx}" if turn_id else ""
        preserved.append(
            _clone_preserved_internal_note_block(
                block=blk,
                preserved_path=preserved_path,
                source_path=str(entry.get("source_path") or "").strip(),
            )
        )

    preference_entries = [entry for entry in ordered if entry.get("tag") == "P" and entry.get("body")]
    digest_block = _build_preference_digest_block(preference_entries)
    merged_summary = _merge_summary_with_preference_digest(summary_text, digest_block)
    return InternalNoteCompactionResult(
        preserved_blocks=preserved,
        summary_text=merged_summary,
    )

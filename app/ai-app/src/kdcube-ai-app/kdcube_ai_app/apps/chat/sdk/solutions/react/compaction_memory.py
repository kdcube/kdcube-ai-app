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
    tags: List[str] | None = None,
) -> Dict[str, Any]:
    cloned = dict(block or {})
    meta = dict(cloned.get("meta") or {})
    meta.pop("replacement_text", None)
    meta["source_path"] = source_path
    meta["preserved_by_compaction"] = True
    if tags:
        meta["note_tags"] = tags
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


def _split_note_beacons(text: str) -> List[Dict[str, Any]]:
    """Split a react.note body into tagged beacon entries.

    A single react.write(content=...) can contain several beacon lines. This
    split is used only for tag and digest extraction; note preservation remains
    block-level, with the authored text kept together. Lines beginning with
    [P]/[D]/[S]/[A]/[K] start a tagged segment; following untagged lines are
    treated as continuation text for that segment. If the text has no tagged
    lines, keep the whole body as one untagged entry.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    entries: List[Dict[str, Any]] = []
    current: List[str] = []
    current_line_index = 1
    saw_tag = False
    for idx, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            if current:
                current.append(line)
            continue
        if _parse_note_tag(stripped):
            saw_tag = True
            if current:
                body = "\n".join(current).strip()
                if body:
                    entries.append({"text": body, "line_index": current_line_index})
            current = [stripped]
            current_line_index = idx
        elif current:
            current.append(line)
    if current:
        body = "\n".join(current).strip()
        if body:
            entries.append({"text": body, "line_index": current_line_index})
    if saw_tag:
        return entries
    return [{"text": raw, "line_index": 1}]


def _extract_note_tags(text: str) -> List[str]:
    tags: List[str] = []
    seen: set[str] = set()
    for segment in _split_note_beacons(text):
        tag = _parse_note_tag(str(segment.get("text") or "").strip())
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return tags


def extract_note_tags(text: str) -> List[str]:
    """Return ordered unique bracket tags used by an internal note body."""
    return _extract_note_tags(text)


def _preference_bodies_from_note(text: str) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for segment in _split_note_beacons(text):
        segment_text = str(segment.get("text") or "").strip()
        if _parse_note_tag(segment_text) != "P":
            continue
        body = _strip_note_tag(segment_text)
        if not body or body in seen:
            continue
        seen.add(body)
        out.append(body)
    return out


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
        for raw_body in reversed(entry.get("preference_bodies") or []):
            body = _normalize_digest_text(str(raw_body or ""))
            if not body or body in seen:
                continue
            seen.add(body)
            lines.append(f"- {body}")
            if len(lines) >= MAX_PREFERENCE_DIGEST_LINES:
                break
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
            "tags": _extract_note_tags(text),
            "preference_bodies": _preference_bodies_from_note(text),
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
                tags=[str(t) for t in (entry.get("tags") or []) if str(t or "").strip()],
            )
        )

    preference_entries = [entry for entry in capped if entry.get("preference_bodies")]
    digest_block = _build_preference_digest_block(preference_entries)
    merged_summary = _merge_summary_with_preference_digest(summary_text, digest_block)
    return InternalNoteCompactionResult(
        preserved_blocks=preserved,
        summary_text=merged_summary,
    )

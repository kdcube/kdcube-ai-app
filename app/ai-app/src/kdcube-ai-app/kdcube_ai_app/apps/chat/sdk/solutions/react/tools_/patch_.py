# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import json
import os
import pathlib
import re
import time

from kdcube_ai_app.apps.chat.sdk.solutions.react.tools.common import (
    tool_call_block,
    run_post_patch_check,
    notice_block,
    add_block,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.artifacts import build_artifact_meta_block

BEGIN_PATCH_MARKER = "*** Begin Patch"
END_PATCH_MARKER = "*** End Patch"
ADD_FILE_MARKER = "*** Add File: "
DELETE_FILE_MARKER = "*** Delete File: "
UPDATE_FILE_MARKER = "*** Update File: "
MOVE_TO_MARKER = "*** Move to: "
EOF_MARKER = "*** End of File"
CHANGE_CONTEXT_MARKER = "@@ "
EMPTY_CHANGE_CONTEXT_MARKER = "@@"
UNICODE_SPACES_RE = re.compile(r"[\u00A0\u2000-\u200A\u202F\u205F\u3000]")

DOC = {
    "id": "react.patch",
    "purpose": (
        "Apply a multi-file patch using the apply_patch format (*** Begin Patch/End Patch). "
        "Supports add, delete, update, and move hunks in a single patch. "
        "Paths inside the patch are resolved relative to OUT_DIR/<turn_id>/files/. "
        "Use this to modify multiple files at once or to add/delete/move files."
    ),
    "args": {
        "path": (
            "str (FIRST FIELD). Compatibility placeholder; ignored by react.apply_patch. "
            "Files are determined by the patch content itself."
        ),
        "channel": (
            "str (SECOND FIELD). Compatibility placeholder; ignored by react.apply_patch. "
            "Use 'canvas' or 'timeline_text' for UI consistency in logs."
        ),
        "patch": (
            "str (THIRD FIELD). The patch content. This SHOULD be in apply_patch format: "
            "*** Begin Patch, then one or more hunks using *** Add File / *** Delete File / *** Update File, "
            "optionally *** Move to, and ending with *** End Patch."
        ),
        "kind": (
            "str (FOURTH FIELD). Compatibility placeholder; ignored by react.apply_patch. "
            "Use 'display' or 'file' to match prior tooling conventions."
        ),
        "input": (
            "str (ALIAS). Preferred field for the patch content; if present it takes precedence over patch."
        ),
    },
    "returns": "summary of applied changes",
    "constraints": [
        "`path` must appear first in the params JSON object (compatibility).",
        "`channel` must appear second in the params JSON object (compatibility).",
        "`patch` must appear third in the params JSON object (or use `input`).",
        "`kind` must appear fourth in the params JSON object (compatibility).",
    ],
    "patch_format": {
        "start": "*** Begin Patch",
        "hunks": [
            "*** Add File: <path> (then lines starting with '+')",
            "*** Delete File: <path>",
            "*** Update File: <path> (optional *** Move to: <path>, then @@ context and +/-/ space lines)",
        ],
        "end": "*** End Patch",
    },
}


class PatchError(ValueError):
    pass


@dataclass
class AddFileHunk:
    path: str
    contents: str
    kind: str = "add"


@dataclass
class DeleteFileHunk:
    path: str
    kind: str = "delete"


@dataclass
class UpdateFileChunk:
    old_lines: List[str]
    new_lines: List[str]
    change_context: Optional[str] = None
    is_end_of_file: bool = False


@dataclass
class UpdateFileHunk:
    path: str
    chunks: List[UpdateFileChunk]
    move_path: Optional[str] = None
    kind: str = "update"


Hunk = Union[AddFileHunk, DeleteFileHunk, UpdateFileHunk]


@dataclass
class ApplyPatchSummary:
    added: List[str]
    modified: List[str]
    deleted: List[str]


@dataclass
class ApplyPatchResult:
    summary: ApplyPatchSummary
    text: str


def _is_safe_relpath(path_value: str) -> bool:
    try:
        p = pathlib.PurePosixPath(path_value)
        if path_value.startswith(("/", "\\")):
            return False
        if any(part == ".." for part in p.parts):
            return False
        return True
    except Exception:
        return False


def _normalize_unicode_spaces(value: str) -> str:
    return UNICODE_SPACES_RE.sub(" ", value)


def _expand_path(file_path: str) -> str:
    normalized = _normalize_unicode_spaces(file_path)
    if normalized == "~":
        return os.path.expanduser(normalized)
    if normalized.startswith("~/"):
        return os.path.expanduser(normalized)
    return normalized


def _resolve_patch_path(file_path: str, base_dir: pathlib.Path) -> Tuple[pathlib.Path, str]:
    expanded = _expand_path(file_path)
    if os.path.isabs(expanded):
        raise PatchError("Absolute paths are not allowed in apply_patch.")
    if not _is_safe_relpath(expanded):
        raise PatchError("Unsafe path in apply_patch.")
    base_resolved = base_dir.resolve()
    resolved = (base_dir / expanded).resolve()
    if str(resolved) != str(base_resolved) and not str(resolved).startswith(
        f"{base_resolved}{os.sep}"):
        raise PatchError("Path escapes base directory.")
    display = os.path.relpath(resolved, base_resolved)
    return resolved, display


def _ensure_dir(file_path: pathlib.Path) -> None:
    parent = file_path.parent
    if not parent or str(parent) == ".":
        return
    parent.mkdir(parents=True, exist_ok=True)


def _record_summary(summary: ApplyPatchSummary, seen: Dict[str, set], bucket: str, value: str) -> None:
    if value in seen[bucket]:
        return
    seen[bucket].add(value)
    getattr(summary, bucket).append(value)


def _format_summary(summary: ApplyPatchSummary) -> str:
    lines = ["Success. Updated the following files:"]
    for file_path in summary.added:
        lines.append(f"A {file_path}")
    for file_path in summary.modified:
        lines.append(f"M {file_path}")
    for file_path in summary.deleted:
        lines.append(f"D {file_path}")
    return "\n".join(lines)


def apply_patch(input_text: str, base_dir: pathlib.Path) -> ApplyPatchResult:
    hunks = _parse_patch_text(input_text)
    summary = ApplyPatchSummary(added=[], modified=[], deleted=[])
    seen = {"added": set(), "modified": set(), "deleted": set()}
    for hunk in hunks:
        if isinstance(hunk, AddFileHunk):
            file_path, display = _resolve_patch_path(hunk.path, base_dir)
            _ensure_dir(file_path)
            file_path.write_text(hunk.contents, encoding="utf-8")
            _record_summary(summary, seen, "added", display)
            continue
        if isinstance(hunk, DeleteFileHunk):
            file_path, display = _resolve_patch_path(hunk.path, base_dir)
            if file_path.exists():
                file_path.unlink()
            _record_summary(summary, seen, "deleted", display)
            continue
        if isinstance(hunk, UpdateFileHunk):
            file_path, display = _resolve_patch_path(hunk.path, base_dir)
            current = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            updated = _apply_update(current, hunk)
            target_path = file_path
            if hunk.move_path:
                target_path, display = _resolve_patch_path(hunk.move_path, base_dir)
                _ensure_dir(target_path)
                if target_path != file_path and file_path.exists():
                    file_path.unlink()
            _ensure_dir(target_path)
            target_path.write_text(updated, encoding="utf-8")
            _record_summary(summary, seen, "modified", display)
            continue
    return ApplyPatchResult(summary=summary, text=_format_summary(summary))


def _parse_patch_text(input_text: str) -> List[Hunk]:
    lines = input_text.splitlines()
    if not lines or lines[0] != BEGIN_PATCH_MARKER:
        raise PatchError("Patch must start with *** Begin Patch.")
    idx = 1
    hunks: List[Hunk] = []
    while idx < len(lines):
        line = lines[idx]
        if line == END_PATCH_MARKER:
            return hunks
        if line.startswith(ADD_FILE_MARKER):
            path = line[len(ADD_FILE_MARKER):]
            idx += 1
            buf: List[str] = []
            while idx < len(lines) and not lines[idx].startswith("*** "):
                raw = lines[idx]
                if not raw.startswith("+"):
                    raise PatchError("Add File lines must start with '+'.")
                buf.append(raw[1:])
                idx += 1
            hunks.append(AddFileHunk(path=path, contents="\n".join(buf) + ("\n" if buf else "")))
            continue
        if line.startswith(DELETE_FILE_MARKER):
            path = line[len(DELETE_FILE_MARKER):]
            hunks.append(DeleteFileHunk(path=path))
            idx += 1
            continue
        if line.startswith(UPDATE_FILE_MARKER):
            path = line[len(UPDATE_FILE_MARKER):]
            idx += 1
            move_path: Optional[str] = None
            if idx < len(lines) and lines[idx].startswith(MOVE_TO_MARKER):
                move_path = lines[idx][len(MOVE_TO_MARKER):]
                idx += 1
            chunks: List[UpdateFileChunk] = []
            current_old: List[str] = []
            current_new: List[str] = []
            current_ctx: Optional[str] = None
            while idx < len(lines):
                current = lines[idx]
                if current == END_PATCH_MARKER or current.startswith(("*** Add File: ", "*** Delete File: ", "*** Update File: ")):
                    break
                if current in {EMPTY_CHANGE_CONTEXT_MARKER} or current.startswith(CHANGE_CONTEXT_MARKER):
                    if current_old or current_new or current_ctx is not None:
                        chunks.append(UpdateFileChunk(old_lines=current_old, new_lines=current_new, change_context=current_ctx))
                        current_old, current_new = [], []
                    current_ctx = None if current == EMPTY_CHANGE_CONTEXT_MARKER else current[len(CHANGE_CONTEXT_MARKER):]
                    idx += 1
                    continue
                if current == EOF_MARKER:
                    chunks.append(UpdateFileChunk(old_lines=current_old, new_lines=current_new, change_context=current_ctx, is_end_of_file=True))
                    current_old, current_new, current_ctx = [], [], None
                    idx += 1
                    continue
                if current.startswith("-"):
                    current_old.append(current[1:])
                elif current.startswith("+"):
                    current_new.append(current[1:])
                elif current.startswith(" "):
                    current_old.append(current[1:])
                    current_new.append(current[1:])
                else:
                    raise PatchError(f"Unexpected line in update hunk: {current}")
                idx += 1
            if current_old or current_new or current_ctx is not None:
                chunks.append(UpdateFileChunk(old_lines=current_old, new_lines=current_new, change_context=current_ctx))
            hunks.append(UpdateFileHunk(path=path, chunks=chunks, move_path=move_path))
            continue
        raise PatchError(f"Unexpected patch line: {line}")
    raise PatchError("Patch must end with *** End Patch.")


def _apply_update(current: str, hunk: UpdateFileHunk) -> str:
    lines = current.splitlines()
    offset = 0
    for chunk in hunk.chunks:
        if chunk.change_context:
            start = _find_context(lines, chunk.change_context)
            if start is None:
                raise PatchError(f"Context not found: {chunk.change_context}")
        else:
            start = 0 if not chunk.old_lines else _find_sequence(lines, chunk.old_lines)
            if start is None:
                raise PatchError("Update sequence not found.")
        end = start + len(chunk.old_lines)
        if lines[start:end] != chunk.old_lines:
            raise PatchError("Update chunk mismatch.")
        lines[start:end] = chunk.new_lines
        offset += len(chunk.new_lines) - len(chunk.old_lines)
    result = "\n".join(lines)
    if current.endswith("\n") or any(chunk.is_end_of_file for chunk in hunk.chunks):
        result += "\n"
    return result


def _find_context(lines: List[str], context: str) -> Optional[int]:
    for idx, line in enumerate(lines):
        if line == context:
            return idx
    return None


def _find_sequence(lines: List[str], needle: List[str]) -> Optional[int]:
    if not needle:
        return 0
    limit = len(lines) - len(needle) + 1
    for idx in range(max(limit, 0)):
        if lines[idx:idx + len(needle)] == needle:
            return idx
    return None

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Staged inbound files for integration actions.

The mirror of the signed download URL: an external agent asks the namespace
for an upload slot (``request_upload``), PUTs the bytes to the returned signed
URL over plain HTTP — never through the model's context — and then references
the returned ``staged:`` ref in ``send``/``upload_file`` payloads. The adapter
resolves the staged bytes into the tool workspace at action time and deletes
them after use (single-use refs with a short TTL sweep as backstop).
"""

from __future__ import annotations

import pathlib
import shutil
import tempfile
import time
import uuid

STAGED_REF_PREFIX = "staged:"
STAGED_TTL_SECONDS = 3600
MAX_STAGED_FILE_BYTES = 25 * 1024 * 1024
_STAGING_DIRNAME = "kdcube-integration-staging"


def _safe_filename(raw: str) -> str:
    name = pathlib.PurePosixPath(str(raw or "").replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        raise ValueError("A staged file needs a plain filename (no directories).")
    return name


def staging_root(storage_path: str = "") -> pathlib.Path:
    """Directory staged files live in until an action consumes them.

    Prefers a local ``STORAGE_PATH`` (shared by all proc workers on the host);
    falls back to the system temp dir. Upload route and action resolution must
    agree on this, so both derive it from the same entrypoint settings.
    """
    base = str(storage_path or "").strip()
    if base and "://" not in base:
        root = pathlib.Path(base) / _STAGING_DIRNAME
    else:
        root = pathlib.Path(tempfile.gettempdir()) / _STAGING_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_staged_ref(filename: str) -> str:
    return f"{STAGED_REF_PREFIX}{uuid.uuid4().hex}:{_safe_filename(filename)}"


def parse_staged_ref(ref: str) -> tuple[str, str]:
    """``staged:<id>:<filename>`` -> (id, filename); raises ValueError otherwise."""
    text = str(ref or "").strip()
    if not text.startswith(STAGED_REF_PREFIX):
        raise ValueError(f"not a staged ref: {text!r}")
    rest = text[len(STAGED_REF_PREFIX):]
    staged_id, _, filename = rest.partition(":")
    if not staged_id or not filename:
        raise ValueError(f"malformed staged ref: {text!r}")
    return staged_id, _safe_filename(filename)


def _staged_path(root: pathlib.Path, staged_id: str, filename: str) -> pathlib.Path:
    return pathlib.Path(root) / staged_id / filename


def save_staged(root: pathlib.Path, staged_ref: str, data: bytes) -> pathlib.Path:
    if len(data) > MAX_STAGED_FILE_BYTES:
        raise ValueError(f"staged file exceeds the {MAX_STAGED_FILE_BYTES}-byte limit")
    staged_id, filename = parse_staged_ref(staged_ref)
    target = _staged_path(root, staged_id, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    sweep_expired(root)
    return target


def load_staged(root: pathlib.Path, staged_ref: str) -> tuple[str, bytes]:
    """Return ``(filename, bytes)`` for one staged ref; raises FileNotFoundError."""
    staged_id, filename = parse_staged_ref(staged_ref)
    target = _staged_path(root, staged_id, filename)
    if not target.is_file():
        raise FileNotFoundError(
            f"staged file not found (expired, already used, or never uploaded): {staged_ref}"
        )
    return filename, target.read_bytes()


def delete_staged(root: pathlib.Path, staged_ref: str) -> None:
    try:
        staged_id, _filename = parse_staged_ref(staged_ref)
    except ValueError:
        return
    shutil.rmtree(pathlib.Path(root) / staged_id, ignore_errors=True)


def sweep_expired(root: pathlib.Path, *, ttl_seconds: int = STAGED_TTL_SECONDS) -> None:
    """Best-effort removal of staged dirs older than the TTL."""
    cutoff = time.time() - max(60, int(ttl_seconds))
    try:
        for entry in pathlib.Path(root).iterdir():
            try:
                if entry.is_dir() and entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                continue
    except OSError:
        pass


__all__ = [
    "MAX_STAGED_FILE_BYTES",
    "STAGED_REF_PREFIX",
    "STAGED_TTL_SECONDS",
    "delete_staged",
    "load_staged",
    "new_staged_ref",
    "parse_staged_ref",
    "save_staged",
    "staging_root",
    "sweep_expired",
]

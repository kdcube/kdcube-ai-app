# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Canonical references and paths for the agent-harness turn workspace.

This module owns the relationship between durable conversation file refs
(``conv:fi:...``) and paths in the distributed per-turn workspace. It is
framework-neutral: ReAct, ported agents, chat, canvas, and integrations all
consume the same grammar.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any


CONVERSATION_NAMESPACE = "conv"
CONVERSATION_FILE_NAMESPACE = "fi"
CONVERSATION_FILE_REF_PREFIX = (
    f"{CONVERSATION_NAMESPACE}:{CONVERSATION_FILE_NAMESPACE}:"
)

ARTIFACT_NAMESPACE_PROJECTS = "git/projects"
ARTIFACT_NAMESPACE_FILES = "files"
ARTIFACT_NAMESPACE_ATTACHMENTS = "attachments"
ARTIFACT_NAMESPACE_SNAPSHOTS = "git/snapshots"
ARTIFACT_EXTERNAL_PREFIX = "external/"
ARTIFACT_CONVERSATION_PREFIX = "conv_"

_TIMESTAMP_TURN_ID_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}(?:-\d{2})?(?:-\d{3,6})?$"
)
_EXTERNAL_LOGICAL_RE = re.compile(
    r"^(?P<turn>[^.]+)\.external\.(?P<event_kind>[^.]+)\.attachments/"
    r"(?P<message_id>[^/]+)/(?P<rel>.+)$"
)
_EXTERNAL_PHYSICAL_RE = re.compile(
    r"^(?P<turn>[^/]+)/external/(?P<event_kind>[^/]+)/attachments/"
    r"(?P<message_id>[^/]+)/(?P<rel>.+)$"
)
_LOGICAL_ARTIFACT_NAMESPACES = (
    ARTIFACT_NAMESPACE_PROJECTS,
    ARTIFACT_NAMESPACE_SNAPSHOTS,
    ARTIFACT_NAMESPACE_FILES,
    ARTIFACT_NAMESPACE_ATTACHMENTS,
)


def is_turn_id(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    return (
        raw.startswith("turn_")
        or raw.startswith("telegram_turn_")
        or bool(_TIMESTAMP_TURN_ID_RE.fullmatch(raw))
    )


def _split_external_attachment_rel(relpath: str) -> tuple[str, str, str]:
    rel = (relpath or "").strip().lstrip("/")
    if not rel.startswith(ARTIFACT_EXTERNAL_PREFIX):
        return "", "", ""
    parts = [part for part in rel.split("/") if part]
    if len(parts) >= 5 and parts[0] == "external" and parts[2] == "attachments":
        kind = parts[1]
        message_id = parts[3]
        file_rel = "/".join(parts[4:])
        if kind and message_id and file_rel:
            return kind, message_id, file_rel
    return "", "", ""


def _conversation_segment(conversation_id: str = "") -> str:
    raw = str(conversation_id or "").strip().strip("/")
    if not raw:
        return ""
    if "." in raw or "/" in raw or "\\" in raw:
        return ""
    return f"{ARTIFACT_CONVERSATION_PREFIX}{raw}"


def _split_logical_conversation_prefix(raw_value: str) -> tuple[str, str]:
    raw = str(raw_value or "").strip()
    if raw.startswith(CONVERSATION_FILE_REF_PREFIX):
        raw = raw[len(CONVERSATION_FILE_REF_PREFIX) :]
    if not raw.startswith(ARTIFACT_CONVERSATION_PREFIX):
        return "", raw
    segment, sep, rest = raw.partition(".")
    if not sep or not rest:
        return "", raw
    conversation_id = segment[len(ARTIFACT_CONVERSATION_PREFIX) :].strip()
    return conversation_id, rest


def peel_conversation_prefix(path: str) -> tuple[str, str, str]:
    """Peel an optional ``conv_<id>.`` owner segment from a ``conv:*`` ref.

    Returns ``(namespace_prefix, conversation_id, unscoped_ref)``.
    ``conv_<id>`` remains part of the canonical ref grammar; it identifies the
    owning conversation and is independent of the leading ``conv:`` namespace.
    """
    raw = str(path or "").strip()
    if not raw:
        return "", "", raw
    if not raw.startswith(f"{CONVERSATION_NAMESPACE}:"):
        return "", "", raw
    _, _, rest = raw.partition(":")
    ns_letters, sep, body = rest.partition(":")
    if not sep or not ns_letters:
        return "", "", raw
    if not ns_letters.isalpha() or not ns_letters.islower():
        return "", "", raw
    namespace_prefix = f"{CONVERSATION_NAMESPACE}:{ns_letters}:"
    if not body.startswith(ARTIFACT_CONVERSATION_PREFIX):
        return namespace_prefix, "", raw
    segment, sep, remainder = body.partition(".")
    if not sep or not remainder:
        return namespace_prefix, "", raw
    conversation_id = segment[len(ARTIFACT_CONVERSATION_PREFIX) :].strip()
    if not conversation_id:
        return namespace_prefix, "", raw
    return namespace_prefix, conversation_id, f"{namespace_prefix}{remainder}"


def qualify_conversation_ref(ref: str, conversation_id: str) -> str:
    """Add the canonical ``conv_<conversation_id>.`` owner segment to a ref."""
    raw = str(ref or "").strip()
    conv_id = str(conversation_id or "").strip()
    if not raw or not conv_id:
        return ref
    if not _conversation_segment(conv_id):
        return ref
    namespace_prefix, existing_conversation, _ = peel_conversation_prefix(raw)
    if not namespace_prefix or existing_conversation:
        return ref
    body = raw[len(namespace_prefix) :]
    if not body:
        return ref
    return (
        f"{namespace_prefix}{ARTIFACT_CONVERSATION_PREFIX}{conv_id}.{body}"
    )


def localize_conversation_ref(ref: str, current_conversation_id: str) -> str:
    """Remove the owner segment only when it names the current conversation."""
    raw = str(ref or "").strip()
    current = str(current_conversation_id or "").strip()
    if not raw or not current:
        return ref
    namespace_prefix, embedded_conversation, unscoped = peel_conversation_prefix(
        raw
    )
    if not namespace_prefix or not embedded_conversation:
        return ref
    if embedded_conversation != current:
        return ref
    return unscoped


_CONV_REF_BODY_STARTS = (
    r"(?:telegram_)?turn_",
    r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}",
    r"sources_pool\[",
    r"plan\.latest:",
)
_CONV_REF_QUALIFY_RE = re.compile(
    r"\bconv:([a-z]{2}):(?=(?:" + "|".join(_CONV_REF_BODY_STARTS) + r"))"
)


def qualify_conversation_refs_in_text(text: str, conversation_id: str) -> str:
    """Qualify conversation-owned refs embedded in free text."""
    raw = str(text or "")
    conv_id = str(conversation_id or "").strip()
    if not raw or not conv_id or "conv:" not in raw:
        return text
    if not _conversation_segment(conv_id):
        return text
    return _CONV_REF_QUALIFY_RE.sub(
        f"conv:\\1:{ARTIFACT_CONVERSATION_PREFIX}{conv_id}.",
        raw,
    )


def _split_physical_conversation_prefix(raw_value: str) -> tuple[str, str]:
    raw = str(raw_value or "").strip().lstrip("/")
    if not raw.startswith(ARTIFACT_CONVERSATION_PREFIX):
        return "", raw
    segment, sep, rest = raw.partition("/")
    if not sep or not rest:
        return "", raw
    conversation_id = segment[len(ARTIFACT_CONVERSATION_PREFIX) :].strip()
    return conversation_id, rest


def build_external_attachment_physical_path(
    *,
    turn_id: str,
    kind: str,
    message_id: str,
    relpath: str,
    conversation_id: str = "",
) -> str:
    rel = (relpath or "").strip().lstrip("/")
    if not turn_id or not kind or not message_id or not rel:
        return ""
    prefix = _conversation_segment(conversation_id)
    scoped = f"{turn_id}/external/{kind}/attachments/{message_id}/{rel}"
    return f"{prefix}/{scoped}" if prefix else scoped


def build_external_attachment_logical_path(
    *,
    turn_id: str,
    kind: str,
    message_id: str,
    relpath: str,
    conversation_id: str = "",
) -> str:
    rel = (relpath or "").strip().lstrip("/")
    if not turn_id or not kind or not message_id or not rel:
        return ""
    prefix = _conversation_segment(conversation_id)
    scoped = f"{turn_id}.external.{kind}.attachments/{message_id}/{rel}"
    return (
        f"{CONVERSATION_FILE_REF_PREFIX}{prefix}.{scoped}"
        if prefix
        else f"{CONVERSATION_FILE_REF_PREFIX}{scoped}"
    )


def build_physical_artifact_path(
    *,
    turn_id: str,
    namespace: str,
    relpath: str,
    conversation_id: str = "",
) -> str:
    rel = (relpath or "").strip().lstrip("/")
    if not turn_id or not namespace or not rel:
        return ""
    prefix = _conversation_segment(conversation_id)
    if namespace == ARTIFACT_NAMESPACE_ATTACHMENTS:
        kind, message_id, event_rel = _split_external_attachment_rel(rel)
        if kind and message_id and event_rel:
            return build_external_attachment_physical_path(
                turn_id=turn_id,
                kind=kind,
                message_id=message_id,
                relpath=event_rel,
                conversation_id=conversation_id,
            )
    scoped = f"{turn_id}/{namespace}/{rel}"
    return f"{prefix}/{scoped}" if prefix else scoped


def build_logical_artifact_path(
    *,
    turn_id: str,
    namespace: str,
    relpath: str,
    conversation_id: str = "",
) -> str:
    rel = (relpath or "").strip().lstrip("/")
    if not turn_id or not namespace or not rel:
        return ""
    prefix = _conversation_segment(conversation_id)
    turn_prefix = f"{prefix}.{turn_id}" if prefix else turn_id
    if namespace in {
        ARTIFACT_NAMESPACE_PROJECTS,
        ARTIFACT_NAMESPACE_FILES,
        ARTIFACT_NAMESPACE_SNAPSHOTS,
    }:
        return (
            f"{CONVERSATION_FILE_REF_PREFIX}{turn_prefix}.{namespace}/{rel}"
        )
    if namespace == ARTIFACT_NAMESPACE_ATTACHMENTS:
        kind, message_id, event_rel = _split_external_attachment_rel(rel)
        if kind and message_id and event_rel:
            return build_external_attachment_logical_path(
                turn_id=turn_id,
                kind=kind,
                message_id=message_id,
                relpath=event_rel,
                conversation_id=conversation_id,
            )
        return (
            f"{CONVERSATION_FILE_REF_PREFIX}{turn_prefix}."
            f"user.attachments/{rel}"
        )
    return ""


def split_physical_artifact_path(path_value: str) -> tuple[str, str, str]:
    raw = (path_value or "").strip().lstrip("/")
    _, raw = _split_physical_conversation_prefix(raw)
    if not raw:
        return "", "", ""
    match = _EXTERNAL_PHYSICAL_RE.match(raw)
    if match:
        turn_id = match.group("turn")
        kind = match.group("event_kind")
        message_id = match.group("message_id")
        rel = match.group("rel")
        if is_turn_id(turn_id) and kind and message_id and rel:
            return (
                turn_id,
                ARTIFACT_NAMESPACE_ATTACHMENTS,
                f"external/{kind}/attachments/{message_id}/{rel}",
            )
    for namespace in _LOGICAL_ARTIFACT_NAMESPACES:
        marker = f"/{namespace}/"
        if marker in raw:
            turn_id, rel = raw.split(marker, 1)
            if is_turn_id(turn_id) and rel:
                return turn_id, namespace, rel
    return "", "", ""


def split_physical_artifact_ref(
    path_value: str,
) -> tuple[str, str, str, str]:
    conversation_id, body = _split_physical_conversation_prefix(path_value)
    turn_id, namespace, rel = split_physical_artifact_path(body)
    return conversation_id, turn_id, namespace, rel


def _split_logical_artifact_body(raw_value: str) -> tuple[str, str, str]:
    raw = (raw_value or "").strip()
    if not raw:
        return "", "", ""
    match = _EXTERNAL_LOGICAL_RE.match(raw)
    if match:
        turn_id = match.group("turn")
        kind = match.group("event_kind")
        message_id = match.group("message_id")
        rel = match.group("rel")
        if is_turn_id(turn_id) and kind and message_id and rel:
            return (
                turn_id,
                ARTIFACT_NAMESPACE_ATTACHMENTS,
                f"external/{kind}/attachments/{message_id}/{rel}",
            )
    if ".user.attachments/" in raw:
        turn_id, rel = raw.split(".user.attachments/", 1)
        return turn_id, ARTIFACT_NAMESPACE_ATTACHMENTS, rel
    for namespace in _LOGICAL_ARTIFACT_NAMESPACES:
        marker = f".{namespace}/"
        if marker in raw:
            turn_id, rel = raw.split(marker, 1)
            if is_turn_id(turn_id) and rel:
                return turn_id, namespace, rel
    return "", "", ""


def split_logical_artifact_path(path_value: str) -> tuple[str, str, str]:
    raw = (path_value or "").strip()
    if not raw.startswith(CONVERSATION_FILE_REF_PREFIX):
        return "", "", ""
    _, body = _split_logical_conversation_prefix(raw)
    return _split_logical_artifact_body(body)


def split_logical_artifact_ref(
    path_value: str,
) -> tuple[str, str, str, str]:
    conversation_id, body = _split_logical_conversation_prefix(path_value)
    if str(path_value or "").strip().startswith(CONVERSATION_FILE_REF_PREFIX):
        turn_id, namespace, rel = _split_logical_artifact_body(body)
    else:
        turn_id, namespace, rel = "", "", ""
    return conversation_id, turn_id, namespace, rel


def logical_artifact_conversation_id(path_value: str) -> str:
    conversation_id, _, _, _ = split_logical_artifact_ref(path_value)
    return conversation_id


def unscoped_logical_artifact_path(path_value: str) -> str:
    _, turn_id, namespace, rel = split_logical_artifact_ref(path_value)
    if turn_id and namespace and rel:
        return build_logical_artifact_path(
            turn_id=turn_id,
            namespace=namespace,
            relpath=rel,
        )
    return str(path_value or "").strip()


def infer_artifact_namespace(
    path_value: str,
    *,
    default: str = ARTIFACT_NAMESPACE_FILES,
) -> str:
    raw = (path_value or "").strip()
    if not raw:
        return default
    _, namespace, _ = split_logical_artifact_path(raw)
    if namespace:
        return namespace
    _, namespace, _ = split_physical_artifact_path(raw)
    if namespace:
        return namespace
    if raw.startswith(f"{ARTIFACT_NAMESPACE_SNAPSHOTS}/"):
        return ARTIFACT_NAMESPACE_SNAPSHOTS
    if raw.startswith(f"{ARTIFACT_NAMESPACE_PROJECTS}/"):
        return ARTIFACT_NAMESPACE_PROJECTS
    if raw.startswith(f"{ARTIFACT_NAMESPACE_ATTACHMENTS}/"):
        return ARTIFACT_NAMESPACE_ATTACHMENTS
    if raw.startswith(f"{ARTIFACT_NAMESPACE_FILES}/"):
        return ARTIFACT_NAMESPACE_FILES
    return default


def physical_path_to_logical_path(path_value: str) -> str:
    raw = (path_value or "").strip().lstrip("/")
    if not raw:
        return ""
    if raw.startswith(CONVERSATION_FILE_REF_PREFIX):
        conversation_id, turn_id, namespace, rel = split_logical_artifact_ref(
            raw
        )
        if turn_id and namespace and rel:
            return build_logical_artifact_path(
                turn_id=turn_id,
                namespace=namespace,
                relpath=rel,
                conversation_id=conversation_id,
            )
        return raw
    if ":" in raw:
        return ""
    conversation_id, turn_id, namespace, rel = split_physical_artifact_ref(raw)
    if turn_id and namespace and rel:
        return build_logical_artifact_path(
            turn_id=turn_id,
            namespace=namespace,
            relpath=rel,
            conversation_id=conversation_id,
        )
    return ""


def normalize_physical_path(
    path_value: str,
    *,
    turn_id: str,
    default_namespace: str = ARTIFACT_NAMESPACE_FILES,
) -> tuple[str, str, bool]:
    """Normalize a supplied path to an artifact-outdir-relative path."""
    raw = (path_value or "").strip()
    if not raw:
        return "", "", False
    if raw.startswith(CONVERSATION_FILE_REF_PREFIX):
        conversation_id, ref_turn_id, namespace, rel = (
            split_logical_artifact_ref(raw)
        )
        if ref_turn_id and namespace and rel:
            rel = rel.lstrip("/")
            use_turn = ref_turn_id if conversation_id else (
                turn_id or ref_turn_id
            )
            physical = build_physical_artifact_path(
                turn_id=use_turn,
                namespace=namespace,
                relpath=rel,
                conversation_id=conversation_id,
            )
            return physical, rel, True
        return "", "", False
    if ":" in raw:
        return "", "", False
    if raw.startswith("outputs/"):
        return "", "", False
    physical_body = raw
    if physical_body.startswith(ARTIFACT_CONVERSATION_PREFIX):
        _, physical_body = _split_physical_conversation_prefix(physical_body)
    first_segment = physical_body.split("/", 1)[0]
    if is_turn_id(first_segment) and not split_physical_artifact_path(
        physical_body
    )[0]:
        return "", "", False

    rel = raw
    rewritten = False
    namespace = infer_artifact_namespace(
        raw,
        default=default_namespace or ARTIFACT_NAMESPACE_FILES,
    )
    if raw.startswith(f"{ARTIFACT_NAMESPACE_PROJECTS}/"):
        rel = raw[len(f"{ARTIFACT_NAMESPACE_PROJECTS}/") :]
        rewritten = True
    elif raw.startswith(f"{ARTIFACT_NAMESPACE_FILES}/"):
        rel = raw[len(f"{ARTIFACT_NAMESPACE_FILES}/") :]
        rewritten = True
    elif raw.startswith(f"{ARTIFACT_NAMESPACE_SNAPSHOTS}/"):
        rel = raw[len(f"{ARTIFACT_NAMESPACE_SNAPSHOTS}/") :]
        rewritten = True
    elif raw.startswith(f"{ARTIFACT_NAMESPACE_ATTACHMENTS}/"):
        rel = raw[len(f"{ARTIFACT_NAMESPACE_ATTACHMENTS}/") :]
        physical = (
            build_physical_artifact_path(
                turn_id=turn_id,
                namespace=ARTIFACT_NAMESPACE_ATTACHMENTS,
                relpath=rel,
            )
            if turn_id
            else rel
        )
        return physical, rel, physical != raw
    else:
        _, raw_namespace, raw_rel = split_physical_artifact_path(raw)
        if raw_namespace:
            namespace = raw_namespace
            rel = raw_rel
            rewritten = True
    prefix = f"{turn_id}/{namespace}/"
    if turn_id and raw.startswith(prefix):
        rel = raw[len(prefix) :]
        rewritten = True
    physical = (
        build_physical_artifact_path(
            turn_id=turn_id,
            namespace=namespace,
            relpath=rel,
        )
        if turn_id
        else rel
    )
    if physical != raw:
        rewritten = True
    return physical, rel, rewritten


def normalize_relpath(path_value: str, *, turn_id: str) -> str:
    """Return the artifact-outdir-relative part of a supplied path."""
    try:
        _, rel, _ = normalize_physical_path(path_value, turn_id=turn_id)
        return rel
    except Exception:
        return (path_value or "").strip()


def normalize_file_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a file payload whose ``filename`` is a basename."""
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    filename = normalized.get("filename")
    if isinstance(filename, str) and filename.strip():
        normalized["filename"] = pathlib.PurePosixPath(filename.strip()).name
    return normalized

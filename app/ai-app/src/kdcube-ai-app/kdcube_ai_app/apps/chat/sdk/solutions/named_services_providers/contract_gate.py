# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Contract-first gate for named-service writes.

Named-service actions are realm-defined named protocols: each namespace's
provider encodes its own payload keys, value shapes, and file forms, and the
`object_schema` / `provider_about` responses are the only place those
contracts are stated. This gate holds that order platform-side for the agent
grammar dispatch (`named_services.tools._call`): the FIRST
`object_action`/`upsert_object` on a namespace whose contract has not been
read in this conversation returns one instructive protocol rejection; the
nudge is recorded, so the retry proceeds. The rejection carries fix actor
``agent`` — it is agent protocol, so chat raises no user banner for it.

State scope — conversation workspace, cross-process:
The gate state is a small JSON file under the conversation's runtime output
root (``resolve_runtime_output_dir()``), the same workspace the ReAct turn
runtime and exec-brokered child runtimes share (turn directories accumulate
under it for the whole conversation). A contract read recorded by the chat
process is therefore visible to a named-service call made from EXEC-brokered
generated code, and the nudge recorded by a child process survives that
process. When no workspace is bound (e.g. a bare tool invocation outside a
ReAct run), an in-process store keyed by conversation id takes over.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import threading
from typing import Dict, Set

LOGGER = logging.getLogger("kdcube.sdk.named_services.contract_gate")

GATE_STATE_FILENAME = "named_services_contract_gate.json"

_CONTRACT_READ = "contract_read"
_NUDGED = "nudged"

_LOCK = threading.Lock()
# In-process fallback: conversation key -> {"contract_read": set, "nudged": set}.
_LOCAL_STATE: Dict[str, Dict[str, Set[str]]] = {}


def _normalize(namespace: str) -> str:
    return str(namespace or "").strip().lower().rstrip(":")


def _conversation_key() -> str:
    try:
        from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx

        identity = comm_ctx.get_current_user_identity()
        return str(identity.get("conversation_id") or "")
    except Exception:
        return ""


def _state_path() -> pathlib.Path | None:
    try:
        from kdcube_ai_app.apps.chat.sdk.runtime.workdir_discovery import resolve_runtime_output_dir

        return resolve_runtime_output_dir() / GATE_STATE_FILENAME
    except Exception:
        return None


def _as_set(raw: object) -> Set[str]:
    if isinstance(raw, (list, tuple, set)):
        return {str(item) for item in raw if str(item or "").strip()}
    return set()


def _load_file_state(path: pathlib.Path) -> Dict[str, Set[str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        _CONTRACT_READ: _as_set(raw.get(_CONTRACT_READ)),
        _NUDGED: _as_set(raw.get(_NUDGED)),
    }


def _store_file_state(path: pathlib.Path, state: Dict[str, Set[str]]) -> None:
    payload = {key: sorted(values) for key, values in state.items()}
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _local_entry() -> Dict[str, Set[str]]:
    return _LOCAL_STATE.setdefault(_conversation_key(), {_CONTRACT_READ: set(), _NUDGED: set()})


def record_contract_read(namespace: str) -> None:
    """Record that the namespace's contract (`object_schema`/`provider_about`) was requested."""

    ns = _normalize(namespace)
    if not ns:
        return
    with _LOCK:
        path = _state_path()
        if path is not None:
            try:
                state = _load_file_state(path)
                if ns not in state[_CONTRACT_READ]:
                    state[_CONTRACT_READ].add(ns)
                    _store_file_state(path, state)
                return
            except Exception:
                LOGGER.debug("contract-gate file state unavailable; using in-process state", exc_info=True)
        _local_entry()[_CONTRACT_READ].add(ns)


def register_write_attempt(namespace: str) -> bool:
    """Register an `object_action`/`upsert_object` dispatch on a namespace.

    Returns True exactly for the FIRST write on a namespace whose contract has
    not been read in this conversation — the caller rejects that one call with
    the instructive protocol notice. The nudge is recorded here, so every
    later call (the retry included) returns False and proceeds.
    """

    ns = _normalize(namespace)
    if not ns:
        return False
    with _LOCK:
        local = _LOCAL_STATE.get(_conversation_key()) or {}
        path = _state_path()
        if path is not None:
            try:
                state = _load_file_state(path)
                if ns in state[_CONTRACT_READ] or ns in local.get(_CONTRACT_READ, set()):
                    return False
                if ns in state[_NUDGED] or ns in local.get(_NUDGED, set()):
                    return False
                state[_NUDGED].add(ns)
                _store_file_state(path, state)
                return True
            except Exception:
                LOGGER.debug("contract-gate file state unavailable; using in-process state", exc_info=True)
        entry = _local_entry()
        if ns in entry[_CONTRACT_READ] or ns in entry[_NUDGED]:
            return False
        entry[_NUDGED].add(ns)
        return True


def reset_contract_gate_process_state() -> None:
    """Clear the in-process fallback store (test isolation)."""

    with _LOCK:
        _LOCAL_STATE.clear()


__all__ = [
    "GATE_STATE_FILENAME",
    "record_contract_read",
    "register_write_attempt",
    "reset_contract_gate_process_state",
]

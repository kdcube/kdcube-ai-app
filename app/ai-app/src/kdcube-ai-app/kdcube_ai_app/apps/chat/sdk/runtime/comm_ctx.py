# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

# kdcube_ai_app/apps/chat/sdk/runtime/comm_ctx.py
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional, Dict, Any

from kdcube_ai_app.apps.chat.emitters import ChatCommunicator
from kdcube_ai_app.apps.chat.sdk.protocol import ChatTaskPayload

# Public: holds the communicator for the *current execution context*
COMM_CV: ContextVar[object | None] = ContextVar("COMM_CV", default=None)
REQUEST_CONTEXT_CV: ContextVar[ChatTaskPayload | None] = ContextVar("REQUEST_CONTEXT_CV", default=None)
BUNDLE_ID_CV: ContextVar[str | None] = ContextVar("BUNDLE_ID_CV", default=None)
_BIND_COMM_UNSET = object()
_BIND_BUNDLE_UNSET = object()

def set_comm(comm: object) -> None:
    """Register the ChatCommunicator singleton for this context."""
    COMM_CV.set(comm)

def get_comm() -> Optional[object|ChatCommunicator]:
    """Get the ChatCommunicator singleton (or None if not initialized)."""
    return COMM_CV.get()


def get_current_comm() -> Optional[object | ChatCommunicator]:
    """Public alias for the current execution communicator."""
    return get_comm()


def set_current_request_context(request_context: ChatTaskPayload | None) -> None:
    """Register the ChatTaskPayload for the current execution context."""
    REQUEST_CONTEXT_CV.set(request_context)


def get_current_request_context() -> Optional[ChatTaskPayload]:
    """Get the current request/task payload bound to this execution context."""
    return REQUEST_CONTEXT_CV.get()


def set_current_bundle_id(bundle_id: str | None) -> None:
    """Register current bundle id for this execution context."""
    BUNDLE_ID_CV.set(str(bundle_id or "").strip() or None)


def get_current_bundle_id() -> str | None:
    """Get the current bundle id bound to this execution context."""
    return BUNDLE_ID_CV.get()


@contextmanager
def bind_current_bundle_id(bundle_id: str | None):
    token = BUNDLE_ID_CV.set(str(bundle_id or "").strip() or None)
    try:
        yield BUNDLE_ID_CV.get()
    finally:
        BUNDLE_ID_CV.reset(token)


@contextmanager
def bind_current_request_context(
    request_context: ChatTaskPayload | None,
    *,
    comm: object | ChatCommunicator | None = _BIND_COMM_UNSET,
    bundle_id: str | None | object = _BIND_BUNDLE_UNSET,
):
    """
    Bind request-local execution context for the lifetime of one invocation.
    ContextVar binding is task-local and survives across awaits within that task.
    """
    req_token = REQUEST_CONTEXT_CV.set(request_context)
    comm_token = None
    bundle_token = None
    if comm is not _BIND_COMM_UNSET:
        comm_token = COMM_CV.set(comm)
    resolved_bundle_id = bundle_id
    if resolved_bundle_id is _BIND_BUNDLE_UNSET and request_context is not None:
        resolved_bundle_id = str(
            getattr(getattr(request_context, "routing", None), "bundle_id", None) or ""
        ).strip() or None
    if resolved_bundle_id is not _BIND_BUNDLE_UNSET:
        bundle_token = BUNDLE_ID_CV.set(str(resolved_bundle_id or "").strip() or None)
    try:
        yield request_context
    finally:
        if bundle_token is not None:
            BUNDLE_ID_CV.reset(bundle_token)
        if comm_token is not None:
            COMM_CV.reset(comm_token)
        REQUEST_CONTEXT_CV.reset(req_token)

async def delta(text: str, index: int, marker: str = "answer", completed: bool = False, **kwargs) -> None:
    """Convenience: emit a delta if communicator is present."""
    comm = get_comm()
    if comm is None:
        return
    await comm.delta(text=text, index=index, marker=marker, completed=completed, **kwargs)

async def step(step: str, status: str, **payload) -> None:
    comm = get_comm()
    if comm is None:
        return
    await comm.step(step=step, status=status, **payload)

async def complete(data: Dict[str, Any] | None = None) -> None:
    comm = get_comm()
    if comm is None:
        return
    await comm.complete(data=data or {})

async def error(message: str, data: Dict[str, Any] | None = None) -> None:
    comm = get_comm()
    if comm is None:
        return
    await comm.error(message=message, data=data or {})

# We rebuild the communicator from PORTABLE_SPEC in the child, so we do NOT
# serialize the COMM_CV object itself (not JSON-safe). Keep tiny helpers:

def snapshot_ctxvars() -> dict:
    request_context = REQUEST_CONTEXT_CV.get()
    if request_context is not None and hasattr(request_context, "model_dump"):
        request_context = request_context.model_dump()
    # communicator itself is rebuilt from spec in child runtimes
    return {
        "COMM_PRESENT": COMM_CV.get() is not None,
        "REQUEST_CONTEXT": request_context,
        "BUNDLE_ID": BUNDLE_ID_CV.get(),
    }

def restore_ctxvars(payload: dict) -> None:
    raw_request_context = (payload or {}).get("REQUEST_CONTEXT")
    if raw_request_context:
        try:
            REQUEST_CONTEXT_CV.set(ChatTaskPayload.model_validate(raw_request_context))
        except Exception:
            REQUEST_CONTEXT_CV.set(None)
    else:
        REQUEST_CONTEXT_CV.set(None)
    BUNDLE_ID_CV.set((payload or {}).get("BUNDLE_ID") or None)

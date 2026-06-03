# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

# chat/ingress/chat_core.py

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from fastapi import HTTPException, Request  # only if you put this in a place where FastAPI is available

from kdcube_ai_app.apps.chat.sdk.config import get_settings
from kdcube_ai_app.apps.chat.continuations import RedisConversationContinuationSource
from kdcube_ai_app.apps.chat.external_events import build_conversation_external_event_source
from kdcube_ai_app.apps.chat.sdk.util import _iso
from kdcube_ai_app.auth.sessions import RequestContext, UserType, UserSession
from kdcube_ai_app.apps.chat.emitters import ChatRelayCommunicator, ChatCommunicator
from kdcube_ai_app.apps.chat.sdk.protocol import (
    ExternalEventPayload, ExternalEventMeta, ExternalEventRouting, ExternalEventActor, ExternalEventUser,
    ExternalEventRequest, ExternalEventConfig, ExternalEventAccounting, ExternalEventContinuation, ExternalEvent,
    ExternalEventLaneRef, ExternalEventLaneWakeup, ServiceCtx, ConversationCtx
)
from kdcube_ai_app.apps.chat.sdk.event_identity import DEFAULT_REACT_AGENT_ID, normalize_agent_id
from kdcube_ai_app.infra.accounting.envelope import build_envelope_from_session
from kdcube_ai_app.infra.gateway.rate_limiter import RateLimitError
from kdcube_ai_app.infra.gateway.backpressure import BackpressureError
from kdcube_ai_app.infra.gateway.circuit_breaker import CircuitBreakerError
from kdcube_ai_app.apps.middleware.token_extract import (
    resolve_auth_from_headers_and_cookies,
    resolve_socket_auth_tokens,
)
from kdcube_ai_app.apps.chat.ids import new_turn_id
from kdcube_ai_app.apps.chat.ingress.resolvers import get_auth_manager
from kdcube_ai_app.infra.plugin.bundle_registry import load_persisted_registry_from_runtime_ctx

from kdcube_ai_app.auth.AuthManager import AuthenticationError, PRIVILEGED_ROLES

logger = logging.getLogger(__name__)

async def _load_active_registry(app, tenant: str, project: str):
    """
    Ingress must not mutate bundle descriptors. It reads the active registry
    via bundle_store; file-backed deployments reread descriptor authority and
    refresh Redis only as a runtime cache.
    """
    return await load_persisted_registry_from_runtime_ctx(app.state, tenant, project)


TransportKind = Literal["sse", "socket", "telegram"]

# Hard limit for input text length.
# Chosen so that we can embed it with OpenAI embeddings without chunking.
try:
    MAX_EMBED_TEXT_CHARS: int = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "32000"))
except Exception:
    MAX_EMBED_TEXT_CHARS = 32000

# -----------------------------
# Gateway checks (shared)
# -----------------------------

@dataclass
class GatewayCheckResult:
    kind: Literal["ok", "rate_limit", "backpressure", "circuit_breaker", "error"]
    exc: Optional[Exception] = None


async def run_gateway_checks(
        gateway_adapter,
        session: UserSession,
        context: RequestContext,
        endpoint: str,
) -> GatewayCheckResult:
    """
    Shared gateway checks for chat ingestion.
    Transport layer decides how to map errors to HTTP / WS semantics.
    """
    try:
        await gateway_adapter.gateway.rate_limiter.check_and_record(session, context, endpoint)
        await gateway_adapter.gateway.backpressure_manager.check_capacity(
            session.user_type, session, context, endpoint
        )
        return GatewayCheckResult(kind="ok")
    except RateLimitError as e:
        return GatewayCheckResult(kind="rate_limit", exc=e)
    except BackpressureError as e:
        return GatewayCheckResult(kind="backpressure", exc=e)
    except CircuitBreakerError as e:
        return GatewayCheckResult(kind="circuit_breaker", exc=e)
    except Exception as e:
        logger.exception("Gateway checks failed for endpoint %s: %s", endpoint, e)
        return GatewayCheckResult(kind="error", exc=e)


def map_gateway_error(result: GatewayCheckResult) -> Dict[str, Any]:
    """
    Map GatewayCheckResult → generic error payload for transport layer.
    """
    if result.kind == "rate_limit":
        e: RateLimitError = result.exc  # type: ignore[assignment]
        msg = f"Rate limit exceeded: {getattr(e, 'message', str(e))}"
        return {
            "error_type": "rate_limit",
            "status": 429,
            "message": msg,
            "retry_after": getattr(e, "retry_after", None),
        }
    if result.kind == "backpressure":
        e: BackpressureError = result.exc  # type: ignore[assignment]
        msg = f"System under pressure: {getattr(e, 'message', str(e))}"
        return {
            "error_type": "backpressure",
            "status": 503,
            "message": msg,
            "retry_after": getattr(e, "retry_after", None),
        }
    if result.kind == "circuit_breaker":
        e: CircuitBreakerError = result.exc  # type: ignore[assignment]
        msg = f"Service temporarily unavailable: {getattr(e, 'message', str(e))}"
        return {
            "error_type": "circuit_breaker",
            "status": 503,
            "message": msg,
            "retry_after": getattr(e, "retry_after", None),
        }

    # generic
    msg = "System check failed"
    return {
        "error_type": "gateway_error",
        "status": 503,
        "message": msg,
        "retry_after": None,
    }


# -----------------------------
# Attachments (shared)
# -----------------------------

@dataclass
class RawAttachment:
    """
    Transport-agnostic representation of a raw uploaded file.
    """
    content: bytes
    name: str
    mime: str
    meta: Optional[Dict[str, Any]] = None


# -----------------------------
# Chat ingestion (shared)
# -----------------------------

@dataclass
class IngressConfig:
    transport: TransportKind                # "sse", "socket", or proc-local transports such as "telegram"
    entrypoint: str                         # "/sse/chat", "/socket.io/chat", "/telegram/webhook", ...
    component: str                          # "chat.sse", "chat.socket", "chat.telegram", ...
    instance_id: str
    stream_id: Optional[str] = None         # SSE stream_id or Socket.IO sid
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class IngressResult:
    ok: bool
    error_type: Optional[str] = None
    error: Optional[str] = None
    http_status: Optional[int] = None
    retry_after: Optional[int] = None
    task_id: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_id: Optional[str] = None
    session_id: Optional[str] = None
    user_type: Optional[str] = None
    queue_stats: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    continuation_kind: Optional[str] = None
    active_turn_id: Optional[str] = None
    target_turn_id: Optional[str] = None
    queued_turn_id: Optional[str] = None
    event_id: Optional[str] = None
    external_event_sequence: Optional[int] = None
    live_owner_detected: Optional[bool] = None


def _message_payload(message_data: Dict[str, Any]) -> Dict[str, Any]:
    payload = message_data.get("payload")
    return payload if isinstance(payload, dict) else {}


def _resolve_requested_continuation_kind(
    message_data: Dict[str, Any],
    *,
    conversation_busy: bool,
) -> tuple[str, bool]:
    payload = _message_payload(message_data)

    raw = (
        message_data.get("message_kind")
        or message_data.get("continuation_kind")
        or payload.get("message_kind")
        or payload.get("continuation_kind")
    )
    raw = str(raw or "").strip().lower()

    explicit_followup = bool(message_data.get("followup") or payload.get("followup"))
    explicit_steer = bool(message_data.get("steer") or payload.get("steer"))

    if explicit_steer or raw == "steer":
        return "steer", True
    if explicit_followup or raw == "followup":
        return "followup", True
    if raw == "regular":
        return ("followup" if conversation_busy else "regular"), True
    return ("followup" if conversation_busy else "regular"), False


def _resolve_target_turn_id(message_data: Dict[str, Any]) -> Optional[str]:
    payload = _message_payload(message_data)
    raw = (
        message_data.get("target_turn_id")
        or message_data.get("active_turn_id")
        or payload.get("target_turn_id")
        or payload.get("active_turn_id")
    )
    value = str(raw or "").strip()
    return value or None


def _external_event_from_message(message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = _message_payload(message_data)
    event = payload.get("external_event")
    if not isinstance(event, dict):
        return None
    return event


def _external_event_is_reactive(event: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(event, dict):
        return False
    routing = event.get("routing") if isinstance(event.get("routing"), dict) else {}
    if "reactive" not in routing:
        return False
    value = routing.get("reactive")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return False


def _external_event_source_id(event: Optional[Dict[str, Any]]) -> str:
    if not isinstance(event, dict):
        return "react.external_event"
    value = str(event.get("event_source_id") or event.get("type") or event.get("kind") or "").strip()
    return value or "react.external_event"


def _target_agent_id(message_data: Dict[str, Any]) -> str:
    payload = _message_payload(message_data)
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    value = (
        target.get("agent_id")
        or target.get("agent")
        or payload.get("agent_id")
        or message_data.get("agent_id")
        or message_data.get("agent")
    )
    return normalize_agent_id(value, default=DEFAULT_REACT_AGENT_ID)


def _chat_event_kind(*, has_external_event: bool, requested_kind: str) -> str:
    if has_external_event:
        return "external_event"
    kind = str(requested_kind or "").strip().lower()
    if kind in {"followup", "steer"}:
        return kind
    return "message"


def _chat_event_source_id(*, has_external_event: bool, external_event: Optional[Dict[str, Any]], requested_kind: str) -> str:
    if has_external_event:
        return _external_event_source_id(external_event)
    kind = _chat_event_kind(has_external_event=False, requested_kind=requested_kind)
    return f"chat.{kind}"


def _external_event_envelope(
    *,
    message_data: Dict[str, Any],
    text: str,
    event: Dict[str, Any],
) -> Dict[str, Any]:
    payload = _message_payload(message_data)
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    envelope: Dict[str, Any] = {
        "message": text or "",
        "external_event": dict(event),
    }
    if target:
        envelope["target"] = dict(target)
    return envelope


def _event_lane_ref_from_envelope(
    *,
    tenant: Optional[str],
    project: Optional[str],
    user_id: Optional[str],
    conversation_id: str,
    agent_id: str,
    event: Any,
) -> ExternalEventLaneRef:
    return ExternalEventLaneRef(
        tenant=tenant,
        project=project,
        user_id=user_id,
        conversation_id=conversation_id,
        agent_id=normalize_agent_id(agent_id, default=DEFAULT_REACT_AGENT_ID),
        event_id=str(getattr(event, "message_id", "") or "") or None,
        sequence=int(getattr(event, "sequence", 0) or 0) or None,
        stream_id=str(getattr(event, "stream_id", "") or "") or None,
    )


def _event_lane_wakeup_from_payload(
    *,
    payload: ExternalEventPayload,
    event: Any,
    tenant: Optional[str],
    project: Optional[str],
    user_id: Optional[str],
    conversation_id: str,
    agent_id: str,
    reason: str,
) -> ExternalEventLaneWakeup:
    return ExternalEventLaneWakeup(
        meta=payload.meta,
        routing=payload.routing,
        actor=payload.actor,
        user=payload.user,
        config=payload.config,
        accounting=payload.accounting,
        continuation=payload.continuation,
        event=payload.event,
        bundle_call_context=dict(getattr(payload, "bundle_call_context", {}) or {}),
        event_lane=_event_lane_ref_from_envelope(
            tenant=tenant,
            project=project,
            user_id=user_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            event=event,
        ),
        reason=reason,
    )


def _resolve_conversation_owner_id(session: UserSession) -> Optional[str]:
    owner_id = getattr(session, "user_id", None) or getattr(session, "fingerprint", None)
    if owner_id is None:
        return None
    owner_id = str(owner_id).strip()
    return owner_id or None


async def _conversation_state_row_exists(
        conversation_browser,
        *,
        user_id: str,
        conversation_id: str,
) -> bool:
    idx = getattr(conversation_browser, "idx", None)
    if idx is None:
        return False
    get_row = getattr(idx, "get_conversation_state_row", None)
    if get_row is None:
        return False
    try:
        row = await get_row(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return bool(row)
    except Exception as e:
        logger.warning(
            "Conversation state-row fallback failed user=%s conversation_id=%s: %s",
            user_id,
            conversation_id,
            e,
        )
        return False


async def resolve_ingress_conversation_id(
        *,
        app,
        session: UserSession,
        message_data: Dict[str, Any],
) -> tuple[str, bool]:
    raw_conversation_id = message_data.get("conversation_id")
    conversation_id = str(raw_conversation_id or "").strip()
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        message_data["conversation_id"] = conversation_id
        return conversation_id, True

    owner_id = _resolve_conversation_owner_id(session)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Authenticated user identity is missing")

    conversation_browser = getattr(getattr(app, "state", None), "conversation_browser", None)
    if conversation_browser is None:
        logger.error("Conversation lookup is unavailable: app.state.conversation_browser is not configured")
        raise HTTPException(status_code=503, detail="Conversation lookup unavailable")

    exists = await conversation_browser.conversation_exists(
        user_id=owner_id,
        conversation_id=conversation_id,
    )
    if not exists:
        # A newly created conversation writes its conversation.state row before
        # the HTTP ack, while searchable turn artifacts may arrive later in the
        # processor. Treat that state row as sufficient ownership evidence so a
        # rapid follow-up does not 404 during the indexing gap.
        exists = await _conversation_state_row_exists(
            conversation_browser,
            user_id=owner_id,
            conversation_id=conversation_id,
        )
    if not exists:
        raise HTTPException(status_code=404, detail="Conversation not found")

    message_data["conversation_id"] = conversation_id
    return conversation_id, False


async def process_chat_message(
        *,
        app,
        chat_queue_manager,
        chat_comm: ChatRelayCommunicator,
        session: UserSession,
        request_context: RequestContext,
        message_data: Dict[str, Any],
        message_text: str,
        ingress: IngressConfig,
        raw_attachments: Optional[List[RawAttachment]] = None,
) -> IngressResult:
    """
    Core chat ingestion:
      - validate message
      - resolve bundle
      - build payload + accounting envelope
      - conversation state (lock, created/in_progress)
      - enqueue
      - emit conv_status + start + errors

    Transport layer already ran gateway checks. It just passes its
    RequestContext + IngressConfig.
    """
    text = (message_text or "").strip()
    has_raw_attachments = bool(raw_attachments)
    requested_kind, requested_kind_explicit = _resolve_requested_continuation_kind(
        message_data,
        conversation_busy=False,
    )
    target_turn_id = _resolve_target_turn_id(message_data)
    external_event = _external_event_from_message(message_data)
    has_external_event = external_event is not None
    external_event_reactive = _external_event_is_reactive(external_event)
    target_agent_id = _target_agent_id(message_data)
    task_id = str(uuid.uuid4())
    turn_id = message_data.get("turn_id") or new_turn_id()
    conversation_id = str(message_data.get("conversation_id") or "").strip()
    if not conversation_id:
        return IngressResult(
            ok=False,
            error_type="missing_conversation_id",
            error="Missing conversation_id",
            http_status=400,
        )
    message_data["conversation_id"] = conversation_id
    # Tenant / project
    settings = get_settings()
    tenant_id = (
            message_data.get("tenant")
            or message_data.get("tenant_id")
            or settings.TENANT
    )
    project_id = message_data.get("project") or settings.PROJECT

    request_id = str(uuid.uuid4())
    provided_bundle_id = message_data.get("bundle_id")

    # Ingress only reads the active registry; it does not mutate descriptors.
    reg = await _load_active_registry(app, tenant_id, project_id)

    svc = ServiceCtx(request_id=request_id, user=session.user_id, project=project_id, tenant=tenant_id)
    conv = ConversationCtx(
        session_id=session.session_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
    )
    comm = ChatCommunicator(
        emitter=chat_comm,
        tenant=tenant_id or "",
        project=project_id or "",
        user_id=session.user_id,
        user_type=session.user_type.value,
        service=svc.model_dump(),
        conversation=conv.model_dump(),
        room=session.session_id,
        target_sid=ingress.stream_id,
    )

    # If the active registry is not available, fail early to avoid stale defaults.
    if not reg:
        err = "Bundle registry unavailable"
        await chat_comm.emit_error(
            svc,
            conv,
            error=err,
            target_sid=ingress.stream_id,
            session_id=session.session_id,
        )
        return IngressResult(
            ok=False,
            error_type="bundle_registry_unavailable",
            error=err,
            http_status=503,
        )

    # Empty text is valid when the user sent attachments: the hosted attachment
    # descriptors are added to request.payload before the turn/follow-up is run.
    # Explicit steer messages and explicit external events may intentionally
    # carry blank text.
    if not text and not has_raw_attachments and requested_kind != "steer" and not has_external_event:
        await chat_comm.emit_error(
            svc,
            conv,
            error='Missing "message"',
            target_sid=ingress.stream_id,
            session_id=session.session_id,
        )
        return IngressResult(
            ok=False,
            error_type="missing_message",
            error='Missing "message"',
            http_status=400,
        )

    from kdcube_ai_app.infra.service_hub.multimodality import (
        MESSAGE_MAX_BYTES,
        MODALITY_DOC_MIME,
        MODALITY_IMAGE_MIME,
        MODALITY_MAX_DOC_BYTES,
        MODALITY_MAX_IMAGE_BYTES,
    )

    text_bytes = len(text.encode("utf-8"))
    if text_bytes > MESSAGE_MAX_BYTES:
        total_limit_mb = int(MESSAGE_MAX_BYTES / (1024 * 1024))
        await chat_comm.emit_error(
            svc,
            conv,
            error=f"Message exceeds the {total_limit_mb} MB total limit (text + attachments).",
            target_sid=ingress.stream_id,
            session_id=session.session_id,
        )
        return IngressResult(
            ok=False,
            error_type="message_size_limit",
            error="message exceeds total size limit",
            http_status=413,
        )

    bundle_id_val = provided_bundle_id or (reg.default_bundle_id if reg else None)
    if not reg or not bundle_id_val or bundle_id_val not in (reg.bundles or {}):
        err = f"Unknown bundle_id '{bundle_id_val or provided_bundle_id}'"
        await chat_comm.emit_error(
            svc,
            conv,
            error=err,
            target_sid=ingress.stream_id,
            session_id=session.session_id,
        )
        return IngressResult(
            ok=False,
            error_type="unknown_bundle",
            error=err,
            http_status=400,
        )
    spec_resolved = reg.bundles.get(bundle_id_val)
    if not spec_resolved:
        err = f"Bundle spec missing for bundle_id '{bundle_id_val}'"
        await chat_comm.emit_error(
            svc,
            conv,
            error=err,
            target_sid=ingress.stream_id,
            session_id=session.session_id,
        )
        return IngressResult(
            ok=False,
            error_type="unknown_bundle",
            error=err,
            http_status=400,
        )

    # Input too long → emit error and do NOT enqueue
    if len(text) > MAX_EMBED_TEXT_CHARS:
        err = (
            f"Input is too long ({len(text)} characters). "
            f"Maximum allowed is {MAX_EMBED_TEXT_CHARS} characters."
        )
        await chat_comm.emit_error(
            svc,
            conv,
            error=err,
            target_sid=ingress.stream_id,
            session_id=session.session_id,
        )
        return IngressResult(
            ok=False,
            error_type="input_too_long",
            error=err,
            http_status=400,
            reason="input_too_long",
        )

    bundle_id = spec_resolved.id
    metadata = dict(ingress.metadata or {})
    acct_env = build_envelope_from_session(
        session=session,
        tenant_id=tenant_id,
        project_id=project_id,
        request_id=request_id,
        component=ingress.component,
        app_bundle_id=bundle_id,
        metadata=metadata,
    ).to_dict()

    ext_config = (message_data.get("config") or {}).copy()
    if "tenant" not in ext_config:
        ext_config["tenant"] = tenant_id
    if "project" not in ext_config and project_id:
        ext_config["project"] = project_id

    routing = ExternalEventRouting(
        session_id=session.session_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        socket_id=ingress.stream_id,
        bundle_id=bundle_id,
    )

    payload = ExternalEventPayload(
        meta=ExternalEventMeta(
            task_id=task_id,
            created_at=time.time(),
            instance_id=ingress.instance_id,
        ),
        routing=routing,
        actor=ExternalEventActor(
            tenant_id=tenant_id,
            project_id=project_id,
        ),
        user=ExternalEventUser(
            user_type=session.user_type.value,
            user_id=session.user_id,
            username=session.username,
            email=session.email,
            fingerprint=session.fingerprint,
            roles=session.roles,
            permissions=session.permissions,
            timezone=session.timezone,
            utc_offset_min=getattr(request_context, "user_utc_offset_min", None),
        ),
        request=ExternalEventRequest(
            message=text,
            chat_history=message_data.get("chat_history") or [],
            operation=message_data.get("operation") or message_data.get("command"),
            invocation=message_data.get("invocation"),
            payload=message_data.get("payload") or {},
            request_id=request_id,
        ),
        config=ExternalEventConfig(values=ext_config),
        accounting=ExternalEventAccounting(envelope=acct_env),
        continuation=ExternalEventContinuation(
            kind=requested_kind,
            explicit=requested_kind_explicit,
            target_turn_id=target_turn_id,
        ),
        event=ExternalEvent(
            kind=_chat_event_kind(has_external_event=has_external_event, requested_kind=requested_kind),
            agent_id=target_agent_id,
            event_source_id=_chat_event_source_id(
                has_external_event=has_external_event,
                external_event=external_event,
                requested_kind=requested_kind,
            ),
            reactive=external_event_reactive if has_external_event else True,
            source=f"ingress.{ingress.transport}",
        ),
    )
    async def _host_message_attachments(
        *,
        storage_turn_id: str,
        rollback_conversation_state: bool,
    ) -> Optional[IngressResult]:
        if not raw_attachments:
            return None

        store = getattr(app.state, "conversation_store", None)
        _av = get_settings().PLATFORM.HOSTED_SERVICES.AV
        enable_av = _av.APP_AV_SCAN
        av_timeout = _av.APP_AV_TIMEOUT_S
        from kdcube_ai_app.infra.gateway.safe_preflight import PreflightConfig, preflight_async
        cfg = PreflightConfig(av_scan=enable_av, av_timeout_s=av_timeout)

        attachment_errors: List[str] = []
        preflight_ok: List[RawAttachment] = []

        async def _safe_attachment_event(reason: str, message: str, att: RawAttachment, extra: Optional[Dict[str, Any]] = None) -> None:
            data = {
                "reason": reason,
                "message": message,
                "filename": att.name or "file",
                "mime": att.mime or "application/octet-stream",
                "show_in_timeline": True,
            }
            if extra:
                data.update(extra)
            try:
                await comm.service_event(
                    type="rate_limit.attachment_failure",
                    step="rate_limit",
                    status="error",
                    title="Attachment rejected",
                    agent="ingress.attachments",
                    data=data,
                )
            except Exception:
                logger.exception("failed to emit attachment failure event")

        total_bytes = text_bytes + sum(len(a.content or b"") for a in raw_attachments)
        total_limit_mb = int(MESSAGE_MAX_BYTES / (1024 * 1024))
        if total_bytes > MESSAGE_MAX_BYTES:
            attachment_errors.append("message_size_limit")
            await _safe_attachment_event(
                "message_size_limit",
                (
                    f"Total message size exceeds {total_limit_mb} MB (includes message text + attachments; "
                    f"per-file caps: images {int(MODALITY_MAX_IMAGE_BYTES / (1024 * 1024))} MB, "
                    f"PDFs {int(MODALITY_MAX_DOC_BYTES / (1024 * 1024))} MB)."
                ),
                raw_attachments[0],
                {"size_bytes": total_bytes, "max_bytes": MESSAGE_MAX_BYTES, "max_mb": total_limit_mb, "text_bytes": text_bytes},
            )

        for a in raw_attachments:
            if not a.content:
                attachment_errors.append("empty")
                await _safe_attachment_event("empty", "Attachment is empty.", a)
                continue
            mime = (a.mime or "").strip().lower()
            per_file_cap = MESSAGE_MAX_BYTES
            if mime in MODALITY_IMAGE_MIME:
                per_file_cap = MODALITY_MAX_IMAGE_BYTES
            elif mime in MODALITY_DOC_MIME:
                per_file_cap = MODALITY_MAX_DOC_BYTES
            if len(a.content) > per_file_cap:
                attachment_errors.append("size_limit")
                per_file_mb = int(per_file_cap / (1024 * 1024))
                await _safe_attachment_event(
                    "size_limit",
                    f"Attachment '{a.name or 'file'}' exceeds the per-file size limit ({per_file_mb} MB).",
                    a,
                    {"size_bytes": len(a.content), "max_bytes": per_file_cap},
                )
                continue
            if not store:
                attachment_errors.append("store_missing")
                await _safe_attachment_event(
                    "store_missing",
                    "Attachment store is unavailable.",
                    a,
                    {"size_bytes": len(a.content)},
                )
                continue
            if enable_av:
                try:
                    pf = await preflight_async(
                        a.content,
                        a.name or "file",
                        a.mime or "application/octet-stream",
                        cfg,
                    )
                except Exception:
                    attachment_errors.append("preflight_error")
                    await _safe_attachment_event("preflight_error", "Attachment preflight failed.", a)
                    continue
                if not pf.allowed:
                    attachment_errors.append("preflight_rejected")
                    await _safe_attachment_event(
                        "preflight_rejected",
                        "Attachment failed security checks.",
                        a,
                        {"reasons": pf.reasons},
                    )
                    continue
            preflight_ok.append(a)

        attachments: List[Dict[str, Any]] = []
        if not attachment_errors and preflight_ok:
            for a in preflight_ok:
                try:
                    uri, key, rn_f = await store.put_attachment(
                        tenant=tenant_id or "",
                        project=project_id or "",
                        user=session.user_id,
                        fingerprint=session.fingerprint,
                        conversation_id=conversation_id,
                        turn_id=storage_turn_id,
                        role="user",
                        filename=a.name or "file",
                        data=a.content,
                        mime=a.mime or "application/octet-stream",
                        user_type=session.user_type.value,
                        origin="user",
                    )
                except Exception:
                    attachment_errors.append("store_error")
                    await _safe_attachment_event("store_error", "Attachment hosting failed.", a)
                    break
                attachments.append({
                    "filename": a.name or "file",
                    "mime": a.mime or "application/octet-stream",
                    "size": len(a.content),
                    "meta": a.meta or {},
                    "hosted_uri": uri,
                    "key": key,
                    "rn": rn_f,
                    "role": "user",
                    "origin": "user",
                })

        if attachment_errors:
            if store:
                try:
                    _, user_or_fp = store._who_and_id(session.user_id, session.fingerprint)
                    await store.delete_turn(
                        tenant=tenant_id or "",
                        project=project_id or "",
                        user_type=session.user_type.value,
                        user_or_fp=user_or_fp,
                        conversation_id=conversation_id,
                        turn_id=storage_turn_id,
                    )
                except Exception:
                    logger.exception("failed to cleanup attachments after failure")
            if rollback_conversation_state:
                try:
                    res_reset = await app.state.conversation_browser.set_conversation_state(
                        tenant=tenant_id,
                        project=project_id,
                        user_id=session.user_id,
                        conversation_id=conversation_id,
                        new_state="idle",
                        by_instance=ingress.instance_id,
                        request_id=request_id,
                        last_turn_id=turn_id,
                        require_not_in_progress=False,
                        user_type=session.user_type.value,
                        bundle_id=bundle_id,
                    )
                    await chat_comm.emit_conv_status(
                        svc,
                        conv,
                        routing=routing,
                        state="idle",
                        updated_at=res_reset.get("updated_at", _iso()),
                        current_turn_id=res_reset.get("current_turn_id"),
                        completion="rollback",
                        target_sid=ingress.stream_id,
                    )
                except Exception:
                    logger.exception("failed to reset conv state after attachment failure")
            return IngressResult(
                ok=False,
                error_type="attachment_rejected",
                error="Attachment rejected; message not processed.",
                http_status=400,
            )

        if attachments:
            payload_obj = message_data.get("payload")
            if not isinstance(payload_obj, dict):
                payload_obj = {}
            payload_obj["attachments"] = attachments
            message_data["payload"] = payload_obj
            if payload.request:
                payload.request.payload = payload_obj
            try:
                await comm.event(
                    agent="tooling",
                    type="chat.attachments",
                    title=f"Attachments Ready ({len(attachments)})",
                    step="attachments",
                    status="completed",
                    data={"count": len(attachments), "items": attachments},
                )
            except Exception:
                logger.exception("failed to emit attachments step")

        return None

    if has_external_event and not external_event_reactive:
        try:
            conv_exists = await app.state.conversation_browser.conversation_exists(
                user_id=payload.user.user_id,
                conversation_id=conversation_id,
                bundle_id=payload.routing.bundle_id,
            )
            idle_res = await app.state.conversation_browser.set_conversation_state(
                tenant=payload.actor.tenant_id,
                project=payload.actor.project_id,
                user_id=payload.user.user_id,
                conversation_id=payload.routing.conversation_id,
                new_state="idle",
                by_instance=ingress.instance_id,
                request_id=request_id,
                last_turn_id=payload.routing.turn_id,
                require_not_in_progress=True,
                user_type=payload.user.user_type,
                bundle_id=payload.routing.bundle_id,
            )
        except Exception as e:
            logger.error("external event idle state update failed: %s", e)
            conv_exists = True
            idle_res = {
                "ok": False,
                "error": f"conversation state update failed: {e}",
                "error_type": "conversation_state_update_error",
                "updated_at": _iso(),
                "current_turn_id": turn_id,
            }
        if idle_res.get("ok", True):
            redis_async = getattr(app.state, "redis_async", None)
            if redis_async is None:
                err = "External event source unavailable"
                await chat_comm.emit_error(
                    svc,
                    conv,
                    error=err,
                    target_sid=ingress.stream_id,
                    session_id=session.session_id,
                )
                return IngressResult(
                    ok=False,
                    error_type="external_event_source_unavailable",
                    error=err,
                    http_status=503,
                )
            attachment_result = await _host_message_attachments(
                storage_turn_id=turn_id,
                rollback_conversation_state=False,
            )
            if attachment_result is not None:
                return attachment_result
            hosted_attachments = []
            try:
                hosted_attachments = list((payload.request.payload or {}).get("attachments") or []) if payload.request else []
            except Exception:
                hosted_attachments = []
            external_event_source = build_conversation_external_event_source(
                redis=redis_async,
                tenant=tenant_id,
                project=project_id,
                conversation_id=conversation_id,
                user_id=session.user_id or session.fingerprint or "",
                agent_id=target_agent_id,
            )
            env = await external_event_source.publish(
                kind="external_event",
                explicit=True,
                target_turn_id=target_turn_id,
                active_turn_id_at_ingress=None,
                owner_turn_id=None,
                source=f"ingress.{ingress.transport}",
                event_source_id=_external_event_source_id(external_event),
                text=text,
                payload=_external_event_envelope(
                    message_data=message_data,
                    text=text,
                    event=external_event or {},
                ),
                task_payload=payload.model_dump(),
            )
            logger.info(
                "[ingress.external] recorded non-reactive external event conversation=%s event_source_id=%s event_id=%s seq=%s target_turn=%s text=%r",
                conversation_id,
                _external_event_source_id(external_event),
                env.message_id,
                env.sequence,
                target_turn_id,
                (text or "")[:160],
            )
            try:
                if not conv_exists:
                    await chat_comm.emit_conv_status(
                        svc,
                        conv,
                        routing,
                        state="created",
                        updated_at=idle_res.get("updated_at", _iso()),
                        current_turn_id=payload.routing.turn_id,
                    )
                await chat_comm.emit_conv_status(
                    svc,
                    conv,
                    routing,
                    state="idle",
                    updated_at=idle_res.get("updated_at", _iso()),
                    current_turn_id=payload.routing.turn_id,
                )
                await comm.service_event(
                    type="event.external.recorded",
                    step="event.external",
                    status="completed",
                    title="External event recorded",
                    agent="ingress",
                    data={
                        "message_kind": "external_event",
                        "input_kind": "external_event",
                        "event_source_id": _external_event_source_id(external_event),
                        "reactive": False,
                        "message_len": len(text or ""),
                        "attachment_count": len(hosted_attachments),
                        "event_id": env.message_id,
                        "event_sequence": env.sequence,
                        "target_turn_id": target_turn_id,
                    },
                )
            except Exception:
                logger.debug("Failed to emit non-reactive external event service status", exc_info=True)
            return IngressResult(
                ok=True,
                task_id=task_id,
                conversation_id=conversation_id,
                turn_id=turn_id,
                session_id=session.session_id,
                user_type=session.user_type.value,
                queue_stats={
                    "external_event_sequence": env.sequence,
                    "live_owner_detected": False,
                },
                reason="external_event_recorded",
                continuation_kind="external_event",
                active_turn_id=None,
                target_turn_id=target_turn_id,
                queued_turn_id=None,
                event_id=env.message_id,
                external_event_sequence=int(env.sequence or 0),
                live_owner_detected=False,
            )
        idle_error_type = idle_res.get("error_type") or ""
        if idle_error_type != "conversation_busy":
            error = idle_res.get("error") or "Conversation state update failed"
            await chat_comm.emit_error(
                svc,
                conv,
                error=error,
                target_sid=ingress.stream_id,
                session_id=session.session_id,
            )
            return IngressResult(
                ok=False,
                error_type=idle_error_type or "conversation_state_update_error",
                error=error,
                http_status=409,
            )

    # --- Conversation lock + state ---
    try:
        conv_exists = await app.state.conversation_browser.conversation_exists(
            user_id=payload.user.user_id,
            conversation_id=conversation_id,
            bundle_id=payload.routing.bundle_id,
        )

        set_res = await app.state.conversation_browser.set_conversation_state(
            tenant=payload.actor.tenant_id,
            project=payload.actor.project_id,
            user_id=payload.user.user_id,
            conversation_id=payload.routing.conversation_id,
            new_state="in_progress",
            by_instance=ingress.instance_id,
            request_id=request_id,
            last_turn_id=payload.routing.turn_id,
            require_not_in_progress=True,
            user_type=payload.user.user_type,
            bundle_id=payload.routing.bundle_id,
        )
    except Exception as e:
        conv_state_update_error = f"conversation state update failed: {e}"
        logger.error(conv_state_update_error)
        conv_exists = True
        set_res = {"ok": False,
                   "error": conv_state_update_error,
                   "updated_at": _iso(),
                   "current_turn_id": turn_id,
                   "error_type": "conversation_state_update_error"
                   }

    if not set_res.get("ok", True):
        active_turn = set_res.get("current_turn_id")
        error = set_res.get("error") or "Conversation is busy (another tab/process is answering)."
        error_type = set_res.get("error_type") or "conversation_busy"
        if error_type == "conversation_busy":
            try:
                continuation_kind, continuation_explicit = _resolve_requested_continuation_kind(
                    message_data,
                    conversation_busy=True,
                )
                payload.continuation = ExternalEventContinuation(
                    kind=continuation_kind,
                    explicit=continuation_explicit,
                    target_turn_id=target_turn_id,
                    active_turn_id=active_turn,
                )
                external_kind = "external_event" if has_external_event else continuation_kind
                if payload.event is not None:
                    payload.event.kind = external_kind
                    payload.event.agent_id = target_agent_id
                    payload.event.event_source_id = (
                        _external_event_source_id(external_event)
                        if has_external_event
                        else f"chat.{external_kind}"
                    )
                    payload.event.reactive = external_event_reactive if has_external_event else True
                external_payload = (
                    _external_event_envelope(
                        message_data=message_data,
                        text=text,
                        event=external_event or {},
                    )
                    if has_external_event
                    else {"message": text}
                )
                external_event_source = None
                redis_async = getattr(app.state, "redis_async", None)
                if redis_async is not None:
                    external_event_source = build_conversation_external_event_source(
                        redis=redis_async,
                        tenant=tenant_id,
                        project=project_id,
                        conversation_id=conversation_id,
                        user_id=session.user_id or session.fingerprint or "",
                        agent_id=target_agent_id,
                    )
                owner = await external_event_source.get_owner() if external_event_source is not None else None
                owner_turn_id = str(owner.turn_id or "").strip() if owner else ""
                if external_event_source is not None:
                    storage_turn_id = str(active_turn or target_turn_id or turn_id or "").strip() or turn_id
                    attachment_result = await _host_message_attachments(
                        storage_turn_id=storage_turn_id,
                        rollback_conversation_state=False,
                    )
                    if attachment_result is not None:
                        return attachment_result
                    hosted_attachments = []
                    try:
                        hosted_attachments = list((payload.request.payload or {}).get("attachments") or []) if payload.request else []
                    except Exception:
                        hosted_attachments = []
                    env = await external_event_source.publish(
                        kind=external_kind,
                        explicit=continuation_explicit,
                        target_turn_id=target_turn_id,
                        active_turn_id_at_ingress=active_turn,
                        owner_turn_id=owner_turn_id,
                        source=f"ingress.{ingress.transport}",
                        event_source_id=_external_event_source_id(external_event) if has_external_event else f"chat.{external_kind}",
                        text=text,
                        payload=external_payload,
                        task_payload=payload.model_dump(),
                    )
                    live_owner_detected = bool(owner_turn_id and active_turn and owner_turn_id == str(active_turn))
                    logger.info(
                        "[ingress.external] published continuation conversation=%s kind=%s event_source_id=%s event_id=%s seq=%s active_turn=%s owner_turn=%s target_turn=%s live_owner=%s text=%r",
                        conversation_id,
                        external_kind,
                        _external_event_source_id(external_event) if has_external_event else "",
                        env.message_id,
                        env.sequence,
                        active_turn,
                        owner_turn_id,
                        target_turn_id,
                        live_owner_detected,
                        (text or "")[:160],
                    )
                    try:
                        if live_owner_detected:
                            await comm.service_event(
                                type="event.external.accepted",
                                step="event.external",
                                status="completed",
                                title="External event accepted",
                                agent="ingress",
                                data={
                                    "message_kind": external_kind,
                                    "input_kind": external_kind,
                                    "event_source_id": _external_event_source_id(external_event) if has_external_event else None,
                                    "reactive": external_event_reactive if has_external_event else True,
                                    "message_len": len(text or ""),
                                    "attachment_count": len(hosted_attachments),
                                    "active_turn_id": active_turn,
                                    "event_id": env.message_id,
                                    "event_sequence": env.sequence,
                                    "target_turn_id": target_turn_id,
                                    "live_owner_detected": True,
                                },
                            )
                        else:
                            await comm.service_event(
                                type="queue.continuation.accepted",
                                step="queue.continuation",
                                status="completed",
                                title="Continuation accepted",
                                agent="ingress",
                                data={
                                    "message_kind": external_kind,
                                    "input_kind": external_kind,
                                    "event_source_id": _external_event_source_id(external_event) if has_external_event else None,
                                    "reactive": external_event_reactive if has_external_event else True,
                                    "message_len": len(text or ""),
                                    "attachment_count": len(hosted_attachments),
                                    "active_turn_id": active_turn,
                                    "queued_turn_id": payload.routing.turn_id,
                                    "task_id": payload.meta.task_id,
                                    "continuation_message_id": env.message_id,
                                    "external_event_sequence": env.sequence,
                                    "live_owner_detected": False,
                                },
                            )
                    except Exception:
                        logger.debug("Failed to emit external continuation accepted", exc_info=True)
                    return IngressResult(
                        ok=True,
                        task_id=task_id,
                        conversation_id=conversation_id,
                        turn_id=turn_id,
                        session_id=session.session_id,
                        user_type=session.user_type.value,
                        queue_stats={
                            "external_event_sequence": env.sequence,
                            "live_owner_detected": live_owner_detected,
                        },
                        reason="external_event_accepted" if has_external_event else f"{continuation_kind}_accepted",
                        continuation_kind=external_kind,
                        active_turn_id=str(active_turn or "") or None,
                        target_turn_id=target_turn_id,
                        queued_turn_id=payload.routing.turn_id,
                        event_id=env.message_id,
                        external_event_sequence=int(env.sequence or 0),
                        live_owner_detected=live_owner_detected,
                    )
                if has_external_event:
                    err = "External event source unavailable"
                    await chat_comm.emit_error(
                        svc,
                        conv,
                        error=err,
                        target_sid=ingress.stream_id,
                        session_id=session.session_id,
                    )
                    return IngressResult(
                        ok=False,
                        error_type="external_event_source_unavailable",
                        error=err,
                        http_status=503,
                    )
                continuation_source = RedisConversationContinuationSource(
                    redis=getattr(app.state, "redis_async", None),
                    tenant=tenant_id,
                    project=project_id,
                    conversation_id=conversation_id,
                )
                attachment_result = await _host_message_attachments(
                    storage_turn_id=turn_id,
                    rollback_conversation_state=False,
                )
                if attachment_result is not None:
                    return attachment_result
                hosted_attachments = []
                try:
                    hosted_attachments = list((payload.request.payload or {}).get("attachments") or []) if payload.request else []
                except Exception:
                    hosted_attachments = []
                env = await continuation_source.publish(
                    payload,
                    kind=continuation_kind,
                    explicit=continuation_explicit,
                    target_turn_id=target_turn_id,
                    active_turn_id=active_turn,
                )
                queue_size = await continuation_source.pending_count()
                try:
                    await comm.service_event(
                        type="queue.continuation.accepted",
                        step="queue.continuation",
                        status="completed",
                        title="Continuation accepted",
                        agent="ingress",
                        data={
                            "message_kind": continuation_kind,
                            "input_kind": continuation_kind,
                            "message_len": len(text or ""),
                            "attachment_count": len(hosted_attachments),
                            "active_turn_id": active_turn,
                            "queued_turn_id": payload.routing.turn_id,
                            "task_id": payload.meta.task_id,
                            "continuation_queue_size": queue_size,
                            "continuation_message_id": env.message_id,
                        },
                    )
                except Exception:
                    logger.debug("Failed to emit continuation accepted service event", exc_info=True)
                return IngressResult(
                    ok=True,
                    task_id=task_id,
                    conversation_id=conversation_id,
                    turn_id=turn_id,
                    session_id=session.session_id,
                    user_type=session.user_type.value,
                    queue_stats={"continuation_queue_size": queue_size},
                    reason=f"{continuation_kind}_accepted",
                    continuation_kind=continuation_kind,
                    active_turn_id=str(active_turn or "") or None,
                    target_turn_id=target_turn_id,
                    queued_turn_id=payload.routing.turn_id,
                    event_id=env.message_id,
                    live_owner_detected=False,
                )
            except Exception:
                logger.exception("Failed to store continuation message for conversation %s", conversation_id)
        try:
            await chat_comm.emit_conv_status(
                svc,
                conv,
                routing,
                state="in_progress",
                updated_at=set_res.get("updated_at", _iso()),
                current_turn_id=active_turn,
                target_sid=ingress.stream_id,
            )
            await chat_comm.emit_error(
                svc,
                conv,
                error=error,
                target_sid=ingress.stream_id,
                session_id=payload.routing.session_id,
            )
        except Exception:
            pass

        return IngressResult(
            ok=False,
            error_type=error_type,
            error=error,
            http_status=409,
        )

    # Emit conv_status created / in_progress
    try:
        if not conv_exists:
            # broadcast. client can update the conversation list
            await chat_comm.emit_conv_status(
                svc,
                conv,
                routing,
                state="created",
                updated_at=set_res["updated_at"],
                current_turn_id=payload.routing.turn_id,
            )
        # broadcast
        await chat_comm.emit_conv_status(
            svc,
            conv,
            routing,
            state="in_progress",
            updated_at=set_res["updated_at"],
            current_turn_id=payload.routing.turn_id,
        )
    except Exception:
        pass

    # --- Attachments (host after lock; reject entire message on any failure) ---
    attachment_result = await _host_message_attachments(
        storage_turn_id=turn_id,
        rollback_conversation_state=True,
    )
    if attachment_result is not None:
        return attachment_result

    redis_async = getattr(app.state, "redis_async", None)
    if redis_async is None:
        err = "External event source unavailable"
        await chat_comm.emit_error(
            svc,
            conv,
            error=err,
            target_sid=ingress.stream_id,
            session_id=session.session_id,
        )
        try:
            res_reset = await app.state.conversation_browser.set_conversation_state(
                tenant=payload.actor.tenant_id,
                project=payload.actor.project_id,
                user_id=payload.user.user_id,
                conversation_id=payload.routing.conversation_id,
                new_state="idle",
                by_instance=ingress.instance_id,
                request_id=request_id,
                last_turn_id=payload.routing.turn_id,
                require_not_in_progress=False,
                user_type=payload.user.user_type,
                bundle_id=payload.routing.bundle_id,
            )
            await chat_comm.emit_conv_status(
                svc,
                conv,
                routing,
                state="idle",
                updated_at=res_reset.get("updated_at", _iso()),
                current_turn_id=res_reset.get("current_turn_id"),
                completion="rollback",
                target_sid=ingress.stream_id,
            )
        except Exception:
            logger.exception("failed to reset conv state after missing external event source")
        return IngressResult(
            ok=False,
            error_type="external_event_source_unavailable",
            error=err,
            http_status=503,
        )

    event_kind = _chat_event_kind(has_external_event=has_external_event, requested_kind=requested_kind)
    event_source_id = _chat_event_source_id(
        has_external_event=has_external_event,
        external_event=external_event,
        requested_kind=requested_kind,
    )
    if payload.event is not None:
        payload.event.kind = event_kind
        payload.event.agent_id = target_agent_id
        payload.event.event_source_id = event_source_id
        payload.event.reactive = external_event_reactive if has_external_event else True
        payload.event.source = f"ingress.{ingress.transport}"

    external_event_source = build_conversation_external_event_source(
        redis=redis_async,
        tenant=tenant_id,
        project=project_id,
        conversation_id=conversation_id,
        user_id=session.user_id or session.fingerprint or "",
        agent_id=target_agent_id,
    )
    event_payload = (
        _external_event_envelope(
            message_data=message_data,
            text=text,
            event=external_event or {},
        )
        if has_external_event
        else {"message": text}
    )
    env = await external_event_source.publish(
        kind=event_kind,
        explicit=bool(requested_kind_explicit or has_external_event),
        target_turn_id=target_turn_id,
        active_turn_id_at_ingress=None,
        owner_turn_id=None,
        source=f"ingress.{ingress.transport}",
        event_source_id=event_source_id,
        text=text,
        payload=event_payload,
        task_payload=payload.model_dump(),
    )
    wakeup = _event_lane_wakeup_from_payload(
        payload=payload,
        event=env,
        tenant=tenant_id,
        project=project_id,
        user_id=session.user_id or session.fingerprint or "",
        conversation_id=conversation_id,
        agent_id=target_agent_id,
        reason="reactive_event",
    )

    # --- Enqueue wakeup ---
    enqueue_started_at = time.monotonic()
    try:
        success, reason, stats = await chat_queue_manager.enqueue_chat_task_atomic(
            session.user_type,
            wakeup.model_dump(),
            session,
            request_context,
            ingress.entrypoint,
        )
    except Exception as e:
        logger.exception("enqueue_chat_task_atomic failed: %s", e)
        success, reason, stats = False, "internal_error", {}
    enqueue_ms = int((time.monotonic() - enqueue_started_at) * 1000)
    try:
        created_at = float(payload.meta.created_at) if payload.meta else None
    except Exception:
        created_at = None
    ingress_to_enqueue_ms = None
    if created_at:
        try:
            ingress_to_enqueue_ms = int((time.time() - created_at) * 1000)
        except Exception:
            ingress_to_enqueue_ms = None

    logger.info(
        "enqueue_chat_task_atomic wakeup result task_id=%s event_id=%s event_seq=%s user_type=%s success=%s reason=%s enqueue_ms=%s ingress_to_enqueue_ms=%s queue_stats=%s",
        task_id,
        env.message_id,
        env.sequence,
        session.user_type.value,
        success,
        reason,
        enqueue_ms,
        ingress_to_enqueue_ms,
        stats,
    )

    if not success:
        try:
            await external_event_source.mark_failed(
                message_id=env.message_id,
                claimant_id="ingress.enqueue_failure",
                reason=f"wakeup_enqueue_failed:{reason}",
            )
        except Exception:
            logger.exception(
                "failed to mark lane event failed after wakeup enqueue failure event_id=%s",
                env.message_id,
            )
        # rollback state since nothing will process this turn
        try:
            res_reset = await app.state.conversation_browser.set_conversation_state(
                tenant=payload.actor.tenant_id,
                project=payload.actor.project_id,
                user_id=payload.user.user_id,
                conversation_id=payload.routing.conversation_id,
                new_state="idle",
                by_instance=ingress.instance_id,
                request_id=request_id,
                last_turn_id=payload.routing.turn_id,
                require_not_in_progress=False,
                user_type=payload.user.user_type,
                bundle_id=payload.routing.bundle_id,
            )
        except Exception as e:
            logger.error("Failed to reset conv state after enqueue failure: %s", e)
            res_reset = {"updated_at": _iso(), "current_turn_id": payload.routing.turn_id}

        retry_after = (
            30
            if session.user_type == UserType.ANONYMOUS
            else 45
            if session.user_type == UserType.REGISTERED
            else 60
        )
        try: # broadcast conv state rollback
            await chat_comm.emit_conv_status(
                svc,
                conv,
                routing=routing,
                state="idle",
                updated_at=res_reset.get("updated_at", _iso()),
                current_turn_id=res_reset.get("current_turn_id"),
                completion="rollback",
            )
            # legacy error for compat
            await chat_comm.emit_error(
                svc,
                conv,
                error=f"System under pressure - request rejected ({reason})",
                target_sid=ingress.stream_id,
                session_id=payload.routing.session_id,
            )
            # chat_service event (minimal inline env)
            env = {
                "type": "queue.enqueue_rejected",   # logical type
                "timestamp": _iso(),
                "ts": int(time.time() * 1000),
                "service": svc.model_dump(),
                "conversation": conv.model_dump(),
                "event": {
                    "step": "enqueue",
                    "status": "error",
                    "title": "Request rejected by queue",
                    "agent": "queue",
                },
                "data": {
                    "message": f"System under pressure - request rejected ({reason})",
                    "error_type": "queue.enqueue_rejected",
                    "http_status": 503,
                    "retry_after": retry_after,
                    "reason": reason,
                    "queue_stats": stats,
                },
                "route": "chat_service",
            }

            await chat_comm.emit(
                event="chat_service",
                data=env,
                tenant=svc.tenant,
                project=svc.project,
                session_id=payload.routing.session_id,
                target_sid=ingress.stream_id,
            )
        except Exception:
            pass

        return IngressResult(
            ok=False,
            error_type="queue.enqueue_rejected",
            error=f"System under pressure - request rejected ({reason})",
            http_status=503,
            retry_after=retry_after,
            reason=reason,
        )

    # --- Success: emit start + ack payload ---
    try:
        await chat_comm.emit_start(
            svc,
            conv,
            message=(text[:100] + "..." if len(text) > 100 else text),
            queue_stats=stats,
            target_sid=ingress.stream_id,
            session_id=session.session_id,
        )
    except Exception:
        pass

    return IngressResult(
        ok=True,
        task_id=task_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        session_id=session.session_id,
        user_type=session.user_type.value,
        queue_stats={
            **(stats or {}),
            "external_event_sequence": env.sequence,
            "event_id": env.message_id,
            "queue_payload_kind": "external_event_lane_wakeup",
        },
        event_id=env.message_id,
        external_event_sequence=int(env.sequence or 0),
    )


# -----------------------------
# Conversation status (shared)
# -----------------------------

async def get_conversation_status(
        *,
        app,
        chat_comm: ChatRelayCommunicator,
        session: UserSession,
        tenant: str,
        project: str,
        bundle_id: Optional[str],
        conversation_id: Optional[str],
        stream_id: Optional[str],
        publish: bool = True,
) -> Dict[str, Any]:
    """
    Shared implementation for conv_status.get for SSE + WS.
    """
    reg = await _load_active_registry(app, tenant, project)
    allowed_bundle_ids = list((getattr(reg, "bundles", None) or {}).keys())
    if not allowed_bundle_ids:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if bundle_id and bundle_id not in allowed_bundle_ids:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv_id = conversation_id or session.session_id
    row = None
    try:
        row = await app.state.conversation_browser.idx.get_conversation_state_row(
            user_id=session.user_id,
            conversation_id=conv_id,
            bundle_ids=[bundle_id] if bundle_id else allowed_bundle_ids,
        )
    except Exception as e:
        logger.error("conv_status lookup failed user=%s conv=%s: %s", session.user_id, conv_id, e)

    if not row:
        exists = False
        try:
            exists = await app.state.conversation_browser.conversation_exists(
                user_id=session.user_id,
                conversation_id=conv_id,
                bundle_ids=[bundle_id] if bundle_id else allowed_bundle_ids,
            )
        except Exception as e:
            logger.error("conv_status existence fallback failed user=%s conv=%s: %s", session.user_id, conv_id, e)
        if not exists:
            raise HTTPException(status_code=404, detail="Conversation not found")
        row = {}
    tags = row.get("tags", [])
    if "conv.state:in_progress" in tags:
        state = "in_progress"
    elif "conv.state:error" in tags:
        state = "error"
    else:
        state = "idle"
    ts = row.get("ts")
    updated_at = ts.isoformat() + "Z" if ts else _iso()
    payload_row = row.get("payload") or {}
    current_turn_id = payload_row.get("last_turn_id")
    if publish:
        if not reg:
            logger.warning(
                "conv_status.get: bundle registry unavailable; falling back to provided bundle_id/default placeholder "
                "(tenant=%s project=%s session=%s)",
                tenant,
                project,
                session.session_id,
            )
        bundle_id_val = bundle_id or (reg.default_bundle_id if reg else "unknown")
        if not bundle_id_val:
            bundle_id_val = "unknown"
            logger.warning(
                "conv_status.get: bundle_id missing; using placeholder (tenant=%s project=%s session=%s)",
                tenant,
                project,
                session.session_id,
            )

        routing = ExternalEventRouting(
            session_id=session.session_id,
            conversation_id=conv_id,
            turn_id=current_turn_id,
            socket_id=stream_id,
            bundle_id=bundle_id_val,
        )
        svc = ServiceCtx(request_id=str(uuid.uuid4()), user=session.user_id, tenant=tenant, project=project)
        conv = ConversationCtx(
            session_id=session.session_id,
            conversation_id=conv_id,
            turn_id=current_turn_id,
        )

        try:
            await chat_comm.emit_conv_status(
                svc,
                conv,
                routing=routing,
                state=state,
                updated_at=updated_at,
                current_turn_id=current_turn_id,
                target_sid=stream_id,
            )
        except Exception as e:
            logger.error("emit_conv_status failed: %s", e)

    return {
        "conversation_id": conv_id,
        "state": state,
        "updated_at": updated_at,
        "current_turn_id": current_turn_id,
    }

def build_sse_request_context(
        request: Request,
        session: UserSession,
        bearer_token: Optional[str] = None,
        id_token: Optional[str] = None,
        *,
        client_ip_fallback: str = "sse",
) -> RequestContext:
    """
    Build RequestContext for SSE endpoints.

    Rule:
      - Use session.request_context if present.
      - If auth/id_token missing there, fill from explicit args.
      - If still missing, fall back to request headers.
    """

    base = getattr(session, "request_context", None)

    # client ip
    client_ip = client_ip_fallback
    try:
        if isinstance(base, RequestContext) and base.client_ip:
            client_ip = base.client_ip
        elif request.client and request.client.host:
            client_ip = request.client.host
    except Exception:
        pass

    # user agent
    user_agent = ""
    if isinstance(base, RequestContext) and base.user_agent:
        user_agent = base.user_agent
    else:
        user_agent = request.headers.get("user-agent", "")

    # authorization header
    auth_header = None
    if isinstance(base, RequestContext) and base.authorization_header:
        auth_header = base.authorization_header
    elif bearer_token:
        auth_header = f"Bearer {bearer_token}"
    else:
        auth_header, _ = resolve_auth_from_headers_and_cookies(
            request.headers.get("authorization"),
            None,
            request.cookies,
        )

    # id token
    resolved_id_token = None
    if isinstance(base, RequestContext) and base.id_token:
        resolved_id_token = base.id_token
    elif id_token:
        resolved_id_token = id_token
    else:
        _, resolved_id_token = resolve_auth_from_headers_and_cookies(
            None,
            request.headers.get(get_settings().AUTH.ID_TOKEN_HEADER_NAME)
            or request.headers.get(get_settings().AUTH.ID_TOKEN_HEADER_NAME.lower()),
            request.cookies,
        )

    return RequestContext(
        client_ip=client_ip,
        user_agent=user_agent,
        authorization_header=auth_header,
        id_token=resolved_id_token,
    )

def build_ws_connect_request_context(
        environ: dict,
        auth: Optional[dict],
) -> RequestContext:

    xff = environ.get("HTTP_X_FORWARDED_FOR")
    client_ip = (xff.split(",")[0].strip() if xff else None) or environ.get("REMOTE_ADDR") or "unknown"
    user_agent = environ.get("HTTP_USER_AGENT", "")
    bearer, id_token = resolve_socket_auth_tokens(auth, environ)
    auth_header = f"Bearer {bearer}" if bearer else None

    return RequestContext(
        client_ip=client_ip,
        user_agent=user_agent,
        authorization_header=auth_header,
        id_token=id_token
    )


def build_ws_chat_request_context() -> RequestContext:
    # For chat_message we often don’t have the raw environ;
    # you already used synthetic values.
    return RequestContext(
        client_ip="socket.io",
        user_agent="socket.io-client",
        authorization_header=None,
    )

async def upgrade_session_from_tokens(
        *,
        session: UserSession,
        ctx,
        bearer_token: Optional[str],
        id_token: Optional[str],
        gateway_adapter,
        chat_comm: ChatRelayCommunicator,
        stream_id: Optional[str],
) -> UserSession:
    # No tokens → nothing to do
    if not bearer_token and not id_token:
        return session

    # Already non-anonymous with a real user → keep as-is
    if session.user_type != UserType.ANONYMOUS and session.user_id:
        return session

    auth_manager = get_auth_manager()

    try:
        user = await auth_manager.authenticate_with_both(
            access_token=bearer_token or "",
            id_token=id_token,
        )
    except AuthenticationError as e:
        svc = ServiceCtx(request_id=str(uuid.uuid4()), user=session.user_id or session.fingerprint)
        conv = ConversationCtx(
            session_id=session.session_id,
            conversation_id=session.session_id,
            turn_id=new_turn_id(),
        )
        # This won't work if this is the connection flow because the relay is not connected.
        await chat_comm.emit_error(
            svc,
            conv,
            error=f"Authentication failed: {e.message}",
            target_sid=stream_id,
            session_id=session.session_id,
        )
        raise e

    roles = user.roles or []
    if any(r in PRIVILEGED_ROLES for r in roles):
        user_type = UserType.PRIVILEGED
    else:
        user_type = UserType.REGISTERED

    user_data = {
        "user_id": user.id,
        "username": user.username,
        "roles": roles,
        "permissions": user.permissions or [],
        "email": user.email,
    }

    new_session = await gateway_adapter.gateway.get_or_create_session_with_econ_role(
        ctx,
        user_type=user_type,
        user_data=user_data,
    )

    # Persist context on the session if you like
    new_session.request_context = ctx
    return new_session

# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter
#
# chat/sdk/tools/backends/summary/conversation_title.py
"""
Reusable conversation-title generator.

A framework-neutral SDK utility that proposes a short human-readable title for a
conversation from the user's message (and, optionally, the assistant's answer).

It is the generalization of the workspace bundle's "gate" title step, minus the
gate identity: any caller — a bundle agent, a background job, an entrypoint — can
ask for a title with a single call.

Design contract
---------------
The primary contract is intentionally tiny::

    title = await generate_conversation_title(svc, user_message="...")

`title` is a plain string ("" on empty / malformed model output — fail open).

Everything else is optional and layers on richer behavior:

* ``on_thinking_delta`` — forward the model's "thinking" channel to a UI in real
  time (streamed as the model produces it).
* ``ctx_browser`` — when present, the call is wrapped in ``retry_with_compaction``
  so a token-limit error auto-compacts the rendered timeline and retries. The
  human message is then built from the browser's timeline blocks instead of the
  raw ``user_message`` text.
* ``output_model`` — override the structured output model (e.g. a bundle model
  that carries extra fields alongside ``conversation_title``); the utility maps
  the configured title field back to the returned string.

Callers that need the parsed payload and the raw channel dump (for logging or to
persist extra output fields) should use :func:`run_conversation_title`, which
returns ``(payload_dict, channel_dump_dict)``. :func:`generate_conversation_title`
is a thin wrapper over it that returns just the title string.

The two output channels follow the standard streaming protocol:

* ``<channel:thinking>``  — free-form text, shown to the user as a "thinking"
  indicator (forwarded via ``on_thinking_delta``).
* ``<channel:output>``    — structured JSON validated against the output model.

The model is addressed by ``role`` (default ``"gate.simple"``), which the caller's
model configuration must resolve to a concrete model.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, Field

from kdcube_ai_app.infra.service_hub.inventory import (
    ModelServiceBase,
    create_cached_system_message,
    create_cached_human_message,
)
from kdcube_ai_app.infra.service_hub.errors import ServiceException, ServiceError
from kdcube_ai_app.apps.chat.sdk.streaming.workspace_streamer import (
    ChannelSpec,
    stream_with_channels,
)
from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.agent_retry import retry_with_compaction
from kdcube_ai_app.apps.chat.sdk.util import token_count


class TitleOut(BaseModel):
    """Default structured output: a single short conversation title."""
    conversation_title: Optional[str] = Field(
        default=None, description="Short conversation title"
    )


def build_title_system_prompt(max_words: int = 6) -> str:
    """
    Build the system prompt that instructs the model to emit a conversation title
    over the two-channel streaming protocol.

    Kept as a standalone function so callers (and tests) can reuse the exact prompt
    text, e.g. for token accounting during compaction.
    """
    return (
        "You propose a short conversation title.\n\n"
        "IMPORTANT: The THINKING channel is shown to the user.\n"
        "Keep it very short (1-2 sentences, no lists).\n\n"
        "Output protocol (strict):\n"
        "<channel:thinking> ... </channel:thinking>\n"
        "<channel:output> {\"conversation_title\": \"...\"} </channel:output>\n\n"
        "Return JSON with key:\n"
        f"- conversation_title: short title (<= {max_words} words).\n\n"
        "Rules:\n"
        "- Only emit conversation_title.\n"
        "- Do not add any other keys.\n"
    )


def _build_human_blocks(
    user_message: Optional[str],
    answer: Optional[str],
) -> List[Dict[str, Any]]:
    """Build the human-message blocks for the direct (no ctx_browser) path."""
    blocks: List[Dict[str, Any]] = []
    if user_message:
        blocks.append({"type": "text", "text": f"User message:\n{user_message}"})
    if answer:
        blocks.append({"type": "text", "text": f"Assistant answer:\n{answer}"})
    if not blocks:
        blocks.append({"type": "text", "text": "(no conversation content)"})
    return blocks


async def run_conversation_title(
    svc: ModelServiceBase,
    *,
    user_message: str = "",
    answer: Optional[str] = None,
    role: str = "gate.simple",
    agent: Optional[str] = None,
    max_words: int = 6,
    max_tokens: int = 128,
    temperature: float = 0.2,
    on_thinking_delta: Optional[Callable[..., Any]] = None,
    ctx_browser: Any = None,
    emit_status: Optional[Callable[[List[str]], Any]] = None,
    render_params: Optional[Dict[str, Any]] = None,
    sanitize_on_fail: bool = True,
    output_model: Type[BaseModel] = TitleOut,
    title_field: str = "conversation_title",
    system_prompt: Optional[str] = None,
    system_message_token_count_fn: Optional[Callable[[], int]] = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Generate a conversation title and return ``(payload, channel_dump)``.

    ``payload`` is the parsed output model dumped to a dict (always contains
    ``title_field``; empty string on malformed output). ``channel_dump`` carries
    the raw ``thinking`` and ``output`` channel text for logging/debug.

    This is the full-featured entry point. Most callers want
    :func:`generate_conversation_title`, which returns just the title string.
    """
    sys_prompt = system_prompt if system_prompt is not None else build_title_system_prompt(max_words)
    # Cached system message — reuses the KV cache across repeated calls.
    system_msg = create_cached_system_message([{"text": sys_prompt, "cache": True}])
    agent_label = agent or role

    # Streaming callback — forwards only the "thinking" channel to the UI.
    async def _emit(**kwargs):
        channel = kwargs.pop("channel", None)
        text = kwargs.get("text") or ""
        if channel == "thinking" and on_thinking_delta:
            await on_thinking_delta(text=text, completed=kwargs.get("completed", False))

    channels = [
        ChannelSpec(name="thinking", format="text", replace_citations=False, emit_marker="thinking"),
        ChannelSpec(name="output", format="json", model=output_model, replace_citations=False, emit_marker="subsystem"),
    ]

    empty_payload: Dict[str, Any] = {title_field: ""}

    def _payload_from_result(res: Any) -> Dict[str, Any]:
        """Parse the output channel into a payload dict; fail open to empty title."""
        if res and res.obj is not None and isinstance(res.obj, output_model):
            return res.obj.model_dump()
        raw = (res.raw if res else "") or ""
        if raw:
            try:
                return output_model.model_validate_json(raw).model_dump()
            except Exception:
                return dict(empty_payload)
        return dict(empty_payload)

    async def _call(*, blocks):
        # ctx_browser path supplies rendered timeline blocks; direct path builds
        # the human message from user_message (+ optional answer).
        human_blocks = blocks if blocks is not None else _build_human_blocks(user_message, answer)
        messages = [system_msg, create_cached_human_message(human_blocks)]
        results, meta = await stream_with_channels(
            svc,
            messages=messages,
            role=role,
            channels=channels,
            emit=_emit,
            agent=agent_label,
            max_tokens=max_tokens,
            temperature=temperature,
            return_full_raw=True,
        )
        service_error = (meta or {}).get("service_error")
        if service_error:
            raise ServiceException(ServiceError.model_validate(service_error))

        payload = _payload_from_result(results.get("output"))
        if title_field not in payload or payload.get(title_field) is None:
            payload[title_field] = ""

        channel_dump = {
            "thinking": (results.get("thinking").raw if results.get("thinking") else "") or "",
            "output": (results.get("output").raw if results.get("output") else "") or "",
        }
        return payload, channel_dump

    # With a ctx_browser, wrap the call so token-limit errors auto-compact & retry.
    if ctx_browser:
        if system_message_token_count_fn is None:
            system_message_token_count_fn = lambda: token_count(sys_prompt)
        return await retry_with_compaction(
            ctx_browser=ctx_browser,
            system_text_fn=lambda: sys_prompt,
            system_message_token_count_fn=system_message_token_count_fn,
            render_params=render_params,
            agent_fn=_call,
            emit_status=emit_status,
            sanitize_on_fail=sanitize_on_fail,
        )

    return await _call(blocks=None)


async def generate_conversation_title(
    svc: ModelServiceBase,
    *,
    user_message: str,
    answer: Optional[str] = None,
    role: str = "gate.simple",
    max_words: int = 6,
    max_tokens: int = 128,
    temperature: float = 0.2,
    on_thinking_delta: Optional[Callable[..., Any]] = None,
    ctx_browser: Any = None,
    emit_status: Optional[Callable[[List[str]], Any]] = None,
    render_params: Optional[Dict[str, Any]] = None,
    sanitize_on_fail: bool = True,
) -> str:
    """
    Propose a short conversation title. Returns the title string ("" on failure).

    A simple caller needs only ``user_message``::

        title = await generate_conversation_title(svc, user_message=text)

    See the module docstring for the optional streaming / compaction / override
    behavior, and :func:`run_conversation_title` for the richer
    ``(payload, channel_dump)`` contract.
    """
    payload, _ = await run_conversation_title(
        svc,
        user_message=user_message,
        answer=answer,
        role=role,
        max_words=max_words,
        max_tokens=max_tokens,
        temperature=temperature,
        on_thinking_delta=on_thinking_delta,
        ctx_browser=ctx_browser,
        emit_status=emit_status,
        render_params=render_params,
        sanitize_on_fail=sanitize_on_fail,
    )
    return (payload.get("conversation_title") or "").strip()


async def emit_conversation_title_event(
    comm: Any,
    *,
    conversation_id: str,
    turn_id: str,
    title: str,
) -> None:
    """Emit the canonical ``chat.conversation.title`` chat event.

    This is THE conversation-title event the chat component renders to update the
    conversation header live. Emitting it from one place keeps the payload
    identical across every caller — the React workflow
    (``BaseWorkflow.emit_conversation_title``) and any run-to-completion bundle
    that streams through ``comm`` — so the client renders both the same way.
    No-op on a blank title or a missing ``comm``.
    """
    title = (title or "").strip()
    if not title or comm is None:
        return
    await comm.event(
        agent="system",
        type="chat.conversation.title",
        route="chat.step",
        title="Conversation Title Updated",
        step="conversation_title",
        data={
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "title": title,
        },
        status="completed",
        broadcast=True,
    )

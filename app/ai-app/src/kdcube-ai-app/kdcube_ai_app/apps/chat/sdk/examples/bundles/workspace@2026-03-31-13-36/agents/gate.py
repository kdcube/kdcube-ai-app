# ── agents/gate.py ──
# Lightweight "gate" agent — the first LLM call in the pipeline.
#
# In this app the gate has a single job: propose a short conversation title
# on the first turn of a new conversation.
#
# The title generation itself is a shared SDK utility
# (kdcube_ai_app.apps.chat.sdk.tools.backends.summary.conversation_title). This
# module is a thin gate wrapper over it: it owns the gate identity (system
# prompt, GateOut output model, the is_new_conversation short-circuit) and
# delegates the streaming / channel parsing / compaction-retry mechanics to the
# utility.
#
# How it works:
#   1. If not a new conversation → skip (return empty defaults)
#   2. Delegate to run_conversation_title() with:
#      - the gate system prompt (emits <channel:thinking> + <channel:output>)
#      - GateOut as the structured output model
#      - the caller's on_thinking_delta / ctx_browser / render_params
#   3. On subsequent turns the gate is skipped entirely.
#
# To extend:
#   Add more fields to GateOut (e.g. route, intent, clarification_questions)
#   and update the system prompt. The orchestrator reads them from scratchpad.gate.

from __future__ import annotations

from typing import Any, Dict, Tuple, Optional, Callable, List

from pydantic import BaseModel, Field

from kdcube_ai_app.infra.service_hub.inventory import ModelServiceBase
from kdcube_ai_app.apps.chat.sdk.tools.backends.summary.conversation_title import (
    run_conversation_title,
)


class GateOut(BaseModel):
    """Structured output from the gate agent. Add fields here to extend."""
    conversation_title: str | None = Field(default=None, description="Conversation title (first turn only)")


# Gate identity: the exact system prompt the gate emits. Kept here (not in the
# shared utility) because it carries the gate's role in this pipeline.
_GATE_SYSTEM_PROMPT = (
    "You are a minimal gate agent.\n"
    "Your only job: propose a conversation title.\n\n"
    "IMPORTANT: The THINKING channel is shown to the user.\n"
    "Keep it very short (1–2 sentences, no lists).\n\n"
    "Output protocol (strict):\n"
    "<channel:thinking> ... </channel:thinking>\n"
    "<channel:output> {\"conversation_title\": \"...\"} </channel:output>\n\n"
    "Return JSON with key:\n"
    "- conversation_title: short title (≤6 words).\n\n"
    "Rules:\n"
    "- Only emit conversation_title.\n"
    "- Do not add any other keys.\n"
)


async def gate_stream(
    svc: ModelServiceBase,
    *,
    is_new_conversation: bool = False,
    on_thinking_delta=None,
    ctx_browser: Any = None,
    emit_status: Optional[Callable[[List[str]], Any]] = None,
    render_params: Optional[Dict[str, Any]] = None,
    sanitize_on_fail: bool = True,
    system_message_token_count_fn: Optional[Callable[[], int]] = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Run the gate agent. Returns (payload_dict, channel_dump_dict).
    Skipped entirely on subsequent turns (is_new_conversation=False).
    """

    # On subsequent turns there is no work for the gate
    if not is_new_conversation:
        return {"conversation_title": ""}, {"thinking": "", "output": ""}

    # Delegate to the shared title utility. Gate keeps its own system prompt and
    # GateOut model; everything else (channels, thinking stream, compaction retry)
    # is handled by the utility. role "gate.simple" resolves to a concrete model
    # via configuration; max_tokens is kept low because gate output is tiny.
    return await run_conversation_title(
        svc,
        role="gate.simple",
        agent="gate.simple",
        max_tokens=800,
        temperature=0.2,
        on_thinking_delta=on_thinking_delta,
        ctx_browser=ctx_browser,
        emit_status=emit_status,
        render_params=render_params,
        sanitize_on_fail=sanitize_on_fail,
        output_model=GateOut,
        system_prompt=_GATE_SYSTEM_PROMPT,
        system_message_token_count_fn=system_message_token_count_fn,
    )

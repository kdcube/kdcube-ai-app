# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
#
# ── stream_adapter.py ── the streaming seam (the create_agent ReAct shape) ──
#
# This is the ONE file that differs meaningfully from a linear-graph port. The
# standalone agent is `langchain.agents.create_agent`, whose graph has a LOOPING
# `model` node (the model node) and a `tools` node:
#
#     START ─▶ model ─┬─(tool calls?)─▶ tools ─▶ model ...   (loops)
#                     └────── no tool calls ─────▶ END        (final message = answer)
#
# The `model` node fires ONCE PER TOOL-DECISION CYCLE, not once per turn. There is
# NO dedicated `answer` node (unlike the lg-solution port, whose linear graph had
# one). So "stream the answer" cannot mean "stream every token the model node
# emits" — that would stream the model's intermediate tool-deciding turns too.
#
# THE RULE (why this file exists):
#   Only the LAST model turn — the one that returns a message with NO tool call —
#   is the answer. So:
#     • Stream a model token as answer text ONLY when it carries visible content
#       and NO tool-call chunk. In the standard ReAct loop a tool-deciding turn
#       emits empty content + a tool call, so this naturally suppresses it. (A
#       model that emits "preamble" text before a tool call in the same turn is
#       the one caveat; the ReAct loop's tool turns emit no visible text.)
#     • Surface each `tools` run as a step (tool start -> running, end ->
#       completed), so the user sees the loop working.
#     • The authoritative final answer is the last model turn's message content
#       when it makes no tool call — used to emit a single delta on the offline /
#       non-streaming path, and as the returned value.
#
# Compaction (SummarizationMiddleware) runs in its OWN before_model middleware node,
# not the `model` node, so its summarization tokens never reach this streaming path.
#
# The teaching point: a DIFFERENT agent shape swaps ONLY this file. identity.py,
# entrypoint.py, and the vendored agent are unchanged from any other port; the
# looping-node handling lives here and nowhere else.

from __future__ import annotations

import logging
from typing import Any, Dict

from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx

LOGGER = logging.getLogger("kdcube.ported_langgraph_agents.stream_react")


def _content_text(content: Any) -> str:
    """Normalize a LangChain message chunk's ``content`` to text.

    Newer chat models (e.g. OpenAI's Responses API) stream ``content`` as a LIST
    of content blocks, not a plain str — so ``answer += chunk.content`` would
    raise ``TypeError: can only concatenate str (not "list") to str``, and a
    ``str(content)`` fallback would render the raw block list. Join the text.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


async def stream_react_turn(
    graph: Any,
    inputs: Dict[str, Any],
    run_config: Dict[str, Any],
    *,
    agent_node: str = "model",
) -> str:
    """Run one turn of a create_agent ReAct ``graph`` and stream it through the
    current communicator. Returns the final answer text (also set on the platform
    state by the caller, so the turn is streamed live AND recorded for reload).

    ``agent_node`` is the looping model node whose FINAL (no-tool-call) turn is the
    user-visible answer.
    """
    idx = 0
    answer = ""
    # Per-agent-turn flag: does the CURRENT agent turn carry a tool call? Reset at
    # each agent-node start, so we can tell an intermediate tool-deciding turn from
    # the final answer turn.
    turn_has_tool_call = False

    async for event in graph.astream_events(inputs, run_config, version="v2"):
        kind = event.get("event")
        name = event.get("name")
        node = (event.get("metadata") or {}).get("langgraph_node")

        if kind == "on_chain_start" and name == agent_node:
            # A new agent turn begins — until proven otherwise it might be final.
            turn_has_tool_call = False

        elif kind == "on_chat_model_stream" and node == agent_node:
            chunk = (event.get("data") or {}).get("chunk")
            # A tool-call chunk marks this agent turn as a tool-deciding turn: it
            # is NOT the answer, so never stream it as answer text.
            if getattr(chunk, "tool_call_chunks", None):
                turn_has_tool_call = True
                continue
            token = _content_text(getattr(chunk, "content", ""))
            if token and not turn_has_tool_call:
                await comm_ctx.delta(text=token, index=idx, marker="answer")
                idx += 1
                answer += token

        elif kind == "on_tool_start":
            # Surface each tool run as a progress step (the loop working).
            LOGGER.info("[ported-langgraph] lg-react tool START: %s", name)
            await comm_ctx.step(step=str(name), status="running")

        elif kind == "on_tool_end":
            LOGGER.info("[ported-langgraph] lg-react tool END: %s", name)
            await comm_ctx.step(step=str(name), status="completed")

        elif kind == "on_chain_end" and name == agent_node:
            # The agent turn just finished. Read its last message (authoritative):
            #   - has tool_calls  -> intermediate turn; the next cycle continues.
            #   - no tool_calls   -> the FINAL answer. If nothing streamed live
            #     (offline / non-streaming model), emit the content as one delta.
            out = (event.get("data") or {}).get("output") or {}
            msgs = out.get("messages") if isinstance(out, dict) else None
            last = msgs[-1] if msgs else None
            if last is not None and not getattr(last, "tool_calls", None):
                content = _content_text(getattr(last, "content", ""))
                if not answer and content:
                    answer = content
                    await comm_ctx.delta(text=answer, index=idx, marker="answer")
                    idx += 1

    LOGGER.info("[ported-langgraph] lg-react turn complete: answer_len=%d", len(answer))
    await comm_ctx.complete(data={"final_answer": answer})
    return answer

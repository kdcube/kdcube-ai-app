"""Conversation compaction for the research graph (the `compact` node).

Unlike the prebuilt ReAct agent — whose ``messages`` list IS the model input — this
graph's ``answer`` node sends only the CURRENT turn's system+user to the model and
never replays the conversation. So its model-input context is ALREADY bounded per
turn; there is no unbounded ``messages`` growth feeding the model to trim.

What this graph lacked was multi-turn CONTINUITY: nothing carried "what we already
discussed" into a later answer. The ``compact`` node adds it in a bounded way,
reusing the same accounted-summary pattern as lg-react:

  - SUMMARIZE (default) — LangMem's ``asummarize_messages`` folds the checkpointed
    history into a running summary (extended across turns via the stored
    ``RunningSummary``) plus a verbatim tail, on a DISTINCT accounted summary role.
  - TRIM (fallback / offline) — keep only the recent turns within a token budget,
    no extra model call. This is also the DEGRADED path when no summary model is
    wired (offline), so a turn never fails over compaction.

The node returns a bounded PLAIN-TEXT block the answer node injects as
"Conversation so far". Because the summary LLM call runs in the ``compact`` node
(not the ``answer`` node the stream adapter keys on), its tokens are never streamed
to the user as the answer.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from langchain_core.messages import trim_messages

from .config import Config


def _is_human(msg: Any) -> bool:
    if getattr(msg, "type", None) == "human":
        return True
    # tuple form ("user"/"human", text)
    if isinstance(msg, (tuple, list)) and msg:
        return str(msg[0]).lower() in ("user", "human")
    return False


def _msg_role_text(msg: Any) -> Tuple[str, str]:
    if isinstance(msg, (tuple, list)) and len(msg) >= 2:
        return str(msg[0]), str(msg[1])
    role = getattr(msg, "type", "") or ""
    content = getattr(msg, "content", "") or ""
    if not isinstance(content, str):
        # multimodal content: keep only text parts
        parts = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
        content = " ".join(parts)
    return str(role), content


def _messages_to_text(messages: List[Any]) -> str:
    lines = []
    for m in messages or []:
        role, text = _msg_role_text(m)
        text = (text or "").strip()
        if text:
            lines.append(f"{role or 'message'}: {text}")
    return "\n".join(lines)


def _approx_token_counter(messages) -> int:
    total = 0
    for m in messages or []:
        _role, text = _msg_role_text(m)
        total += max(1, len(text or "") // 4)
    return total


async def build_history_summary(
    messages: List[Any],
    *,
    summary_model: Any,
    config: Config,
    prior_summary: Any = None,
) -> Tuple[str, Any]:
    """Bound the prior conversation into a text block for the answer prompt.

    Returns ``(history_text, running_summary)``. ``running_summary`` (a LangMem
    ``RunningSummary`` or None) is carried in graph state so the next turn extends
    the summary rather than rebuilding it. The CURRENT turn's trailing user message
    is dropped (it is already the answer prompt's question)."""
    history = list(messages or [])
    if history and _is_human(history[-1]):
        history = history[:-1]
    if not history:
        return "", prior_summary

    if summary_model is not None and config.context_strategy == "summarize":
        try:
            from langmem.short_term import asummarize_messages

            result = await asummarize_messages(
                history,
                running_summary=prior_summary,
                model=summary_model,
                max_tokens=config.ctx_tokens,
                max_tokens_before_summary=config.summary_trigger_tokens,
                max_summary_tokens=config.summary_max_tokens,
            )
            return _messages_to_text(result.messages), result.running_summary
        except Exception:
            # Any summarization failure degrades to trim — never fail the turn.
            pass

    # Trim fallback: keep the most recent turns within the token budget.
    try:
        bounded = trim_messages(
            history,
            max_tokens=config.ctx_tokens,
            token_counter=_approx_token_counter,
            strategy="last",
            start_on="human",
            include_system=True,
            allow_partial=False,
        )
    except Exception:
        bounded = history
    return _messages_to_text(bounded or history), prior_summary

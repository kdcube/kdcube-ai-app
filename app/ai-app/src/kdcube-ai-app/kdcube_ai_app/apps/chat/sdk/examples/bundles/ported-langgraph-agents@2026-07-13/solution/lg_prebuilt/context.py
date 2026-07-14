"""Context management (compaction) for the prebuilt ReAct agent.

The conversation IS the ``messages`` list, persisted by the checkpointer (Postgres)
keyed by ``thread_id``. Left unbounded, that list grows every turn and every model
call would re-send the whole history — unbounded context and cost.

``build_context_middleware(config, summary_model)`` returns the middleware list
``create_agent`` runs to bound what the model sees each turn WITHOUT deleting stored
history (the checkpointer still holds every turn). When a summary model is present
AND ``config.context_strategy == "summarize"`` it returns a single
``SummarizationMiddleware``:

  - It folds older turns into a summary once the conversation exceeds
    ``config.summary_trigger_tokens`` and keeps the most recent
    ``config.summary_keep_messages`` messages verbatim.
  - Its summarization LLM call runs on a DISTINCT accounted role
    (``lg-react.summary``) and executes in its own ``before_model`` middleware node
    (``SummarizationMiddleware.before_model``), NOT the ``model`` node the stream
    adapter keys on — so its tokens are never streamed to the user as the answer.

Otherwise the list is empty (no middleware): the offline path (no summary model),
and the ``context_strategy == "trim"`` path. Summarization needs a model to run, and
offline turns are short, so running with no middleware keeps a turn from ever failing
over context management.
"""
from __future__ import annotations

from typing import Any, List

from .config import Config


def build_context_middleware(config: Config, summary_model: Any = None) -> List[Any]:
    """Return the compaction middleware for ``create_agent``.

    ``summary_model`` is a LangChain chat model on a DISTINCT accounted summary
    role. When it is present and ``config.context_strategy == "summarize"`` the
    list holds one ``SummarizationMiddleware``; otherwise it is empty (the offline /
    no-summary-model / ``context_strategy="trim"`` path runs with no middleware)."""
    if summary_model is None or config.context_strategy != "summarize":
        return []
    from langchain.agents.middleware import SummarizationMiddleware

    return [
        SummarizationMiddleware(
            model=summary_model,
            # Fold older turns into a summary once the conversation exceeds this.
            trigger=("tokens", config.summary_trigger_tokens),
            # Keep this many of the most recent messages verbatim after summarizing.
            keep=("messages", config.summary_keep_messages),
        )
    ]

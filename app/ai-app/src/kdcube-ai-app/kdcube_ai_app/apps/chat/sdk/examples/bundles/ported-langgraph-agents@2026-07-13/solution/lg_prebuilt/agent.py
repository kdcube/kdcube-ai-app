"""Build the prebuilt ReAct agent.

``build_agent`` returns the compiled graph from ``langchain.agents.create_agent`` —
the standard ReAct loop everyone builds:

    START -> model -> (tools -> model)* -> END

The ``model`` node calls the model; if the model returns tool calls, the ``tools``
node runs them and control loops back to ``model``. The loop ends when the model
returns a message with NO tool calls — that final message is the answer.

Everything is injectable so the same graph builder serves the standalone CLI and,
later, a hosting platform: pass your own ``model`` (e.g. an accounted one),
``tools`` (plain or MCP-loaded), and ``checkpointer`` without touching this file.
"""
from __future__ import annotations

from typing import Any, List, Optional

from langchain.agents import create_agent

from .config import Config, get_config
from .context import build_context_middleware
from .llm import build_chat_model
from .tools import build_plain_tools


SYSTEM_PROMPT = (
    "You are a concise, helpful assistant. Use the available tools when they help "
    "answer accurately — the calculator for arithmetic, the unit converter for "
    "conversions, and the knowledge search for questions about LangGraph and this "
    "agent's own design. When you have enough to answer, answer directly and cite "
    "any knowledge-base titles in brackets."
)

# The create_agent graph's node names (stable across the ReAct loop):
# 'model' is the LOOPING model node, 'tools' runs tool calls. The stream adapter
# keys token streaming on this model node, so this constant must match it exactly.
AGENT_NODE = "model"
TOOLS_NODE = "tools"


def build_agent(
    config: Optional[Config] = None,
    *,
    model: Any = None,
    tools: Optional[List[Any]] = None,
    checkpointer: Any = None,
    summary_model: Any = None,
):
    """Build and compile the prebuilt ReAct agent.

    - ``model``        — a LangChain chat model; defaults to the standalone model
                         (real online, deterministic stub offline).
    - ``tools``        — the tool list to bind; defaults to the plain local tools.
    - ``checkpointer`` — short-term memory across turns; ``None`` is valid (the
                         structure can be inspected without one).
    - ``summary_model``— a LangChain chat model on a DISTINCT accounted summary
                         role, used by the compaction ``SummarizationMiddleware`` to
                         fold older turns into a summary. ``None`` (offline / no
                         model service) runs the turn with no middleware. See
                         context.py.
    """
    config = config or get_config()
    model = model if model is not None else build_chat_model(config)
    tools = tools if tools is not None else build_plain_tools()

    return create_agent(
        model,
        tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        # Bound the model's per-turn context view (the checkpointer keeps the full
        # history; the middleware summarizes older turns). See context.py.
        middleware=build_context_middleware(config, summary_model=summary_model),
    )

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Conversation compaction — summarization that runs off the answer node.

Both agents compact a growing conversation to bound the model's view:

  - lg-react — ``build_context_middleware`` returns a LangChain
    ``SummarizationMiddleware`` when a summary model is present and the strategy is
    "summarize"; it returns an empty list (no middleware) when there is no summary
    model (offline) or the strategy is "trim".
  - lg-solution — ``build_history_summary`` folds prior turns into a bounded text
    block, dropping the current turn (already in the answer prompt) and degrading to
    a recent-turns trim offline.

Streaming isolation (asserted structurally, proven by the stream adapters keying on
the ANSWER node): the summary work runs in a NON-answer node — lg-react's
``SummarizationMiddleware.before_model`` node, lg-solution's "compact" node — so its
tokens are never streamed to the user as the answer.

Fully offline — no model, no network, no DB.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents.middleware import SummarizationMiddleware

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _prebuilt_context():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "solution" / "lg_prebuilt" / "context.py")
    return m


def _prebuilt_agent_module():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "solution" / "lg_prebuilt" / "agent.py")
    return m


def _prebuilt_llm_module():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "solution" / "lg_prebuilt" / "llm.py")
    return m


def _solution_context():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "solution" / "lg_solution" / "context.py")
    return m


def _entrypoint_module():
    _n, m = load_dynamic_module_for_path(BUNDLE_ROOT / "entrypoint.py")
    return m


def _prebuilt_config(strategy="summarize"):
    return SimpleNamespace(
        context_strategy=strategy,
        summary_trigger_tokens=2000,
        summary_keep_messages=20,
    )


def _solution_config(strategy="summarize"):
    return SimpleNamespace(
        context_strategy=strategy,
        ctx_tokens=2000,
        summary_trigger_tokens=100000,  # high -> below trigger, no LLM call in tests
        summary_max_tokens=256,
    )


# ── lg-react: SummarizationMiddleware vs no middleware ────────────────────────

def _stub_summary_model():
    # SummarizationMiddleware needs a real BaseChatModel (it reads `_llm_type` to
    # pick a token counter); the offline stub is one, so no network is touched.
    return _prebuilt_llm_module().StubChatModel()


def test_prebuilt_middleware_is_summarization_when_summary_model_present() -> None:
    ctx = _prebuilt_context()
    mw = ctx.build_context_middleware(_prebuilt_config("summarize"), summary_model=_stub_summary_model())
    assert len(mw) == 1
    assert isinstance(mw[0], SummarizationMiddleware)
    # Configured off our config knobs: token trigger + messages-to-keep.
    assert mw[0].trigger == ("tokens", 2000)
    assert mw[0].keep == ("messages", 20)
    # It runs as its OWN before_model node, NOT the model node the stream adapter
    # keys on, so its summarization tokens are never streamed as the answer.
    ep = _entrypoint_module()
    assert ep.PREBUILT_AGENT_NODE == "model"
    assert mw[0].name != ep.PREBUILT_AGENT_NODE  # "SummarizationMiddleware" != "model"


def test_prebuilt_no_middleware_offline() -> None:
    ctx = _prebuilt_context()
    # No summary model (offline) -> no middleware; the turn still runs.
    assert ctx.build_context_middleware(_prebuilt_config("summarize"), summary_model=None) == []


def test_prebuilt_trim_strategy_never_summarizes_even_with_a_model() -> None:
    ctx = _prebuilt_context()
    assert ctx.build_context_middleware(_prebuilt_config("trim"), summary_model=_stub_summary_model()) == []


# ── lg-solution: build_history_summary ───────────────────────────────────────

def _history():
    return [
        HumanMessage(content="q1: what is a checkpointer?"),
        AIMessage(content="a1: it persists graph state."),
        HumanMessage(content="current turn question"),
    ]


def test_solution_history_summary_offline_trims_and_drops_current_turn() -> None:
    ctx = _solution_context()
    text, running = asyncio.run(
        ctx.build_history_summary(
            _history(), summary_model=None, config=_solution_config("summarize"),
        )
    )
    # Offline trim path: prior turns rendered, current (last human) turn dropped.
    assert "q1: what is a checkpointer?" in text
    assert "current turn question" not in text
    assert running is None


def test_solution_history_summary_empty_when_no_prior_turns() -> None:
    ctx = _solution_context()
    text, running = asyncio.run(
        ctx.build_history_summary(
            [HumanMessage(content="only the current turn")],
            summary_model=None, config=_solution_config("summarize"),
        )
    )
    assert text == ""
    assert running is None


def test_solution_history_summary_below_trigger_passes_prior_turns_verbatim() -> None:
    # With a summary model + summarize strategy but history below the trigger,
    # langmem returns the prior turns verbatim (no LLM call), so the dummy model is
    # never invoked — exercising the real asummarize_messages wiring offline.
    ctx = _solution_context()
    text, _running = asyncio.run(
        ctx.build_history_summary(
            _history(), summary_model=object(), config=_solution_config("summarize"),
        )
    )
    assert "q1: what is a checkpointer?" in text
    assert "current turn question" not in text


def test_prebuilt_model_node_is_named_model() -> None:
    # The stream adapter keys token streaming on the model node via PREBUILT_AGENT_NODE;
    # the create_agent graph's model node must be exactly that name.
    agent_mod = _prebuilt_agent_module()
    ep = _entrypoint_module()
    assert agent_mod.AGENT_NODE == "model"
    assert ep.PREBUILT_AGENT_NODE == "model"
    stub = _prebuilt_llm_module().StubChatModel()
    graph = agent_mod.build_agent(model=stub, tools=[], summary_model=stub)
    nodes = set(graph.get_graph().nodes.keys())
    assert agent_mod.AGENT_NODE in nodes  # "model" node present
    # The summarization runs in its OWN node, distinct from the model node.
    assert "SummarizationMiddleware.before_model" in nodes


def test_prebuilt_summarization_middleware_runs_inside_create_agent_offline() -> None:
    # Prove the wiring EXECUTES: a create_agent built with a SummarizationMiddleware
    # runs a short turn end to end (below the summary trigger, so the summary model is
    # never called), the StubChatModel answers, and the graph does not crash.
    agent_mod = _prebuilt_agent_module()
    stub = _prebuilt_llm_module().StubChatModel()
    graph = agent_mod.build_agent(model=stub, tools=[], summary_model=stub)
    out = asyncio.run(graph.ainvoke({"messages": [("user", "just say hello")]}))
    msgs = out["messages"]
    assert msgs and getattr(msgs[-1], "content", "")


def test_solution_compact_is_a_step_node_but_not_the_answer_node() -> None:
    ep = _entrypoint_module()
    assert "compact" in ep.SOLUTION_STEP_NODES
    assert "compact" != ep.SOLUTION_ANSWER_NODE
    # Distinct accounted summary roles (not the answer roles).
    assert ep.SOLUTION_SUMMARY_ROLE == "lg-solution.summary"
    assert ep.PREBUILT_SUMMARY_ROLE == "lg-react.summary"
    assert ep.SOLUTION_SUMMARY_ROLE != ep.SOLUTION_ANSWER_ROLE
    assert ep.PREBUILT_SUMMARY_ROLE != ep.PREBUILT_ANSWER_ROLE

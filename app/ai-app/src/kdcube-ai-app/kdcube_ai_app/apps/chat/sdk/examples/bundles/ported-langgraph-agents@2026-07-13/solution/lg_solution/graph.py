"""The main research-assistant graph.

Shape:

    START -> compact -> retrieve -> plan -> (delegate?) -> answer -> END
                                              |               ^
                                              +--- subagent --+   (conditional)

Nodes:
  - compact  : fold the checkpointed conversation history into a bounded running
               summary (multi-turn continuity), on a DISTINCT accounted summary
               role; degrades to a recent-turns trim offline (see context.py)
  - retrieve : pull KB documents + this user's memories for the question
  - plan     : the model drafts a plan and decides whether to delegate a
               scoped sub-question to the subagent
  - delegate : run the subagent sub-graph (only if plan asked for it)
  - answer   : stream the final grounded answer (multimodal when the turn carried
               image/PDF attachments), then persist a memory note

The compiled graph takes a checkpointer (Postgres in the CLI) keyed by
thread_id, so conversation state survives across process runs.
"""
from __future__ import annotations

import json
from typing import Annotated, Any, List, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .context import build_history_summary
from .deps import Deps, build_deps
from .knowledge import KBHit
from .memory import MemoryHit
from .subagent import build_subagent


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    question: str
    kb_hits: List[KBHit]
    memories: List[MemoryHit]
    plan: str
    needs_subagent: bool
    sub_question: str
    sub_finding: str
    answer: str
    # Current turn's multimodal attachment blocks (image/document), threaded in by
    # the platform so the answer model sees them; text-only turns leave this empty.
    attachments: List[Any]
    # Bounded prior-conversation continuity produced by the `compact` node.
    history_summary: str
    # LangMem RunningSummary carried across turns so the summary is extended, not
    # rebuilt (persisted in the checkpointer alongside the rest of the state).
    running_summary: Any


def build_graph(deps: Deps | None = None, checkpointer=None):
    """Build and compile the main graph. `checkpointer` is optional so the
    structure can be inspected without a DB; the CLI passes a Postgres saver."""
    deps = deps or build_deps()
    subagent = build_subagent(deps)

    # -- nodes --------------------------------------------------------------

    async def compact(state: AgentState) -> dict:
        # Bound the prior conversation into a running summary (multi-turn
        # continuity) on the DISTINCT accounted summary role. Best-effort: any
        # failure / no summary model degrades to a trim (see context.py), so the
        # turn never fails over compaction. Its model tokens carry
        # langgraph_node="compact" (not "answer"), so they are never streamed as
        # the answer.
        try:
            summary_model = deps.llm.summary_chat_model()
            text, running = await build_history_summary(
                state.get("messages") or [],
                summary_model=summary_model,
                config=deps.config,
                prior_summary=state.get("running_summary"),
            )
        except Exception:
            text, running = "", state.get("running_summary")
        return {"history_summary": text, "running_summary": running}

    async def retrieve(state: AgentState) -> dict:
        # Async so the embedding + pgvector calls run on the event loop within
        # the turn's bound accounting context: @track_embedding bills this turn
        # and the processor loop never blocks. (A sync node would be offloaded to
        # an executor thread that loses the accounting contextvar — the gap this
        # conversion closes.)
        q = state["question"]
        # Retrieval is best-effort: a missing/unreachable DB degrades to empty
        # context (with a clear stderr note) rather than crashing the turn.
        try:
            kb_hits = await deps.knowledge.search(q, k=4)
        except Exception as e:  # noqa: BLE001 - prototype degrades gracefully
            print(f"  [retrieve] KB unavailable: {e}", file=__import__("sys").stderr)
            kb_hits = []
        try:
            memories = await deps.memory.recall(state["user_id"], q, k=5)
        except Exception as e:  # noqa: BLE001
            print(f"  [retrieve] memory unavailable: {e}", file=__import__("sys").stderr)
            memories = []
        return {"kb_hits": kb_hits, "memories": memories}

    async def plan(state: AgentState) -> dict:
        kb = "\n".join(f"- {h.title}: {h.text[:160]}" for h in state["kb_hits"]) or "(none)"
        mem = "\n".join(f"- {m.text}" for m in state["memories"]) or "(none)"
        system = (
            "You are the planner for a research assistant. Given the question, KB "
            "excerpts and user memories, decide whether a deeper scoped sub-question "
            "should be delegated to a research subagent. Respond as strict JSON: "
            '{"plan": str, "delegate": bool, "sub_question": str}. '
            "Set delegate false and sub_question \"\" when the KB already suffices."
        )
        user = (
            f"Question: {state['question']}\n\n"
            f"KB excerpts:\n{kb}\n\nUser memories:\n{mem}"
        )
        raw = await deps.llm.chat(system, user)
        plan_text, delegate, sub_q = _parse_plan(raw, state["question"], deps.config.offline)
        return {"plan": plan_text, "needs_subagent": delegate, "sub_question": sub_q}

    async def delegate(state: AgentState) -> dict:
        result = await subagent.ainvoke({"sub_question": state["sub_question"]})
        return {"sub_finding": result.get("finding", "")}

    async def answer(state: AgentState) -> dict:
        kb = "\n\n".join(f"[{h.title}] {h.text}" for h in state["kb_hits"]) or "(no KB matches)"
        mem = "\n".join(f"- {m.text}" for m in state["memories"]) or "(no stored memories)"
        sub = state.get("sub_finding") or "(subagent not used)"
        history = (state.get("history_summary") or "").strip() or "(no earlier conversation)"
        system = (
            "You are a helpful research assistant. Answer the user's question using "
            "the knowledge-base context, the subagent finding, the earlier "
            "conversation, and what you remember about this user. When the user "
            "attaches an image or document, use it. Cite KB titles in brackets when "
            "relevant. Be direct."
        )
        user = (
            f"Question: {state['question']}\n\n"
            f"Conversation so far:\n{history}\n\n"
            f"Knowledge base:\n{kb}\n\n"
            f"Subagent finding:\n{sub}\n\n"
            f"User memories:\n{mem}"
        )

        model = deps.llm.chat_model()
        if model is not None:
            # Stream from the raw LangChain model so on_chat_model_stream events
            # surface through astream_events for the CLI/UI. When the turn carried
            # attachments, the user turn becomes a multimodal HumanMessage whose
            # content is [text, image/document blocks...]; text-only stays a plain
            # string. The blocks flow verbatim through KDCubeChatModel's provider
            # normalizers (see platform/attachments.py).
            from langchain_core.messages import HumanMessage, SystemMessage

            attachments = state.get("attachments") or []
            human_content = [{"type": "text", "text": user}, *attachments] if attachments else user
            text = ""
            async for chunk in model.astream(
                [SystemMessage(content=system), HumanMessage(content=human_content)]
            ):
                text += chunk.content or ""
            answer_text = text
        else:
            answer_text = await deps.llm.chat(system, user)

        # Persist a lightweight memory note so future turns recall this exchange.
        try:
            await deps.memory.remember(state["user_id"], f"Asked: {state['question']} -> {answer_text[:200]}")
        except Exception:
            # Memory persistence is best-effort in the prototype; never fail the turn.
            pass

        return {"answer": answer_text, "messages": [("assistant", answer_text)]}

    # -- wiring -------------------------------------------------------------

    def route_after_plan(state: AgentState) -> str:
        return "delegate" if state.get("needs_subagent") else "answer"

    g = StateGraph(AgentState)
    g.add_node("compact", compact)
    g.add_node("retrieve", retrieve)
    g.add_node("plan", plan)
    g.add_node("delegate", delegate)
    g.add_node("answer", answer)

    g.add_edge(START, "compact")
    g.add_edge("compact", "retrieve")
    g.add_edge("retrieve", "plan")
    g.add_conditional_edges("plan", route_after_plan, {"delegate": "delegate", "answer": "answer"})
    g.add_edge("delegate", "answer")
    g.add_edge("answer", END)

    return g.compile(checkpointer=checkpointer)


def _parse_plan(raw: str, question: str, offline: bool) -> tuple[str, bool, str]:
    """Tolerant JSON parse of the planner output with an offline fallback."""
    if offline:
        # Deterministic heuristic so the delegate branch is exercised in stub mode.
        delegate = len(question.split()) > 6
        sub_q = question if delegate else ""
        return ("[offline] retrieve from KB, then answer", delegate, sub_q)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start : end + 1]) if start >= 0 else {}
    except Exception:
        data = {}
    plan_text = str(data.get("plan", "answer from KB"))
    delegate = bool(data.get("delegate", False))
    sub_q = str(data.get("sub_question", "")) if delegate else ""
    return plan_text, delegate, sub_q

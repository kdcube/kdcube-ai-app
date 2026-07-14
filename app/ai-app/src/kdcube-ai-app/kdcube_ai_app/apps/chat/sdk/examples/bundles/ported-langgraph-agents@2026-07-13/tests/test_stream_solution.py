"""The lg-solution streaming seam (platform/stream_solution.py).

Drives ``stream_graph_turn`` — the DEDICATED-answer-node adapter — with a stub
graph that yields LangGraph-shaped astream_events, plus a fake communicator bound
through comm_ctx. Asserts the 1:1 translation (node start/end -> step, answer
tokens -> delta, end of turn -> complete) and that the final answer is returned.
Fully offline — no DB, no API key, no real graph.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from kdcube_ai_app.apps.chat.sdk.runtime import comm_ctx
from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _stream_module():
    _name, module = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "stream_solution.py")
    return module


class _FakeComm:
    def __init__(self) -> None:
        self.steps: list[tuple[str, str]] = []
        self.deltas: list[str] = []
        self.complete_data: dict | None = None
        self.completed = False

    async def step(self, *, step: str, status: str, **payload) -> None:
        self.steps.append((step, status))

    async def delta(self, *, text: str, index: int, marker: str = "answer", **kwargs) -> None:
        self.deltas.append(text)

    async def complete(self, *, data=None) -> None:
        self.completed = True
        self.complete_data = data


class _StreamingGraph:
    """A stub graph whose answer node emits token events (online path)."""

    async def astream_events(self, inputs, config, *, version=None):
        assert version == "v2"
        yield {"event": "on_chain_start", "name": "retrieve", "metadata": {"langgraph_node": "retrieve"}}
        yield {"event": "on_chain_end", "name": "retrieve", "metadata": {"langgraph_node": "retrieve"}}
        yield {"event": "on_chain_start", "name": "answer", "metadata": {"langgraph_node": "answer"}}
        for tok in ("Hello", ", ", "world"):
            yield {
                "event": "on_chat_model_stream",
                "name": "model",
                "metadata": {"langgraph_node": "answer"},
                "data": {"chunk": SimpleNamespace(content=tok)},
            }
        yield {
            "event": "on_chain_end",
            "name": "answer",
            "metadata": {"langgraph_node": "answer"},
            "data": {"output": {"answer": "Hello, world"}},
        }


class _OfflineGraph:
    """A stub graph whose answer node emits no tokens (offline/stub path):
    the node's returned answer is streamed as a single delta."""

    async def astream_events(self, inputs, config, *, version=None):
        yield {"event": "on_chain_start", "name": "answer", "metadata": {"langgraph_node": "answer"}}
        yield {
            "event": "on_chain_end",
            "name": "answer",
            "metadata": {"langgraph_node": "answer"},
            "data": {"output": {"answer": "canned offline answer"}},
        }


def _run(graph, step_nodes):
    async def _go():
        comm = _FakeComm()
        comm_ctx.set_comm(comm)
        answer = await _stream_module().stream_graph_turn(
            graph,
            {"question": "hi"},
            {"configurable": {"thread_id": "t"}},
            answer_node="answer",
            step_nodes=step_nodes,
        )
        return comm, answer

    return asyncio.run(_go())


def test_streaming_path_emits_steps_deltas_and_complete() -> None:
    comm, answer = _run(_StreamingGraph(), {"retrieve", "answer"})

    assert answer == "Hello, world"

    # Step lifecycle: retrieve running+completed, answer running+completed.
    assert ("retrieve", "running") in comm.steps
    assert ("retrieve", "completed") in comm.steps
    assert ("answer", "running") in comm.steps
    assert ("answer", "completed") in comm.steps

    # Tokens streamed as answer deltas.
    assert "".join(comm.deltas) == "Hello, world"

    # Turn completes with the final answer.
    assert comm.completed is True
    assert comm.complete_data == {"final_answer": "Hello, world"}


def test_offline_path_streams_node_answer_as_single_delta() -> None:
    comm, answer = _run(_OfflineGraph(), {"answer"})

    assert answer == "canned offline answer"
    # A single delta carries the whole answer when no token stream exists.
    assert comm.deltas == ["canned offline answer"]
    assert ("answer", "completed") in comm.steps
    assert comm.completed is True
    assert comm.complete_data == {"final_answer": "canned offline answer"}

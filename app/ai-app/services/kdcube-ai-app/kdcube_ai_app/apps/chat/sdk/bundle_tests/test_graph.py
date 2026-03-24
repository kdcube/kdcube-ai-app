# SPDX-License-Identifier: MIT

"""Graph tests for bundles (Type 3).

Test that the LangGraph works correctly.
Tests work with any bundle specified via --bundle-id parameter.

Run with:
  pytest test_graph.py --bundle-id=react.doc -v
  pytest test_graph.py --bundle-id=openrouter-data -v
"""

from __future__ import annotations

import time

import pytest


class TestBundleGraph:
    """Test that the LangGraph compiles and is structurally correct."""

    def test_build_graph_returns_compiled_state_graph(self, bundle):
        """_build_graph() returns a compiled StateGraph (not None)."""
        assert hasattr(bundle, "_build_graph"), "Bundle must implement _build_graph()"
        assert callable(bundle._build_graph)

        graph = bundle._build_graph()
        assert graph is not None

    def test_compiled_graph_stored_on_bundle(self, bundle):
        """Bundle stores the compiled graph as self.graph after __init__."""
        assert hasattr(bundle, "graph"), (
            "Bundle must store compiled graph as self.graph in __init__"
        )
        assert bundle.graph is not None

    def test_graph_has_nodes(self, bundle):
        """Compiled graph has at least one node."""
        graph = bundle._build_graph()
        # LangGraph compiled graphs expose nodes via .nodes or get_graph()
        inner = graph.get_graph()
        assert len(inner.nodes) > 0, "Graph must have at least one node"

    def test_graph_has_edges(self, bundle):
        """Compiled graph has edges connecting nodes."""
        graph = bundle._build_graph()
        inner = graph.get_graph()
        assert len(inner.edges) > 0, "Graph must have at least one edge"

    def test_graph_starts_from_start_node(self, bundle):
        """Graph has an edge from __start__ to the first real node."""
        graph = bundle._build_graph()
        inner = graph.get_graph()
        edge_sources = {e.source for e in inner.edges}
        assert "__start__" in edge_sources, (
            "Graph must have an edge originating from START (__start__)"
        )

    def test_graph_ends_at_end_node(self, bundle):
        """Graph has an edge to __end__."""
        graph = bundle._build_graph()
        inner = graph.get_graph()
        edge_targets = {e.target for e in inner.edges}
        assert "__end__" in edge_targets, (
            "Graph must have an edge leading to END (__end__)"
        )

    def test_graph_no_orphan_nodes(self, bundle):
        """Every node is reachable (connected to at least one edge)."""
        graph = bundle._build_graph()
        inner = graph.get_graph()

        all_nodes = {n for n in inner.nodes}
        connected_nodes = set()
        for e in inner.edges:
            connected_nodes.add(e.source)
            connected_nodes.add(e.target)

        # Remove __start__ and __end__ which may not be in nodes dict
        real_nodes = all_nodes - {"__start__", "__end__"}
        orphans = real_nodes - connected_nodes
        assert not orphans, f"Orphan nodes found (not connected to any edge): {orphans}"

    def test_build_graph_does_not_raise(self, bundle):
        """_build_graph() completes without raising an exception."""
        try:
            graph = bundle._build_graph()
            assert graph is not None
        except Exception as exc:
            pytest.fail(f"_build_graph() raised an unexpected exception: {exc}")

    def test_build_graph_is_fast(self, bundle):
        """Graph compilation completes in a reasonable time (< 5 seconds)."""
        start = time.time()
        bundle._build_graph()
        elapsed = time.time() - start
        assert elapsed < 5.0, (
            f"_build_graph() took {elapsed:.2f}s — expected < 5s"
        )

    def test_graph_supports_ainvoke(self, bundle):
        """Compiled graph has an ainvoke method (async invocation)."""
        graph = bundle._build_graph()
        assert hasattr(graph, "ainvoke"), "Compiled graph must expose ainvoke()"
        assert callable(graph.ainvoke)

    def test_multiple_graph_builds_are_independent(self, bundle):
        """Each call to _build_graph() returns a fresh, independent graph."""
        graph1 = bundle._build_graph()
        graph2 = bundle._build_graph()
        # Should be different objects (not the same cached instance)
        assert graph1 is not graph2
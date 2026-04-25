#!/usr/bin/env python
"""
Advanced RAG smoke test (no DB / LLM / cross-encoder required).

What this checks (in order; stops at the first failure):

  1) The new modules import cleanly.
  2) `cross_encoder_rerank(mode="compound")` runs end-to-end with a stubbed CE.
  3) `_adv_settings` parses RuntimeCtx-shaped settings into pipeline knobs.
  4) `_merge_dedup` and `_shape_source` produce the expected payload shape.
  5) The Semantic-Kernel plugin module loads and registers `kb_advanced_rag`.
  6) `AdvancedRAGRuntime.is_available()` honours the knowledge-enabled check.

It does NOT touch Postgres / Neo4j / OpenAI / any cross-encoder model files.
It only proves the integration plumbing is internally consistent.

Run from the kdcube-ai-app service dir, with the project venv (or Docker shell):

    cd app/ai-app/services/kdcube-ai-app
    python ../../../tools/smoke_test_advanced_rag.py
"""
from __future__ import annotations

import os
import sys
import traceback
import types
from pathlib import Path

# Make the kdcube package importable when this script is executed directly.
SERVICE_DIR = Path(__file__).resolve().parent.parent / "app" / "ai-app" / "services" / "kdcube-ai-app"
if SERVICE_DIR.is_dir() and str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))


# --- helpers ---------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


class SkipStep(Exception):
    """Raise from a step when it cannot run because of an infra dep that is
    not part of what we want to verify (e.g. semantic_kernel not installed in
    a barebones venv). Reported as SKIP, not FAIL."""


def step(name: str, fn) -> str:
    """Returns 'PASS', 'SKIP', or 'FAIL'."""
    print(f"\n--- {name} ---")
    try:
        fn()
        print(f"[{PASS}] {name}")
        return PASS
    except SkipStep as e:
        print(f"[{SKIP}] {name}: {e}")
        return SKIP
    except Exception:
        print(f"[{FAIL}] {name}")
        traceback.print_exc()
        return FAIL


# --- 1) Imports ------------------------------------------------------------

def step_imports():
    # Each import in its own try-block so you see the first failure clearly.
    # rerank.py imports sentence_transformers; if the model file is missing on
    # disk it will still import the class — only `predict()` would lazy-load.
    import kdcube_ai_app.infra.rerank.rerank as _rerank  # noqa: F401
    print("  ok: kdcube_ai_app.infra.rerank.rerank")

    import kdcube_ai_app.apps.chat.sdk.retrieval.kb_client as _kbc  # noqa: F401
    print("  ok: kdcube_ai_app.apps.chat.sdk.retrieval.kb_client")
    assert hasattr(_kbc.KBClient, "expand_neighbors"), "KBClient.expand_neighbors missing"
    print("  ok: KBClient.expand_neighbors present")

    import kdcube_ai_app.apps.chat.sdk.tools._advanced_rag_internal.runtime as _rt  # noqa: F401
    print("  ok: _advanced_rag_internal.runtime")

    import kdcube_ai_app.apps.chat.sdk.tools._advanced_rag_internal.query_rewrite as _qr  # noqa: F401
    print("  ok: _advanced_rag_internal.query_rewrite")

    import kdcube_ai_app.apps.chat.sdk.tools._advanced_rag_internal.entity_extract as _ee  # noqa: F401
    print("  ok: _advanced_rag_internal.entity_extract")

    import kdcube_ai_app.apps.chat.sdk.tools._advanced_rag_internal.pipeline as _pl  # noqa: F401
    print("  ok: _advanced_rag_internal.pipeline")


# --- 2) Compound rerank end-to-end -----------------------------------------

def step_compound_rerank():
    import numpy as np
    from kdcube_ai_app.infra.rerank.rerank import cross_encoder_rerank

    class FixedCE:
        def __init__(self, scores):
            self.scores = scores
        def predict(self, pairs, convert_to_numpy=True):
            return np.array(self.scores, dtype=float)

    candidates = [
        {"id": "x", "text": "irrelevant",  "semantic_score": 0.9, "tags": []},
        {"id": "y", "text": "irrelevant2", "semantic_score": 0.85, "tags": []},
        {"id": "z", "text": "important",   "semantic_score": 0.20, "tags": ["important"]},
    ]
    out = cross_encoder_rerank(
        "q", candidates, column_name="text",
        cross_encoder=FixedCE([5.0, 4.0, 1.0]),
        top_k=2, mode="compound",
        weights={"rerank": 0.6, "vec": 0.4, "kw": 0.0, "priority": 0.0},
        priority_keys=["important"],
        min_priority_slots=1,
    )
    ids = [r["id"] for r in out]
    print(f"  top_k=2 with min_priority_slots=1 -> {ids}")
    assert "z" in ids, "priority slot guarantee failed"
    print("  rerank_components on first row:", out[0].get("rerank_components"))


# --- 3) _adv_settings knob parsing -----------------------------------------

def step_adv_settings():
    from kdcube_ai_app.apps.chat.sdk.tools._advanced_rag_internal.pipeline import _adv_settings

    rt_ctx = types.SimpleNamespace(search_settings={
        "hybrid": {
            "enabled": True,
            "top_k_vector": 12,
            "use_reranking": False,
            "min_score_threshold": 0.4,
            "context_window": 2,
            "distance_type": "cosine",
            "w_sem": 0.7, "w_bm25": 0.3,
        },
        "advancedRag": {
            "enable_query_rewrite": False,
            "enable_entity_pass": True,
            "entity_top_k": 9,
            "min_priority_slots": 2,
        },
    })
    knobs = _adv_settings(rt_ctx)
    print("  parsed knobs:", {k: knobs[k] for k in (
        "enabled", "rewrite", "entity_pass", "entity_top_k",
        "compound_rerank", "neighbor_window", "ui_top_k",
        "min_score_threshold", "distance_type",
    )})
    assert knobs["ui_top_k"] == 12
    assert knobs["compound_rerank"] is False  # follows hybrid.use_reranking
    assert knobs["neighbor_window"] == 2      # follows hybrid.context_window
    assert knobs["rewrite"] is False
    assert knobs["entity_top_k"] == 9


# --- 4) Merge / dedup / source shaping -------------------------------------

def step_merge_and_shape():
    from kdcube_ai_app.apps.chat.sdk.tools._advanced_rag_internal.pipeline import (
        _merge_dedup, _shape_source,
    )

    a = [
        {"resource_id": "r1", "version": 1, "id": "s1", "semantic_score": 0.4},
        {"resource_id": "r1", "version": 1, "id": "s2", "semantic_score": 0.6},
    ]
    b = [
        {"resource_id": "r1", "version": 1, "id": "s1", "semantic_score": 0.9},
        {"resource_id": "r2", "version": 1, "id": "s3", "semantic_score": 0.5},
    ]
    merged = _merge_dedup(a, b)
    print(f"  merged {len(merged)} rows from {len(a)+len(b)} inputs")
    assert len(merged) == 3
    by_id = {(r["resource_id"], r["version"], r["id"]): r for r in merged}
    assert by_id[("r1", 1, "s1")]["semantic_score"] == 0.9

    src = _shape_source({
        "id": "seg1", "version": 3, "resource_id": "doc-1",
        "title": "", "content": "body",
        "extensions": {"datasource": {"title": "Real Title", "uri": "https://x", "provider": "kb"}},
        "rerank_score": 0.7, "semantic_score": 0.55,
    }, sid=4)
    print(f"  shaped source sid={src['sid']} title={src['title']!r} url={src['url']!r}")
    assert src["title"] == "Real Title"
    assert src["url"] == "https://x"


# --- 5) SK plugin loads ----------------------------------------------------

def step_sk_plugin():
    try:
        import semantic_kernel  # noqa: F401
    except ModuleNotFoundError as e:
        raise SkipStep(f"semantic_kernel not installed in this Python ({e}); "
                       f"run in the project venv/container to exercise this step") from e

    from kdcube_ai_app.apps.chat.sdk.tools.kb_advanced_rag_tools import (
        kernel, tools, set_runtime,
    )
    plugins = list(kernel.plugins)
    print(f"  kernel.plugins: {plugins}")
    assert "kb_advanced_rag" in plugins, f"plugin not registered, got {plugins!r}"
    print(f"  tool class: {type(tools).__name__}")
    assert hasattr(tools, "advanced_rag_search"), "tool method missing"
    print("  kb_advanced_rag.advanced_rag_search present")
    # set_runtime should accept None without raising (clears the slot)
    set_runtime(None)
    print("  set_runtime(None) ok")


# --- 6) AdvancedRAGRuntime gating ------------------------------------------

def step_runtime_gating():
    from kdcube_ai_app.apps.chat.sdk.tools._advanced_rag_internal.runtime import AdvancedRAGRuntime

    rt = AdvancedRAGRuntime(
        kb=object(), model_service=object(), conv_store=object(),
        get_runtime_ctx=lambda: types.SimpleNamespace(search_settings={}),
        knowledge_enabled_check=lambda: True,
    )
    assert rt.is_available() is True
    print("  is_available() = True when knowledge enabled")

    rt2 = AdvancedRAGRuntime(
        kb=object(), model_service=object(), conv_store=object(),
        get_runtime_ctx=lambda: types.SimpleNamespace(search_settings={}),
        knowledge_enabled_check=lambda: False,
    )
    assert rt2.is_available() is False
    print("  is_available() = False when knowledge disabled")

    rt3 = AdvancedRAGRuntime(
        kb=None, model_service=object(), conv_store=object(),
        get_runtime_ctx=lambda: types.SimpleNamespace(search_settings={}),
    )
    assert rt3.is_available() is False
    print("  is_available() = False when kb is None")


# --- runner ----------------------------------------------------------------

def main() -> int:
    print(f"Python: {sys.version.split()[0]}  cwd: {os.getcwd()}")
    print(f"sys.path[0]: {sys.path[0]}")

    steps = [
        ("1. imports",            step_imports),
        ("2. compound rerank",    step_compound_rerank),
        ("3. _adv_settings",      step_adv_settings),
        ("4. merge + shape",      step_merge_and_shape),
        ("5. SK plugin loads",    step_sk_plugin),
        ("6. runtime gating",     step_runtime_gating),
    ]
    counts = {PASS: 0, SKIP: 0, FAIL: 0}
    for name, fn in steps:
        result = step(name, fn)
        counts[result] += 1
        if result == FAIL:
            break  # stop at first hard failure for clarity

    print("\n" + "=" * 60)
    print(f"PASS={counts[PASS]}  SKIP={counts[SKIP]}  FAIL={counts[FAIL]}")
    if counts[FAIL] == 0:
        if counts[SKIP] == 0:
            print("ALL CHECKS PASSED — advanced RAG plumbing is internally consistent.")
        else:
            print("All runnable checks passed; some steps skipped (missing infra dep).")
            print("Re-run inside the project venv/container to exercise the SKIPped steps.")
        print("Next: bring up the worker + KB and try a real turn.")
        return 0
    print(f"FAILED at the step above. Fix and re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

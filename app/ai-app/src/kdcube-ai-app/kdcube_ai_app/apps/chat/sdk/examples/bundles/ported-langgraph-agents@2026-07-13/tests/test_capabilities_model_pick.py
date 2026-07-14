# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Capabilities model pick — the ACCEPTANCE tests, offline, PER AGENT.

Proves this multi-agent, non-ReAct app drives the Capabilities model picker end to
end via the generic `simple_model_pick` provider, independently for EACH hosted
agent:

  1. INVENTORY — the `agent_capabilities` catalog for each agent's real config
     returns its declared model picker (supported_models + default_model), and the
     resolved provider is the generic one (not ReAct).
  2. OVERLAY   — binding `role_models` onto the bundle call context changes the
     model the KDCube model router resolves for that agent's answer role.
  3. APPLY     — the per-turn seam (`resolve_turn_role_models(ep, state, agent_id)`)
     loads a saved pick for the ACTIVE agent and returns it as THAT agent's
     answer-role overlay; per-conversation isolation holds; the two agents never
     cross-apply; no pick / no store falls back to the agent's configured DEFAULT
     overlay (so the declared default routes — never the platform fallback).

Everything is offline — no DB, no API key, no real graph.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict

import yaml

from kdcube_ai_app.apps.chat.sdk.runtime.agent_capabilities import (
    SimpleModelPickProvider,
    resolve_capability_provider,
)
from kdcube_ai_app.apps.chat.sdk.runtime.agent_inventory import agent_capabilities_catalog
from kdcube_ai_app.apps.chat.sdk.runtime.comm_ctx import bind_current_bundle_call_context_patch
from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ID = "ported-langgraph-agents@2026-07-13"

SONNET = "claude-sonnet-4-5-20250929"
HAIKU = "claude-haiku-4-5-20251001"
SOLUTION_ROLE = "lg-solution.answer"
PREBUILT_ROLE = "lg-react.answer"


def _bundle_config() -> Dict[str, Any]:
    raw = (BUNDLE_ROOT / "config" / "bundles.template.yaml").read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    return doc["bundles"]["items"][0]["config"]


def _capabilities_module():
    _name, module = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "capabilities.py")
    return module


# ── 1. INVENTORY: each agent's catalog returns its own model picker ──────────


def test_each_agent_declares_simple_model_pick_provider() -> None:
    props = _bundle_config()

    sol = resolve_capability_provider(props, "lg-solution")
    assert isinstance(sol, SimpleModelPickProvider)
    assert sol.agent_kind == "simple_model_pick"
    assert sol.role == SOLUTION_ROLE

    pre = resolve_capability_provider(props, "lg-react")
    assert isinstance(pre, SimpleModelPickProvider)
    assert pre.role == PREBUILT_ROLE


def test_catalog_exposes_each_agents_model_picker() -> None:
    props = _bundle_config()

    # default_model is the {provider, model} pair (matching a supported row), so
    # the picker can mark the default row — a bare id string would leave
    # default_model.model undefined on the client and the "default" tag unrendered.
    sol = agent_capabilities_catalog(props, "lg-solution")
    assert sol["default_model"] == {"provider": "anthropic", "model": SONNET}
    assert [row["model"] for row in sol["supported_models"]] == [SONNET, HAIKU]
    assert sol["skills"] == []
    assert sol["subagents"] is None

    pre = agent_capabilities_catalog(props, "lg-react")
    assert pre["default_model"] == {"provider": "anthropic", "model": HAIKU}
    assert [row["model"] for row in pre["supported_models"]] == [HAIKU, SONNET]


# ── 2. OVERLAY: bound role_models change the router-resolved model ───────────


def test_bound_role_models_override_the_router_resolution() -> None:
    from kdcube_ai_app.infra.service_hub.inventory import Config, ModelRouter

    router = ModelRouter(Config())
    base = router.describe(SOLUTION_ROLE)

    with bind_current_bundle_call_context_patch(
        {"role_models": {SOLUTION_ROLE: {"provider": "anthropic", "model": HAIKU}}}
    ):
        picked = router.describe(SOLUTION_ROLE)

    assert picked.provider == "anthropic"
    assert picked.model_name == HAIKU
    after = router.describe(SOLUTION_ROLE)
    assert (after.provider, after.model_name) == (base.provider, base.model_name)


# ── 3. APPLY: the per-turn seam loads + returns the pick for the ACTIVE agent ─


class _FakeSelectionStore:
    """Stand-in for UserAgentSelectionStore: returns a per-(agent, conversation)
    model pick and records the identity keys it was queried with."""

    def __init__(self, *, pg_pool=None, tenant="default", project="default"):
        self.tenant = tenant
        self.project = project
        self.queries: list[dict] = []

    async def get_selection(self, *, user_id, bundle_id, agent_id, conversation_id="", materialize=False):
        self.queries.append({
            "user_id": user_id, "bundle_id": bundle_id, "agent_id": agent_id,
            "conversation_id": conversation_id,
        })
        # lg-solution's conv "A" -> Haiku; lg-react's conv "A" -> Sonnet; else none.
        picks = {
            ("lg-solution", "A"): {"provider": "anthropic", "model": HAIKU},
            ("lg-react", "A"): {"provider": "anthropic", "model": SONNET},
        }
        return {"schema_version": 1, "disabled": {}, "model": picks.get((agent_id, conversation_id))}


class _FakeEntrypoint:
    def __init__(self, props, *, pg_pool):
        self.bundle_props = props
        self.pg_pool = pg_pool

    def bundle_prop(self, path, default=None):
        node: Any = self.bundle_props
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def _agent_selection_identity(self):
        return {
            "tenant": "t1", "project": "p1",
            "user_id": "user-42", "bundle_id": BUNDLE_ID,
        }


def _install_fake_store(monkeypatch) -> list[_FakeSelectionStore]:
    import kdcube_ai_app.apps.chat.sdk.solutions.user_settings as user_settings

    built: list[_FakeSelectionStore] = []

    def _factory(**kwargs):
        store = _FakeSelectionStore(**kwargs)
        built.append(store)
        return store

    monkeypatch.setattr(user_settings, "UserAgentSelectionStore", _factory)
    return built


def test_saved_pick_applies_to_the_active_agents_role(monkeypatch) -> None:
    cap = _capabilities_module()
    built = _install_fake_store(monkeypatch)
    ep = _FakeEntrypoint(_bundle_config(), pg_pool=object())

    sol_overlay = asyncio.run(cap.resolve_turn_role_models(ep, {"conversation_id": "A"}, "lg-solution"))
    pre_overlay = asyncio.run(cap.resolve_turn_role_models(ep, {"conversation_id": "A"}, "lg-react"))

    # Each pick rebases ONLY its own agent's answer role.
    assert sol_overlay == {SOLUTION_ROLE: {"provider": "anthropic", "model": HAIKU}}
    assert pre_overlay == {PREBUILT_ROLE: {"provider": "anthropic", "model": SONNET}}
    # The store was queried with the right agent id each time.
    agent_ids = {q["agent_id"] for store in built for q in store.queries}
    assert agent_ids == {"lg-solution", "lg-react"}
    q = built[0].queries[-1]
    assert q["user_id"] == "user-42"
    assert q["bundle_id"] == BUNDLE_ID


def test_pick_does_not_leak_across_conversations(monkeypatch) -> None:
    cap = _capabilities_module()
    _install_fake_store(monkeypatch)
    ep = _FakeEntrypoint(_bundle_config(), pg_pool=object())

    overlay_a = asyncio.run(cap.resolve_turn_role_models(ep, {"conversation_id": "A"}, "lg-solution"))
    overlay_unpicked = asyncio.run(cap.resolve_turn_role_models(ep, {"conversation_id": "Z"}, "lg-solution"))

    assert overlay_a[SOLUTION_ROLE]["model"] == HAIKU
    # Conv Z has no pick -> the agent's admin default (Sonnet) routes, NOT conv
    # A's Haiku pick. The default (not empty) proves both no-leak AND that the
    # declared default is what fills an unpicked conversation.
    assert overlay_unpicked == {SOLUTION_ROLE: {"provider": "anthropic", "model": SONNET}}


def test_no_pick_applies_configured_default(monkeypatch) -> None:
    cap = _capabilities_module()
    _install_fake_store(monkeypatch)
    ep = _FakeEntrypoint(_bundle_config(), pg_pool=object())

    overlay = asyncio.run(cap.resolve_turn_role_models(ep, {"conversation_id": "unpicked"}, "lg-react"))
    # No stored pick -> the admin-configured default routes (lg-react's is Haiku).
    assert overlay == {PREBUILT_ROLE: {"provider": "anthropic", "model": HAIKU}}


def test_fails_open_without_store() -> None:
    cap = _capabilities_module()
    ep = _FakeEntrypoint(_bundle_config(), pg_pool=None)

    overlay = asyncio.run(cap.resolve_turn_role_models(ep, {"conversation_id": "A"}, "lg-solution"))
    # No store -> the selection load fails open to empty, then the admin default
    # routes (the agent gets its declared default, never the platform fallback).
    assert overlay == {SOLUTION_ROLE: {"provider": "anthropic", "model": SONNET}}

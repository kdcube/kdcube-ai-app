# SPDX-License-Identifier: MIT

"""Workflow-side subagent v2 behavior: per-agent opt-in, the child turn's
scratchpad/charter wiring, fork records on the turn log, and the
persist-then-report ordering of the child's terminal event."""

import time
from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.chatbot import base_workflow as workflow_mod
from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.base_workflow import BaseWorkflow
from kdcube_ai_app.apps.chat.sdk.solutions.react.proto import RuntimeCtx
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.charter import SubagentCharter
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.child_turn import (
    SubagentChildTurnContext,
)
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.events import ParentLaneAddress
from kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.fork import (
    FORK_MARKER_BLOCK_TYPE,
    build_fork_marker_block,
)


# ------------------------------------------------ per-agent subagents opt-in


def test_subagents_config_default_is_off():
    enabled, defaults = workflow_mod._react_subagents_config({}, agent_id="main")
    assert enabled is False
    assert defaults == {}


def test_subagents_config_per_agent_flag_enables_only_that_agent():
    props = {
        "react": {
            "agents": {"main": {"subagents": True}},
            "subagents": {"model": "claude-haiku-4-5"},
        }
    }
    enabled_main, defaults_main = workflow_mod._react_subagents_config(props, agent_id="main")
    assert enabled_main is True
    # the bundle-level block keeps serving the shared defaults
    assert defaults_main == {"model": "claude-haiku-4-5"}
    enabled_other, _ = workflow_mod._react_subagents_config(props, agent_id="wizard")
    assert enabled_other is False


def test_subagents_config_per_agent_flag_is_the_authority():
    props = {
        "react": {
            "agents": {"main": {"subagents": False}},
            "subagents": {"enabled": True, "model": "claude-haiku-4-5"},
        }
    }
    enabled, _ = workflow_mod._react_subagents_config(props, agent_id="main")
    assert enabled is False


def test_subagents_config_bundle_level_enabled_still_opts_agents_in():
    props = {"react": {"subagents": {"enabled": True, "model": "claude-haiku-4-5"}}}
    enabled, defaults = workflow_mod._react_subagents_config(props, agent_id="main")
    assert enabled is True
    assert defaults == {"model": "claude-haiku-4-5"}


def test_subagents_config_per_agent_dict_form_merges_defaults():
    props = {
        "react": {
            "agents": {"main": {"subagents": {"enabled": True, "model": "claude-sonnet-4-6"}}},
            "subagents": {"model": "claude-haiku-4-5", "other": 1},
        }
    }
    enabled, defaults = workflow_mod._react_subagents_config(props, agent_id="main")
    assert enabled is True
    assert defaults == {"model": "claude-sonnet-4-6", "other": 1}


def _install_spawner(props, *, agent_id="main", depth=0, user_denied=False):
    runtime_ctx = RuntimeCtx(agent_id=agent_id, subagent_depth=depth)
    stub = SimpleNamespace(bundle_props=props, _user_subagents_denied=user_denied)
    BaseWorkflow._install_subagent_spawner(stub, runtime_ctx=runtime_ctx, build_template={})
    return runtime_ctx


def test_spawner_installed_only_for_opted_in_agents():
    # flag absent: no spawner -> react.delegate is absent from the agent's
    # catalog and instructions (the subagent role stays None)
    ctx = _install_spawner({"react": {"subagents": {"model": "claude-haiku-4-5"}}})
    assert ctx.subagent_spawner is None

    ctx = _install_spawner({"react": {"agents": {"main": {"subagents": False}}}})
    assert ctx.subagent_spawner is None

    ctx = _install_spawner({
        "react": {
            "agents": {"main": {"subagents": True}},
            "subagents": {"model": "claude-haiku-4-5"},
        }
    })
    assert ctx.subagent_spawner is not None
    assert ctx.subagent_defaults == {"model": "claude-haiku-4-5"}

    # a subagent runtime never gets a spawner, opt-in or not
    ctx = _install_spawner(
        {"react": {"agents": {"main": {"subagents": True}}}},
        depth=1,
    )
    assert ctx.subagent_spawner is None


def test_delegate_tool_and_instructions_follow_the_optin():
    """The spawner is what puts react.delegate in the catalog AND in the
    decision instructions (the catalog entry is the instruction block); the
    per-agent flag therefore decides both."""
    from kdcube_ai_app.apps.chat.sdk.solutions.react.call import get_react_tools_catalog
    from kdcube_ai_app.apps.chat.sdk.solutions.react.v3.runtime import ReactSolverV2

    def _role_for(props, **kwargs):
        runtime_ctx = _install_spawner(props, **kwargs)
        solver = SimpleNamespace(ctx_browser=SimpleNamespace(runtime_ctx=runtime_ctx))
        return ReactSolverV2._subagent_role(solver)

    # opted in: parent role -> react.delegate present
    role = _role_for({"react": {"agents": {"main": {"subagents": True}}}})
    assert role == "parent"
    assert "react.delegate" in {t["id"] for t in get_react_tools_catalog(subagent_role=role)}

    # flag absent: no role -> the catalog (and instructions) carry no delegate
    role = _role_for({})
    assert role is None
    assert "react.delegate" not in {t["id"] for t in get_react_tools_catalog(subagent_role=role)}

    # a subagent runtime is the child role: contribute, never delegate
    role = _role_for({"react": {"agents": {"main": {"subagents": True}}}}, depth=1)
    assert role == "child"
    child_ids = {t["id"] for t in get_react_tools_catalog(subagent_role=role)}
    assert "react.contribute" in child_ids and "react.delegate" not in child_ids


# ------------------------------------------- user decides: subagents toggle


_OPTED_IN_PROPS = {
    "react": {
        "agents": {"main": {"subagents": True}},
        "subagents": {"model": "claude-haiku-4-5"},
    }
}


def test_capabilities_catalog_offers_subagents_with_the_tradeoff_stated():
    from kdcube_ai_app.apps.chat.sdk.runtime.agent_inventory import (
        agent_capabilities_catalog,
    )

    entry = agent_capabilities_catalog(_OPTED_IN_PROPS, "main")["subagents"]
    assert entry["available"] is True
    assert entry["label"]
    # the picker copy states the user's trade-off plainly: quality vs spend
    description = entry["description"].lower()
    assert "quality" in description
    assert "billed" in description or "cost" in description or "spend" in description

    # admin absent/false = not in the inventory at all
    assert agent_capabilities_catalog({}, "main")["subagents"] is None
    assert agent_capabilities_catalog(
        {"react": {"agents": {"main": {"subagents": False}}}}, "main",
    )["subagents"] is None


def test_subagents_denial_clamps_to_the_offered_inventory():
    from kdcube_ai_app.apps.chat.sdk.runtime.agent_inventory import clamp_selection

    offered = {"subagents": {"available": True}}
    assert clamp_selection({"subagents": True}, offered) == {"subagents": True}
    # admin does not offer it: nothing to deny, nothing stored
    assert clamp_selection({"subagents": True}, {"subagents": None}) == {}
    assert clamp_selection({"subagents": True}, {}) == {}
    # falsy value = enabled = absent from the record
    assert clamp_selection({"subagents": False}, offered) == {}


def test_subagents_toggle_is_a_capability_delta():
    from kdcube_ai_app.apps.chat.sdk.runtime.agent_inventory import (
        SELECTION_CHANGE_CAPABILITY,
        classify_selection_change,
        selection_snapshot,
    )

    prev = selection_snapshot({}, None)
    curr = selection_snapshot({"subagents": True}, None)
    change = classify_selection_change(prev, curr)
    assert change["changed"] is True
    assert "subagents_toggle" in change["reasons"]
    assert SELECTION_CHANGE_CAPABILITY in change["classes"]
    # same both ways (re-enabling is a delta too)
    assert classify_selection_change(curr, prev)["changed"] is True


def test_selection_merge_toggles_subagents():
    from kdcube_ai_app.apps.chat.sdk.solutions.user_settings.agent_selection import (
        merge_selection_patch,
    )

    assert merge_selection_patch({}, {"subagents": True}) == {"subagents": True}
    # absent from the patch keeps the stored state
    assert merge_selection_patch({"subagents": True}, {}) == {"subagents": True}
    # false re-enables (the key leaves the record)
    assert merge_selection_patch({"subagents": True}, {"subagents": False}) == {}


def test_user_denial_removes_the_spawner():
    # admin offered, user default (on): wired
    ctx = _install_spawner(_OPTED_IN_PROPS)
    assert ctx.subagent_spawner is not None
    # admin offered, user turned it off: the ability is absent for their turns
    ctx = _install_spawner(_OPTED_IN_PROPS, user_denied=True)
    assert ctx.subagent_spawner is None
    # narrowing only: a user preference never widens an unoffered ability
    ctx = _install_spawner({}, user_denied=False)
    assert ctx.subagent_spawner is None


@pytest.mark.asyncio
async def test_apply_user_agent_selection_captures_subagents_denial():
    import json as _json

    from kdcube_ai_app.apps.chat.sdk.runtime.skill_config import AgentSkillConfig
    from kdcube_ai_app.apps.chat.sdk.runtime.tool_config import AgentToolConfig
    from kdcube_ai_app.apps.chat.sdk.solutions.user_settings import agent_selection_key

    class _Con:
        def __init__(self, rows):
            self._rows = rows

        async def fetchrow(self, sql, *args):
            return self._rows.get((args[0], args[1], args[2]))

        async def execute(self, sql, *args):
            return None

    class _Acquire:
        def __init__(self, con):
            self._con = con

        async def __aenter__(self):
            return self._con

        async def __aexit__(self, *exc):
            return False

    class _Pool:
        def __init__(self, rows):
            self._con = _Con(rows)

        def acquire(self):
            return _Acquire(self._con)

    rows = {
        ("u1", "bundle@1-0", agent_selection_key("main")): {
            "value_json": _json.dumps({
                "schema_version": 1,
                "disabled": {"subagents": True},
            }),
            "created_at": "",
            "updated_at": "",
        }
    }
    stub = SimpleNamespace(
        pg_pool=_Pool(rows),
        logger=SimpleNamespace(log=lambda *a, **k: None),
        bundle_props=dict(_OPTED_IN_PROPS),
        runtime_ctx=SimpleNamespace(
            tenant="acme",
            project="demo",
            user_id="u1",
            bundle_id="bundle@1-0",
            agent_id="main",
            conversation_id="conv-1",
            cold_turn_marker=None,
        ),
        ctx_browser=SimpleNamespace(timeline=None),
        _conversation_cache_is_warm=lambda timeline: False,
        _user_subagents_denied=False,
    )
    await BaseWorkflow.apply_user_agent_selection(stub, AgentToolConfig(), AgentSkillConfig())
    assert stub._user_subagents_denied is True

    # the captured denial is what the spawner gate enforces
    runtime_ctx = RuntimeCtx(agent_id="main", subagent_depth=0)
    BaseWorkflow._install_subagent_spawner(stub, runtime_ctx=runtime_ctx, build_template={})
    assert runtime_ctx.subagent_spawner is None


# ---------------------------------------------------------- child turn wiring


def _child_context():
    return SubagentChildTurnContext(
        charter=SubagentCharter(goal="Research X", max_rounds=4),
        parent=ParentLaneAddress(
            tenant="tenant",
            project="project",
            user_id="user_1",
            conversation_id="conv_parent",
            turn_id="turn_parent",
            agent_id="main",
        ),
        depth=1,
        child_conversation_id="sub_x",
        child_turn_id="turn_c1",
        parent_session_id="sess_parent",
        parent_user={"user_type": "privileged", "user_id": "user_1"},
    )


@pytest.mark.asyncio
async def test_construct_scratchpad_uses_charter_as_child_task_text():
    wf = BaseWorkflow.__new__(BaseWorkflow)
    wf._ctx = {}
    wf.comm_context = None
    wf.gate_out_class = None
    wf._subagent_child_context = _child_context()

    scratchpad = await BaseWorkflow.construct_turn_and_scratchpad(wf, {
        "request_id": "req-1",
        "tenant": "tenant",
        "project": "project",
        "user": "user_1",
        "session_id": "sub_x",
        "conversation_id": "sub_x",
        "turn_id": "turn_c1",
        "external_events": [],
    })
    assert scratchpad.user_text.startswith("[SUBAGENT CHARTER]")
    assert "Research X" in scratchpad.user_text


def _finish_turn_workflow(*, child_context=None, contrib_blocks=None):
    order = []
    saved_turn_logs = []

    async def _noop_async(*args, **kwargs):
        del args, kwargs

    class _Timeline:
        def __init__(self, blocks):
            self.blocks = list(blocks)

    class _CtxBrowser:
        def __init__(self, runtime_ctx, blocks):
            self.runtime_ctx = runtime_ctx
            self.timeline = _Timeline(blocks)

        def current_turn_blocks(self):
            return list(self.timeline.blocks)

        async def persist_timeline(self):
            order.append("persist_timeline")

        async def stop_external_event_listener(self):
            return None

        def contribute(self, blocks):
            self.timeline.blocks.extend(list(blocks or []))

    async def _save_turn_log_as_artifact(**kwargs):
        order.append("save_turn_log")
        saved_turn_logs.append(dict(kwargs))

    wf = BaseWorkflow.__new__(BaseWorkflow)
    wf.logger = SimpleNamespace(
        log=lambda *args, **kwargs: None,
        finish_operation=lambda *args, **kwargs: None,
    )
    wf.ctx_client = SimpleNamespace(save_turn_log_as_artifact=_save_turn_log_as_artifact)
    wf._emit = _noop_async
    wf._persist_stream_artifacts = _noop_async
    wf.report_timings = _noop_async
    wf._publish_git_workspace_if_needed = _noop_async
    wf._assert_event_lane_turn_current = _noop_async
    wf.redis = object()
    wf._ctx = {
        "service": {
            "tenant": "tenant",
            "project": "project",
            "user": "user_1",
            "user_type": "registered",
            "request_id": "req-1",
        },
        "conversation": {"conversation_id": "sub_x", "turn_id": "turn_c1"},
        "turn": {"t_turn0": time.perf_counter(), "ms0u": 0},
    }
    wf.config = SimpleNamespace(ai_bundle_spec=SimpleNamespace(id="bundle.test"))
    wf.runtime_ctx = RuntimeCtx(conversation_id="sub_x", turn_id="turn_c1")
    wf.comm_context = None
    wf.ctx_browser = _CtxBrowser(wf.runtime_ctx, contrib_blocks or [])
    wf._subagent_child_context = child_context
    wf._subagent_completion_published = False
    return wf, order, saved_turn_logs


@pytest.mark.asyncio
async def test_finish_turn_publishes_converged_only_after_persist(monkeypatch):
    order_calls = []

    async def _fake_publish(**kwargs):
        order_calls.append(("publish", kwargs))

    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.child_turn.publish_child_completion",
        _fake_publish,
    )
    wf, order, _logs = _finish_turn_workflow(child_context=_child_context())

    def _record_publish(**kwargs):
        order.append("publish_completion")
        return _fake_publish(**kwargs)

    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.child_turn.publish_child_completion",
        lambda **kwargs: _record_publish(**kwargs),
    )

    scratchpad = SimpleNamespace(
        answer="Charter complete.",
        answer_raw="Charter complete.",
        timings=[],
        started_at="2026-07-12T00:00:00Z",
        suggested_followups=[],
        assistant_completion_attempts=[],
        persisted_turn_entry_paths=set(),
    )
    wf.persist_turn_prompt_entries = _noop(wf)
    wf.persist_assistant = _noop(wf)
    wf._emit_committed_answer_once = _noop(wf)

    await wf.finish_turn(scratchpad, ok=True)

    assert "publish_completion" in order
    # END-OF-TURN PERSIST first, the report after
    assert order.index("save_turn_log") < order.index("publish_completion")
    assert order.index("persist_timeline") < order.index("publish_completion")
    assert order_calls and order_calls[0][1]["ok"] is True
    assert order_calls[0][1]["final_answer"] == "Charter complete."

    # exactly once: a second publish attempt is a no-op
    await wf._publish_subagent_completion(scratchpad, ok=True)
    assert len(order_calls) == 1


def _noop(wf):
    async def _fn(*args, **kwargs):
        del args, kwargs
    return _fn


@pytest.mark.asyncio
async def test_finish_turn_without_answer_reports_failed(monkeypatch):
    published = []

    async def _fake_publish(**kwargs):
        published.append(kwargs)

    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.child_turn.publish_child_completion",
        _fake_publish,
    )
    wf, _order, _logs = _finish_turn_workflow(child_context=_child_context())
    scratchpad = SimpleNamespace(
        answer="",
        timings=[],
        started_at="2026-07-12T00:00:00Z",
        suggested_followups=[],
    )
    await wf.finish_turn(scratchpad, ok=False)
    assert len(published) == 1
    assert published[0]["ok"] is False


@pytest.mark.asyncio
async def test_finish_turn_without_child_context_publishes_nothing(monkeypatch):
    published = []

    async def _fake_publish(**kwargs):
        published.append(kwargs)

    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.child_turn.publish_child_completion",
        _fake_publish,
    )
    wf, _order, _logs = _finish_turn_workflow(child_context=None)
    scratchpad = SimpleNamespace(
        answer="",
        timings=[],
        started_at="2026-07-12T00:00:00Z",
        suggested_followups=[],
    )
    await wf.finish_turn(scratchpad, ok=True)
    assert published == []


# --------------------------------------------------- fork records on the log


@pytest.mark.asyncio
async def test_finish_turn_lifts_fork_records_into_turn_log():
    marker = build_fork_marker_block(
        parent_turn_id="turn_c1",
        child_conversation_id="sub_grandchild",
        child_turn_id="turn_g1",
        charter_summary="Draft the appendix",
        deliverables=[],
        max_rounds=6,
    )
    assert marker["type"] == FORK_MARKER_BLOCK_TYPE
    wf, _order, saved_turn_logs = _finish_turn_workflow(
        child_context=None,
        contrib_blocks=[{"type": "user.prompt", "turn_id": "turn_c1", "text": "hi"}, marker],
    )
    scratchpad = SimpleNamespace(
        answer="",
        timings=[],
        started_at="2026-07-12T00:00:00Z",
        suggested_followups=[],
    )
    await wf.finish_turn(scratchpad, ok=True)
    assert len(saved_turn_logs) == 1
    forks = saved_turn_logs[0]["payload"].get("forks")
    assert forks == [{
        "child_conversation_id": "sub_grandchild",
        "charter_goal": "Draft the appendix",
        "forked_at": str(marker.get("ts") or ""),
    }]


# ----------------------------------------------------------- failure authored


@pytest.mark.asyncio
async def test_turn_exception_authors_failed_completion(monkeypatch):
    published = []

    async def _fake_publish(**kwargs):
        published.append(kwargs)

    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.solutions.react.subagents.child_turn.publish_child_completion",
        _fake_publish,
    )
    wf, _order, _logs = _finish_turn_workflow(child_context=_child_context())

    async def _delete_turn(**kwargs):
        del kwargs

    wf.ctx_client.delete_turn = _delete_turn
    wf.message_resources_fn = lambda *args, **kwargs: None

    async def _report_timings(*args, **kwargs):
        return "", "", []

    wf.report_timings = _report_timings
    wf.comm = SimpleNamespace(
        error=_noop(wf),
        delta=_noop(wf),
        service_event=_noop(wf),
    )
    scratchpad = SimpleNamespace(
        answer="",
        timings=[],
        started_at="2026-07-12T00:00:00Z",
        suggested_followups=[],
        current_phase=None,
        conversation_id="sub_x",
        turn_id="turn_c1",
    )

    with pytest.raises(RuntimeError):
        await wf._handle_turn_exception(RuntimeError("decision model unavailable"), scratchpad)

    assert len(published) == 1
    assert published[0]["ok"] is False
    assert "decision model unavailable" in str(published[0]["reason"])

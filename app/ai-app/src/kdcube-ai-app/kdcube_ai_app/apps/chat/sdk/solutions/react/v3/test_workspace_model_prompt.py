# SPDX-License-Identifier: MIT

from kdcube_ai_app.apps.chat.sdk.skills.instructions.shared_instructions import get_workspace_implementation_guide
from kdcube_ai_app.apps.chat.sdk.solutions.react.v3.agents.decision import build_decision_system_text


def test_get_workspace_implementation_guide_custom_mentions_hosting_backed_mode():
    guide = get_workspace_implementation_guide("custom")
    assert "react.pull(paths=[...])" in guide
    assert 'react.checkout(mode="replace", paths=[...])' in guide or 'react.checkout(mode="replace", paths=["fi:' in guide
    assert "mode=\"overlay\"" in guide
    assert "EXACT file ref" in guide
    assert "binary descendants" in guide
    assert "CUSTOM mode" in guide
    assert "not from git" in guide


def test_get_workspace_implementation_guide_git_mentions_git_backed_mode():
    guide = get_workspace_implementation_guide("git")
    assert "react.pull(paths=[...])" in guide
    assert "EXACT file ref" in guide
    assert "binary descendants" in guide
    assert "GIT mode" in guide
    assert "git-backed workspace lineage snapshot" in guide
    assert "local git repo" in guide
    assert "git pull" in guide
    assert "active lineage workspace" in guide
    assert "historical snapshot view" in guide
    assert 'react.checkout(mode="replace", paths=[...])' in guide or 'react.checkout(mode="replace", paths=["fi:' in guide
    assert "runnable/searchable/testable project snapshot" in guide
    assert "mode=\"overlay\"" in guide
    assert "turn_<current_turn>/files/..." in guide
    assert "ls workspace" in guide
    assert "existing top-level scope" in guide


def test_build_decision_system_text_uses_selected_workspace_implementation():
    text = build_decision_system_text(
        adapters=[],
        infra_adapters=[],
        workspace_implementation="git",
    )
    assert "react.pull(paths=[...])" in text
    assert "EXACT file ref" in text
    assert "binary descendants" in text
    assert "local git repo" in text
    assert "Workspace activation is explicit" in text
    assert "do NOT auto-materialize old files" in text
    assert 'react.checkout(mode="replace", paths=[fi:...])' in text or 'react.checkout(mode="replace", paths=["fi:' in text
    assert "runnable/searchable/testable project snapshot" in text
    assert "mode=\"overlay\"" in text
    assert "turn_<current_turn>/files/..." in text
    assert "existing top-level scope" in text
    assert "ls workspace" in text


def test_build_decision_system_text_appends_additional_runtime_instructions():
    text = build_decision_system_text(
        adapters=[],
        infra_adapters=[],
        workspace_implementation="custom",
        additional_instructions="Always prefer the product knowledge skill before web search.",
    )
    assert "[ADDITIONAL RUNTIME INSTRUCTIONS]" in text
    assert "Always prefer the product knowledge skill before web search." in text


def test_build_decision_system_text_single_action_mode_uses_action_channel_wording():
    text = build_decision_system_text(
        adapters=[],
        infra_adapters=[],
        workspace_implementation="custom",
        multi_action_mode="off",
    )
    assert text.index("CRITICAL: you have 3 channels") < text.index("[CORE RESPONSIBILITIES]")
    assert "One response = one round" in text
    assert "After </channel:code>, STOP. The platform calls you again if another round is needed." in text
    assert "Do NOT emit a second full thinking/ReactDecisionOutV2/code triplet in the same response." in text
    assert "<channel:ReactDecisionOutV2> is the action channel" in text
    assert "For now we support only one action per round" in text
    assert "produce exactly one <channel:ReactDecisionOutV2> channel instance" in text
    assert "If multiple tools are needed, emit only the first action now. Never simulate round 2 yourself." in text
    assert "If you cite a channel token literally, write it in backticks like `channel:CHANNEL_ID`." in text


def test_build_decision_system_text_safe_fanout_explains_no_intermediate_review_and_no_exec_bundle():
    text = build_decision_system_text(
        adapters=[],
        infra_adapters=[],
        workspace_implementation="custom",
        multi_action_mode="safe_fanout",
    )
    assert "One response = one round" in text
    assert "Do NOT emit a second full thinking/ReactDecisionOutV2/code triplet in the same response." in text
    assert "<channel:ReactDecisionOutV2> is the action channel" in text
    assert "If you want multiple actions in one round, repeat only <channel:ReactDecisionOutV2>." in text
    assert "One channel instance means one action." in text
    assert "Example:" in text
    assert "<channel:thinking>...one short status for the whole round...</channel:thinking>" in text
    assert "<channel:code></channel:code>" in text
    assert "Never put two actions into one ReactDecisionOutV2 channel instance" in text
    assert "Execution is sequential and you do NOT review intermediate results in the middle" in text
    assert "action B must not depend on action A's result" in text
    assert "Do NOT use exec_tools.execute_code_python in a multi-action round" in text
    assert "it must be the only action in the round" in text
    assert "If you cite a channel token literally, write it in backticks like `channel:CHANNEL_ID`." in text

"""The shared multi-user + multi-agent isolation gate (platform/identity.py).

The two vendored agents were single-user. One deployment is tenant/project-bound,
but one process serves many users and this app hosts both agents. The same app can
also run in another deployment against shared backing stores. ``identity.py`` keeps
the keys partitioned by deployment, user, conversation, and active agent id. These
tests import that module directly (stdlib-only, no DB / API).
"""
from __future__ import annotations

from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _identity_module():
    _name, module = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "identity.py")
    return module


def test_same_raw_user_in_different_tenants_gets_different_keys() -> None:
    mod = _identity_module()
    a = mod.turn_identity(
        {"tenant": "t1", "project": "p", "user": "alice", "conversation_id": "c1"},
        agent_id="lg-solution",
    )
    b = mod.turn_identity(
        {"tenant": "t2", "project": "p", "user": "alice", "conversation_id": "c1"},
        agent_id="lg-solution",
    )
    assert a.user_id != b.user_id
    assert a.user_id == "t1:p:lg-solution:alice"
    assert b.user_id == "t2:p:lg-solution:alice"


def test_same_raw_user_in_different_projects_gets_different_keys() -> None:
    mod = _identity_module()
    a = mod.turn_identity({"tenant": "t", "project": "p1", "user": "alice"}, agent_id="lg-solution")
    b = mod.turn_identity({"tenant": "t", "project": "p2", "user": "alice"}, agent_id="lg-solution")
    assert a.user_id != b.user_id


def test_the_two_agents_get_different_keys_for_the_same_user_and_conversation() -> None:
    """The multi-agent invariant: the SAME (tenant, project, user, conversation)
    resolves to DIFFERENT per-user + per-conversation keys under the two agents, so
    lg-solution's memory can never bleed into lg-react's (and vice versa)."""
    mod = _identity_module()
    state = {"tenant": "t", "project": "p", "user": "alice", "conversation_id": "c1"}
    sol = mod.turn_identity(state, agent_id="lg-solution")
    pre = mod.turn_identity(state, agent_id="lg-react")

    assert sol.user_id != pre.user_id
    assert sol.thread_id != pre.thread_id
    assert sol.user_id == "t:p:lg-solution:alice"
    assert pre.user_id == "t:p:lg-react:alice"
    assert sol.agent_id == "lg-solution"
    assert pre.agent_id == "lg-react"


def test_thread_id_is_scoped_by_user_and_agent() -> None:
    mod = _identity_module()
    ident = mod.turn_identity(
        {"tenant": "t", "project": "p", "user": "alice", "conversation_id": "conv-42"},
        agent_id="lg-react",
    )
    assert ident.thread_id == "t:p:lg-react:alice:conv-42"


def test_shared_conversation_id_across_users_never_collides() -> None:
    mod = _identity_module()
    a = mod.turn_identity(
        {"tenant": "t", "project": "p", "user": "alice", "conversation_id": "shared"},
        agent_id="lg-solution",
    )
    b = mod.turn_identity(
        {"tenant": "t", "project": "p", "user": "bob", "conversation_id": "shared"},
        agent_id="lg-solution",
    )
    assert a.thread_id != b.thread_id


def test_session_id_and_fallback_thread_id() -> None:
    mod = _identity_module()
    by_session = mod.turn_identity(
        {"tenant": "t", "project": "p", "user": "alice", "session_id": "sess-7"},
        agent_id="lg-solution",
    )
    assert by_session.thread_id == "t:p:lg-solution:alice:sess-7"
    by_fallback = mod.turn_identity(
        {"tenant": "t", "project": "p", "user": "alice"},
        agent_id="lg-solution",
        fallback_thread_id="thread-9",
    )
    assert by_fallback.thread_id == "t:p:lg-solution:alice:thread-9"


def test_anonymous_fallback_and_blank_agent() -> None:
    mod = _identity_module()
    # No user, no fingerprint -> "anonymous".
    anon = mod.turn_identity({"tenant": "t", "project": "p"}, agent_id="lg-solution")
    assert anon.user_id == "t:p:lg-solution:anonymous"
    # Fingerprint is used when no resolved user is present.
    fp = mod.turn_identity({"tenant": "t", "project": "p", "fingerprint": "fp-123"}, agent_id="lg-solution")
    assert fp.user_id == "t:p:lg-solution:fp-123"
    # A blank agent id folds to "default" so keys stay deterministic.
    bare = mod.turn_identity({}, agent_id="")
    assert bare.user_id == "t:p:default:anonymous"
    assert bare.thread_id == "t:p:default:anonymous:default"


def test_missing_tenant_project_use_safe_placeholders() -> None:
    mod = _identity_module()
    ident = mod.turn_identity({"user": "alice"}, agent_id="lg-react")
    assert ident.user_id == "t:p:lg-react:alice"
    assert ident.thread_id == "t:p:lg-react:alice:default"


def test_telegram_scoped_user_gets_an_isolated_memory_key() -> None:
    # The Telegram webhook resolves a sender to the platform user `telegram_<id>`
    # and drives the DEFAULT agent's turn, so by the time this gate runs
    # state["user"] is already that scoped id. It folds identically.
    mod = _identity_module()
    tg = mod.turn_identity(
        {"tenant": "t", "project": "p", "user": "telegram_12345", "conversation_id": "telegram_chat_7"},
        agent_id="lg-solution",
    )
    assert tg.user_id == "t:p:lg-solution:telegram_12345"

    browser = mod.turn_identity({"tenant": "t", "project": "p", "user": "12345"}, agent_id="lg-solution")
    other_tg = mod.turn_identity({"tenant": "t", "project": "p", "user": "telegram_99999"}, agent_id="lg-solution")
    assert tg.user_id != browser.user_id
    assert tg.user_id != other_tg.user_id

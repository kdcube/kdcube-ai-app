# SPDX-License-Identifier: MIT

"""Owner-qualified conversation ref tests across ReAct resolvers.

The agent receives self-describing paths from memsearch like:

    conv:ev:conv_<id>.turn_<id>.events/...
    conv:ws:conv_<id>.turn_<id>.conv.working.summary
    conv:ar:conv_<id>.turn_<id>.react.turn.index
    conv:tc:conv_<id>.turn_<id>.<call_id>.result
    conv:fi:conv_<id>.turn_<id>.files/...

The leading ``conv:`` is the owner namespace. The ``conv_<id>`` segment names
the owning conversation and remains distinct from that namespace. These tests
verify local versus owner-qualified forms without accepting orphan prefixes.
"""

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.runtime.harness.workspace.references import peel_conversation_prefix
from kdcube_ai_app.apps.chat.sdk.solutions.react.timeline import (
    parse_turn_index_path,
    parse_turn_index_ref,
)


# ---------------------------------------------------------------- peeler ----

def test_peel_bare_path_returns_empty_conv():
    ns, conv_id, unscoped = peel_conversation_prefix("conv:ar:turn_X.react.turn.index")
    assert ns == "conv:ar:"
    assert conv_id == ""
    assert unscoped == "conv:ar:turn_X.react.turn.index"


def test_peel_scoped_path_splits_correctly():
    ns, conv_id, unscoped = peel_conversation_prefix("conv:ws:conv_abc.turn_X.conv.working.summary")
    assert ns == "conv:ws:"
    assert conv_id == "abc"
    assert unscoped == "conv:ws:turn_X.conv.working.summary"


def test_peel_handles_all_supported_namespaces():
    for ns in ("conv:fi:", "conv:ev:", "conv:ar:", "conv:ws:", "conv:tc:", "conv:so:"):
        out_ns, conv_id, unscoped = peel_conversation_prefix(f"{ns}conv_xyz.turn_Y.tail")
        assert out_ns == ns
        assert conv_id == "xyz"
        assert unscoped == f"{ns}turn_Y.tail"


def test_peel_does_not_invent_conversation_ids():
    # The peeler must never extract a conv_id from inputs that don't start with
    # `<ns>:conv_<id>.`. The returned path stays unchanged in all these cases.
    # https://example.com/... starts with `https:` but no conv_ segment follows.
    _, conv, unscoped = peel_conversation_prefix("https://example.com/conv_X.foo")
    assert conv == ""
    assert unscoped == "https://example.com/conv_X.foo"
    # C:\path — uppercase scheme is rejected entirely.
    assert peel_conversation_prefix("C:\\path") == ("", "", "C:\\path")
    # No scheme at all.
    assert peel_conversation_prefix("sources_pool[1,2]") == ("", "", "sources_pool[1,2]")
    # Empty input is preserved.
    assert peel_conversation_prefix("") == ("", "", "")


def test_peel_no_segment_after_conv_prefix_returns_unchanged():
    # `ws:conv_abc` with no `.<rest>` after the conv segment is malformed; the
    # peeler must not strip it.
    out_ns, conv_id, unscoped = peel_conversation_prefix("conv:ws:conv_abc")
    assert out_ns == "conv:ws:"
    assert conv_id == ""
    assert unscoped == "conv:ws:conv_abc"


# ----------------------------------------------------- turn-index parser ----

def test_parse_turn_index_path_bare():
    assert parse_turn_index_path("conv:ar:turn_X.react.turn.index") == "turn_X"


def test_parse_turn_index_path_cross_conv():
    # Strip the conv_<id>. prefix silently; return the turn_id alone.
    assert parse_turn_index_path("conv:ar:conv_abc.turn_X.react.turn.index") == "turn_X"


def test_parse_turn_index_path_rejects_wrong_prefix_or_suffix():
    assert parse_turn_index_path("conv:ws:turn_X.conv.working.summary") is None
    assert parse_turn_index_path("conv:ar:turn_X") is None
    assert parse_turn_index_path("") is None
    assert parse_turn_index_path(None) is None  # type: ignore[arg-type]


def test_parse_turn_index_ref_returns_both():
    assert parse_turn_index_ref("conv:ar:turn_X.react.turn.index") == ("", "turn_X")
    assert parse_turn_index_ref("conv:ar:conv_abc.turn_X.react.turn.index") == ("abc", "turn_X")
    assert parse_turn_index_ref("conv:ws:turn_X.conv.working.summary") is None
    assert parse_turn_index_ref("conv:ar:conv_abc") is None

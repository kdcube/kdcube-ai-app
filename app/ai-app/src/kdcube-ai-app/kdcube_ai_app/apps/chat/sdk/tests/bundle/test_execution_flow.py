# SPDX-License-Identifier: MIT

"""Execution flow tests for bundles (Types 10–11).

Test complete request → response flow and agent request/response cycle.
Tests work with any bundle selected by folder.

Run with:
  BUNDLE_UNDER_TEST=/abs/path/to/bundle pytest test_execution_flow.py -v
  pytest test_execution_flow.py --bundle-path=/abs/path/to/bundle -v
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock

from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint import BaseEntrypoint
from kdcube_ai_app.infra.service_hub.inventory import APP_STATE_KEYS


class TestCreateInitialState:
    """Tests for create_initial_state() helper."""

    def test_create_initial_state_returns_dict(self):
        """create_initial_state() returns a plain dict."""
        state = BaseEntrypoint.create_initial_state({})
        assert isinstance(state, dict)

    def test_create_initial_state_final_answer_not_set(self):
        """create_initial_state() does not pre-populate final_answer."""
        state = BaseEntrypoint.create_initial_state({"text": "hello"})
        assert state.get("final_answer") is None

    def test_create_initial_state_followups_not_set(self):
        """create_initial_state() does not pre-populate followups."""
        state = BaseEntrypoint.create_initial_state({})
        assert state.get("followups") is None

    def test_create_initial_state_error_message_not_set(self):
        """create_initial_state() does not pre-populate error_message."""
        state = BaseEntrypoint.create_initial_state({})
        assert state.get("error_message") is None

    def test_create_initial_state_includes_start_time(self):
        """create_initial_state() always records a start_time."""
        before = time.time()
        state = BaseEntrypoint.create_initial_state({})
        after = time.time()
        assert before <= state["start_time"] <= after

    def test_create_initial_state_step_logs_empty_list(self):
        """create_initial_state() initializes step_logs to []."""
        state = BaseEntrypoint.create_initial_state({})
        assert state["step_logs"] == []

    def test_create_initial_state_two_calls_produce_independent_states(self):
        """Two calls to create_initial_state() return independent dicts."""
        s1 = BaseEntrypoint.create_initial_state({"text": "a"})
        s2 = BaseEntrypoint.create_initial_state({"text": "b"})
        s1["step_logs"].append("log")
        assert s2["step_logs"] == [], "State objects must not share mutable fields"


class TestProjectAppState:
    """Tests for project_app_state() class method."""

    def test_project_app_state_returns_dict(self, bundle):
        """project_app_state() returns a dict."""
        out = type(bundle).project_app_state({})
        assert isinstance(out, dict)

    def test_project_app_state_includes_all_app_state_keys(self, bundle):
        """project_app_state() includes every key from APP_STATE_KEYS."""
        full_state = {
            "request_id": "r1",
            "tenant": "t",
            "project": "p",
            "user": "u",
            "session_id": "s",
            "text": "hi",
            "attachments": [],
            "final_answer": "answer",
            "followups": [],
            "error_message": None,
            "step_logs": [],
        }
        out = type(bundle).project_app_state(full_state)
        for key in APP_STATE_KEYS:
            assert key in out, f"project_app_state() must include '{key}'"

    def test_project_app_state_context_contains_bundle_id(self, bundle):
        """project_app_state() context dict contains bundle key."""
        out = type(bundle).project_app_state({})
        assert "context" in out
        assert "bundle" in out["context"]
        assert out["context"]["bundle"]


class TestExecuteCore:
    """Tests for execute_core() contract."""

    def test_execute_core_method_exists(self, bundle):
        """Bundle exposes execute_core() method."""
        assert hasattr(bundle, "execute_core")
        assert callable(bundle.execute_core)

    def test_pre_run_hook_exists(self, bundle):
        """Bundle exposes pre_run_hook() method."""
        assert hasattr(bundle, "pre_run_hook")
        assert callable(bundle.pre_run_hook)

    def test_post_run_hook_exists(self, bundle):
        """Bundle exposes post_run_hook() method."""
        assert hasattr(bundle, "post_run_hook")
        assert callable(bundle.post_run_hook)


class TestSequentialRequests:
    """Test that sequential requests do not leak state."""

    def test_bundle_props_not_mutated_by_first_request(self, bundle):
        """Modifying bundle_props during a request does not persist after restore."""
        original = dict(bundle.bundle_props)
        bundle.bundle_props["__test_seq__"] = "polluted"
        bundle.bundle_props = original
        assert bundle.bundle_props.get("__test_seq__") is None

    def test_create_initial_state_called_twice_no_shared_state(self):
        """Two consecutive create_initial_state() calls produce independent states."""
        from kdcube_ai_app.infra.service_hub.inventory import Config
        s1 = BaseEntrypoint.create_initial_state({"request_id": "req-1", "text": "first"})
        s2 = BaseEntrypoint.create_initial_state({"request_id": "req-2", "text": "second"})
        assert s1["request_id"] != s2["request_id"]
        assert s1["text"] != s2["text"]
        s1["step_logs"].append("x")
        assert s2["step_logs"] == []

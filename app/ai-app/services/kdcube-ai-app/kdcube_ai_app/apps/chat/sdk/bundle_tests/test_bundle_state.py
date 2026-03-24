# SPDX-License-Identifier: MIT

"""BundleState tests for bundles (Type 4).

Test that request/response state is handled correctly.
Tests work with any bundle specified via --bundle-id parameter.

Run with:
  pytest test_bundle_state.py --bundle-id=react.doc -v
  pytest test_bundle_state.py --bundle-id=openrouter-data -v
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from kdcube_ai_app.infra.service_hub.inventory import Config
from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint import BaseEntrypoint


class TestBundleState:
    """Test that request/response state is handled correctly."""

    def test_create_initial_state_preserves_required_fields(self):
        """create_initial_state preserves request_id, tenant, project, user."""
        payload = {
            "request_id": "req-123",
            "tenant": "acme",
            "project": "main",
            "user": "user-456",
            "user_type": "registered",
            "session_id": "sess-789",
            "conversation_id": "conv-abc",
            "text": "hello world",
        }
        state = BaseEntrypoint.create_initial_state(payload)

        assert state["request_id"] == "req-123"
        assert state["tenant"] == "acme"
        assert state["project"] == "main"
        assert state["user"] == "user-456"
        assert state["user_type"] == "registered"
        assert state["session_id"] == "sess-789"
        assert state["conversation_id"] == "conv-abc"
        assert state["text"] == "hello world"

    def test_create_initial_state_generates_request_id_if_missing(self):
        """create_initial_state generates request_id when not provided."""
        payload = {"tenant": "t", "project": "p", "user": "u"}
        state = BaseEntrypoint.create_initial_state(payload)
        assert state["request_id"]
        assert isinstance(state["request_id"], str)
        assert len(state["request_id"]) > 0

    def test_create_initial_state_initializes_step_logs(self):
        """create_initial_state initializes step_logs to empty list."""
        state = BaseEntrypoint.create_initial_state({})
        assert "step_logs" in state
        assert state["step_logs"] == []

    def test_create_initial_state_initializes_start_time(self):
        """create_initial_state records a start_time timestamp."""
        import time
        before = time.time()
        state = BaseEntrypoint.create_initial_state({})
        after = time.time()
        assert "start_time" in state
        assert before <= state["start_time"] <= after

    def test_create_initial_state_handles_attachments_from_payload_key(self):
        """Attachments read from top-level 'attachments' key."""
        attachments = [{"type": "image", "url": "https://example.com/img.png"}]
        payload = {"attachments": attachments}
        state = BaseEntrypoint.create_initial_state(payload)
        assert state["attachments"] == attachments

    def test_create_initial_state_handles_attachments_from_nested_payload(self):
        """Attachments read from nested payload.attachments when top-level missing."""
        attachments = [{"type": "file", "name": "doc.pdf"}]
        payload = {"payload": {"attachments": attachments}}
        state = BaseEntrypoint.create_initial_state(payload)
        assert state["attachments"] == attachments

    def test_create_initial_state_defaults_attachments_to_empty_list(self):
        """Attachments default to empty list when not provided."""
        state = BaseEntrypoint.create_initial_state({})
        assert state["attachments"] == []

    def test_create_initial_state_strips_whitespace_from_text(self):
        """Text is stripped of leading/trailing whitespace."""
        payload = {"text": "  hello  "}
        state = BaseEntrypoint.create_initial_state(payload)
        assert state["text"] == "hello"

    def test_create_initial_state_text_defaults_to_empty_string(self):
        """Text defaults to empty string when not provided."""
        state = BaseEntrypoint.create_initial_state({})
        assert state["text"] == ""

    def test_bundle_state_final_answer_field_exists_in_type(self):
        """BundleState TypedDict contains final_answer field."""
        from kdcube_ai_app.infra.service_hub.inventory import BundleState
        annotations = BundleState.__annotations__
        assert "final_answer" in annotations

    def test_bundle_state_followups_field_exists_in_type(self):
        """BundleState TypedDict contains followups field."""
        from kdcube_ai_app.infra.service_hub.inventory import BundleState
        annotations = BundleState.__annotations__
        assert "followups" in annotations

    def test_bundle_state_error_message_field_exists_in_type(self):
        """BundleState TypedDict contains error_message field."""
        from kdcube_ai_app.infra.service_hub.inventory import BundleState
        annotations = BundleState.__annotations__
        assert "error_message" in annotations

    def test_bundle_state_attachments_field_exists_in_type(self):
        """BundleState TypedDict contains attachments field."""
        from kdcube_ai_app.infra.service_hub.inventory import BundleState
        annotations = BundleState.__annotations__
        assert "attachments" in annotations

    def test_state_does_not_leak_between_bundle_instances(self):
        """Two separate bundle instances do not share state."""
        try:
            from pathlib import Path
            from kdcube_ai_app.infra.plugin.bundle_store import _examples_root
            from kdcube_ai_app.infra.plugin.agentic_loader import (
                AgenticBundleSpec,
                _resolve_module,
                _discover_decorated,
            )
            root = _examples_root()
            candidates = [
                d for d in sorted(root.iterdir())
                if d.is_dir() and (d / "entrypoint.py").exists()
            ]
            if not candidates:
                pytest.skip("No bundles found in examples/bundles/")

            bundle_dir = candidates[0]
            spec = AgenticBundleSpec(path=str(bundle_dir), module="entrypoint")
            mod = _resolve_module(spec)
            chosen = _discover_decorated(mod)
            if chosen is None or chosen[0] != "class":
                pytest.skip("No class-based bundle found")

            bundle_cls = chosen[2]
            instance_a = bundle_cls(config=Config(), redis=MagicMock(), comm_context=MagicMock())
            instance_b = bundle_cls(config=Config(), redis=MagicMock(), comm_context=MagicMock())

            # Mutate A's bundle_props — B must be unaffected
            instance_a.bundle_props["_test_marker"] = "instance-a"
            assert instance_b.bundle_props.get("_test_marker") is None, (
                "Mutating instance A's bundle_props must not affect instance B"
            )
        except ImportError as e:
            pytest.skip(f"Cannot import bundle infrastructure: {e}")

    def test_project_app_state_includes_app_state_keys(self, bundle):
        """project_app_state() outputs all APP_STATE_KEYS."""
        from kdcube_ai_app.infra.service_hub.inventory import APP_STATE_KEYS

        full_state = {
            "request_id": "req-1",
            "tenant": "t",
            "project": "p",
            "user": "u",
            "session_id": "s",
            "text": "hi",
            "attachments": [],
            "final_answer": "The answer",
            "followups": ["follow up?"],
            "error_message": None,
            "step_logs": [],
        }
        out = type(bundle).project_app_state(full_state)

        for key in APP_STATE_KEYS:
            assert key in out, f"project_app_state() must include '{key}'"

    def test_project_app_state_includes_bundle_context(self, bundle):
        """project_app_state() includes bundle ID in context."""
        out = type(bundle).project_app_state({})
        assert "context" in out
        assert "bundle" in out["context"]
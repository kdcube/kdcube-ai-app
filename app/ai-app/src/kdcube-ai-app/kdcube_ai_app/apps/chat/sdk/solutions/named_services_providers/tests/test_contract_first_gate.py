# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Contract-first gate on the named-service grammar dispatch.

Surfaced case: the ReAct agent sent `object_action(action="send")` on the mail
namespace with a guessed payload (`attachments[].content_base64`) without ever
reading `object_schema` — actions are realm-defined named protocols, so the
payload was wrong by construction. The dispatch now returns ONE instructive
protocol rejection for the first action/upsert on a namespace whose contract
has not been read in the conversation; the retry proceeds, and a
schema/provider_about read clears the gate — including across processes via
the shared conversation workspace (the exec-brokered path).
"""

from __future__ import annotations

import contextlib
import json

import pytest

from kdcube_ai_app.apps.chat.sdk.infra.bundle_operations import (
    BundleNamedServiceResult,
    bind_bundle_named_service_caller,
)
from kdcube_ai_app.apps.chat.sdk.runtime.run_ctx import OUTDIR_CV
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers import (
    NamedServiceResponse,
    tools as ns_tools,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.contract_gate import (
    GATE_STATE_FILENAME,
    reset_contract_gate_process_state,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.instructions import (
    NAMED_SERVICES_REACT_ADDITIONAL_INSTRUCTIONS,
)


@contextlib.contextmanager
def _workspace(tmp_path):
    token = OUTDIR_CV.set(str(tmp_path))
    try:
        yield
    finally:
        OUTDIR_CV.reset(token)


def _bind_mail_client() -> None:
    ns_tools.bind_registry({
        "bundle_props": {
            "named_services": {
                "namespaces": {
                    "mail": {
                        "providers": [{"bundle_id": "mail@1-0", "provider": "mail.gmail"}],
                        "clients": {
                            "main": {"tools": {"allowed_operations": ["*"]}},
                        },
                    },
                },
            },
        },
        "client_id": "main",
    })


def _recording_caller(calls: list):
    async def _caller(call):
        calls.append(call)
        return BundleNamedServiceResult(
            NamedServiceResponse.ok_response(
                provider={"provider_id": call.request.provider},
                namespace=call.request.namespace,
                extra={"operation": call.request.operation},
            )
        )

    return _caller


@pytest.mark.asyncio
async def test_first_action_without_contract_is_rejected_once_then_retry_proceeds(tmp_path):
    _bind_mail_client()
    calls: list = []
    with _workspace(tmp_path), bind_bundle_named_service_caller(_recording_caller(calls)):
        first = await ns_tools.object_action(
            namespace="mail",
            object_ref="mail:gmail:acct-1",
            action="send",
            payload=json.dumps({"to": "someone@example.com"}),
        )
        retry = await ns_tools.object_action(
            namespace="mail",
            object_ref="mail:gmail:acct-1",
            action="send",
            payload=json.dumps({"to": "someone@example.com"}),
        )

    # The exact surfaced case: the guessed first action is rejected with the
    # instructive protocol notice, and the provider is never called for it.
    assert first["ok"] is False
    assert first["error"] == "named_service_contract_not_read"
    assert "Read the action contract first" in first["message"]
    assert "named_services.object_schema" in first["message"]
    assert first["fix"]["actor"] == "agent"
    # One rejection only: the nudge is recorded, the retry proceeds.
    assert retry["ok"] is True
    assert [call.request.operation for call in calls] == ["object.action"]
    # The nudge lives in the shared conversation-workspace state file.
    state = json.loads((tmp_path / GATE_STATE_FILENAME).read_text(encoding="utf-8"))
    assert "mail" in state["nudged"]


@pytest.mark.asyncio
async def test_schema_read_clears_the_gate(tmp_path):
    _bind_mail_client()
    calls: list = []
    with _workspace(tmp_path), bind_bundle_named_service_caller(_recording_caller(calls)):
        schema = await ns_tools.object_schema(namespace="mail")
        action = await ns_tools.object_action(
            namespace="mail",
            object_ref="mail:gmail:acct-1",
            action="send",
        )

    assert schema["ok"] is True
    assert action["ok"] is True
    assert [call.request.operation for call in calls] == ["object.schema", "object.action"]


@pytest.mark.asyncio
async def test_provider_about_clears_the_gate(tmp_path):
    _bind_mail_client()
    calls: list = []
    with _workspace(tmp_path), bind_bundle_named_service_caller(_recording_caller(calls)):
        about = await ns_tools.provider_about(namespace="mail")
        action = await ns_tools.object_action(
            namespace="mail",
            object_ref="mail:gmail:acct-1",
            action="send",
        )

    assert about["ok"] is True
    assert action["ok"] is True
    assert [call.request.operation for call in calls] == ["provider.about", "object.action"]


@pytest.mark.asyncio
async def test_first_upsert_without_contract_is_rejected_then_retry_proceeds(tmp_path):
    _bind_mail_client()
    calls: list = []
    with _workspace(tmp_path), bind_bundle_named_service_caller(_recording_caller(calls)):
        first = await ns_tools.upsert_object(
            namespace="mail",
            object_json=json.dumps({"subject": "draft"}),
        )
        retry = await ns_tools.upsert_object(
            namespace="mail",
            object_json=json.dumps({"subject": "draft"}),
        )

    assert first["ok"] is False
    assert first["error"] == "named_service_contract_not_read"
    assert "Read the object contract first" in first["message"]
    assert retry["ok"] is True
    assert [call.request.operation for call in calls] == ["object.upsert"]


@pytest.mark.asyncio
async def test_contract_read_recorded_by_another_process_clears_the_gate(tmp_path):
    """The exec-brokered path: a child process starts with empty in-process
    state but shares the conversation workspace file, so a schema read done in
    the chat process clears the gate for it."""

    _bind_mail_client()
    calls: list = []
    with _workspace(tmp_path), bind_bundle_named_service_caller(_recording_caller(calls)):
        schema = await ns_tools.object_schema(namespace="mail")
        assert schema["ok"] is True

        # Fresh process memory, same workspace file.
        reset_contract_gate_process_state()

        action = await ns_tools.object_action(
            namespace="mail",
            object_ref="mail:gmail:acct-1",
            action="send",
        )

    assert action["ok"] is True
    assert [call.request.operation for call in calls] == ["object.schema", "object.action"]


@pytest.mark.asyncio
async def test_in_process_fallback_gates_without_a_workspace():
    _bind_mail_client()
    calls: list = []
    with bind_bundle_named_service_caller(_recording_caller(calls)):
        first = await ns_tools.object_action(
            namespace="mail",
            object_ref="mail:gmail:acct-1",
            action="send",
        )
        retry = await ns_tools.object_action(
            namespace="mail",
            object_ref="mail:gmail:acct-1",
            action="send",
        )

    assert first["ok"] is False
    assert first["error"] == "named_service_contract_not_read"
    assert retry["ok"] is True
    assert [call.request.operation for call in calls] == ["object.action"]


def test_instructions_carry_the_contract_first_rule():
    text = NAMED_SERVICES_REACT_ADDITIONAL_INSTRUCTIONS
    # The hard rule sits at the action decision point (path 5), positively
    # framed, scoped to the conversation like the platform gate.
    assert "Before your FIRST `object_action` or `upsert_object` on a namespace in a conversation" in text
    assert "realm-defined named protocol" in text
    # The dispatch behavior is named so the model can interpret the rejection.
    assert "protocol notice" in text
    # Path 6 keys upserts to the same rule.
    assert "The contract-first rule in 5 covers `upsert_object`" in text

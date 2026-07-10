# SPDX-License-Identifier: MIT

"""Named-service relay over the Data Bus.

Surfaced case: a named-service call from generated code (exec supervisor)
died with `named_service_api_endpoint_unavailable` — no live registry caller
exists outside the host proc. The relay publishes the request to the provider
bundle's Data Bus stream and waits for the recorded result; the server side
is idempotent per message id so bus redelivery never re-runs the action.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from kdcube_ai_app.apps.chat.sdk.protocol import (
    ExternalEventActor,
    ExternalEventPayload,
    ExternalEventRouting,
    ExternalEventUser,
)
from kdcube_ai_app.apps.chat.sdk.runtime.comm_ctx import bind_current_request_context
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers import relay
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.types import (
    NamedServiceRequest,
    NamedServiceResponse,
)


def _request_context() -> ExternalEventPayload:
    return ExternalEventPayload(
        routing=ExternalEventRouting(bundle_id="workspace@2026-03-31-13-36", session_id="sess-1"),
        actor=ExternalEventActor(tenant_id="demo-tenant", project_id="demo-project"),
        user=ExternalEventUser(user_type="registered", user_id="user-1", roles=["kdcube:role:registered"]),
    )


def _send_request() -> NamedServiceRequest:
    return NamedServiceRequest(
        operation="object.action",
        namespace="mail",
        object_ref="mail:gmail:acc-1",
        action="send",
        payload={"to": "user@example.test", "subject": "Hi"},
    )


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value


@pytest.mark.asyncio
async def test_relay_call_carries_identity_and_returns_provider_response(monkeypatch):
    captured: dict[str, Any] = {}

    async def _publish_and_wait(self, **kwargs):
        captured.update(kwargs)
        return {
            "status": "ok",
            "message_id": kwargs["message_id"],
            "data": {"response": {"ok": True, "ret": {"attrs": {"namespace": "mail"}}, "status": 200}},
        }

    monkeypatch.setattr(relay.DataBusPublisher, "publish_and_wait", _publish_and_wait)

    with bind_current_request_context(_request_context()):
        response = await relay.relay_named_service_call(
            bundle_id="kdcube-services@1-0",
            request=_send_request(),
        )

    assert isinstance(response, NamedServiceResponse)
    assert response.ok is True
    assert captured["subject"] == relay.NAMED_SERVICE_RELAY_SUBJECT
    # The carried request identity rides as the bus actor — the provider
    # authorizes against the real user, never a service account.
    assert captured["actor"]["user_id"] == "user-1"
    assert captured["actor"]["user_type"] == "registered"
    assert captured["payload"]["request"]["action"] == "send"
    # Redelivery protection: the message id doubles as the idempotency key.
    assert captured["idempotency_key"] == captured["message_id"]


@pytest.mark.asyncio
async def test_relay_call_times_out_loudly(monkeypatch):
    async def _publish_and_wait(self, **kwargs):
        raise TimeoutError("no result")

    monkeypatch.setattr(relay.DataBusPublisher, "publish_and_wait", _publish_and_wait)

    with bind_current_request_context(_request_context()):
        response = await relay.relay_named_service_call(
            bundle_id="kdcube-services@1-0",
            request=_send_request(),
        )

    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "named_service_relay_timeout"
    assert response.status == 504


@pytest.mark.asyncio
async def test_relay_call_requires_bound_identity():
    response = await relay.relay_named_service_call(
        bundle_id="kdcube-services@1-0",
        request=_send_request(),
        tenant="demo-tenant",
        project="demo-project",
    )
    assert response.ok is False
    assert response.error is not None
    assert response.error.code == "named_service_relay_identity_missing"


@pytest.mark.asyncio
async def test_relay_handler_dispatches_once_and_replays_recorded_result(monkeypatch):
    calls: list[NamedServiceRequest] = []

    class _FakeClient:
        def __init__(self, registry, *, auth_context=None, **kwargs):
            del registry, auth_context, kwargs

        async def call(self, request):
            calls.append(request)
            return NamedServiceResponse(ok=True, ret={"attrs": {"namespace": request.namespace}})

    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.client.NamedServiceClient",
        _FakeClient,
    )

    redis = _FakeRedis()
    bundle = SimpleNamespace(redis=redis, named_services=lambda: object())
    ctx = SimpleNamespace(bundle=bundle)
    message = SimpleNamespace(
        tenant="demo-tenant",
        project="demo-project",
        bundle_id="kdcube-services@1-0",
        message_id="nsrelay_1",
        payload={"request": _send_request().to_dict()},
    )

    with bind_current_request_context(_request_context()):
        first = await relay.handle_named_service_relay(ctx, message)
        # The bus redelivers at-least-once; the second delivery must answer
        # from the recorded result without re-running the send.
        second = await relay.handle_named_service_relay(ctx, message)

    assert first["status"] == "ok"
    assert first["data"]["response"]["ok"] is True
    assert second == first
    assert len(calls) == 1
    cached = json.loads(list(redis.store.values())[0])
    assert cached["data"]["response"]["ok"] is True


@pytest.mark.asyncio
async def test_relay_handler_rejects_message_without_request():
    ctx = SimpleNamespace(bundle=SimpleNamespace(redis=None, named_services=lambda: object()))
    message = SimpleNamespace(
        tenant="demo-tenant",
        project="demo-project",
        bundle_id="kdcube-services@1-0",
        message_id="nsrelay_2",
        payload={},
    )
    result = await relay.handle_named_service_relay(ctx, message)
    assert result["status"] == "rejected"
    assert result["error"]["code"] == "named_service_relay_request_invalid"

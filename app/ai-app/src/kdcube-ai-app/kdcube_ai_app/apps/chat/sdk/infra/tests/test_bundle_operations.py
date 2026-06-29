from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.infra.bundle_operations import (
    BundleOperationCall,
    _apply_request_projection_to_session,
    _target_comm_context,
    bind_bundle_operation_caller,
    call_bundle_operation,
    get_current_bundle_operation_caller,
)
from kdcube_ai_app.apps.chat.sdk.protocol import (
    ExternalEventActor,
    ExternalEventPayload,
    ExternalEventRequest,
    ExternalEventRouting,
    ExternalEventUser,
)
from kdcube_ai_app.auth.sessions import UserSession, UserType


@pytest.mark.asyncio
async def test_call_bundle_operation_uses_bound_request_caller():
    calls: list[BundleOperationCall] = []

    async def _caller(call: BundleOperationCall):
        calls.append(call)
        return {"ok": True, "operation": call.operation, "data": call.data}

    with bind_bundle_operation_caller(_caller):
        result = await call_bundle_operation(
            tenant="tenant-a",
            project="project-a",
            bundle_id="task-tracker@1-0",
            operation="named_service",
            data={"operation": "provider.about"},
        )

    assert result == {"ok": True, "operation": "named_service", "data": {"operation": "provider.about"}}
    assert calls == [
        BundleOperationCall(
            tenant="tenant-a",
            project="project-a",
            bundle_id="task-tracker@1-0",
            operation="named_service",
            data={"operation": "provider.about"},
            route="operations",
        )
    ]
    assert get_current_bundle_operation_caller() is None


@pytest.mark.asyncio
async def test_call_bundle_operation_requires_request_caller():
    with pytest.raises(RuntimeError, match="No request-bound bundle operation caller"):
        await call_bundle_operation(bundle_id="task-tracker@1-0", operation="named_service")


def test_target_comm_context_preserves_identity_authority():
    source = ExternalEventPayload(
        request=ExternalEventRequest(request_id="request-1"),
        routing=ExternalEventRouting(
            bundle_id="user-memories@2026-06-26",
            session_id="session-1",
            conversation_id="conversation-1",
            turn_id="turn-1",
        ),
        actor=ExternalEventActor(tenant_id="tenant-a", project_id="project-a"),
        user=ExternalEventUser(user_type="registered", user_id="telegram_42"),
    )
    session = UserSession(
        session_id="session-1",
        user_type=UserType.PRIVILEGED,
        user_id="telegram_42",
        roles=["kdcube:role:super-admin"],
        permissions=["memories:read"],
        identity_authority={
            "authority_id": "telegram.kdcube_ref",
            "actor_user_id": "telegram_42",
            "platform_user_id": "platform-user-1",
        },
    )

    target = _target_comm_context(
        source,
        bundle_id="connection-hub@1-0",
        tenant="tenant-a",
        project="project-a",
        session=session,
    )

    assert target.user.user_id == "telegram_42"
    assert target.user.identity_authority["platform_user_id"] == "platform-user-1"
    assert target.user.roles == ["kdcube:role:super-admin"]


def test_request_projection_overlays_stored_session_for_peer_calls():
    source = ExternalEventPayload(
        request=ExternalEventRequest(request_id="request-1"),
        routing=ExternalEventRouting(
            bundle_id="user-memories@2026-06-26",
            session_id="session-1",
        ),
        actor=ExternalEventActor(tenant_id="tenant-a", project_id="project-a"),
        user=ExternalEventUser(
            user_type="privileged",
            user_id="telegram_42",
            roles=["kdcube:role:super-admin"],
            permissions=["memories:read"],
            identity_authority={
                "authority_id": "telegram.kdcube_ref",
                "actor_user_id": "telegram_42",
                "platform_user_id": "platform-user-1",
            },
        ),
    )
    stored = UserSession(
        session_id="session-1",
        user_type=UserType.REGISTERED,
        user_id="telegram_42",
        roles=[],
        permissions=[],
    )

    session = _apply_request_projection_to_session(stored, source)

    assert session.identity_authority["platform_user_id"] == "platform-user-1"
    assert session.user_type == "privileged"
    assert session.roles == ["kdcube:role:super-admin"]
    assert session.permissions == ["memories:read"]

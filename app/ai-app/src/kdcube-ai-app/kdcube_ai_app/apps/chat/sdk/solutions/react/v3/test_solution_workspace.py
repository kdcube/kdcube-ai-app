# SPDX-License-Identifier: MIT

import pytest


@pytest.mark.asyncio
async def test_emit_solver_artifacts_preserves_transport_fields():
    from kdcube_ai_app.apps.chat.sdk.solutions.react.solution_workspace import ApplicationHostingService

    class _FakeComm:
        service = {"conversation_id": "conv_1"}

        def __init__(self):
            self.events = []

        async def event(self, **kwargs):
            self.events.append(kwargs)

    comm = _FakeComm()
    hosting = ApplicationHostingService(store=None, comm=comm)

    await hosting.emit_solver_artifacts(
        files=[
            {
                "filename": "diagram-scene-hub.svg",
                "mime": "image/svg+xml",
                "visibility": "external",
                "logical_path": "fi:conv_1.turn_1.user.attachments/named_services/task/digest/diagram-scene-hub.svg",
                "physical_path": "turn_1/attachments/named_services/task/digest/diagram-scene-hub.svg",
                "hosted_uri": "s3://bucket/cb/tenants/t/projects/p/attachments/u/conv_1/turn_1/diagram-scene-hub.svg",
                "key": "cb/tenants/t/projects/p/attachments/u/conv_1/turn_1/diagram-scene-hub.svg",
                "rn": "rn:file",
            }
        ],
        citations=[],
    )

    assert len(comm.events) == 1
    event = comm.events[0]
    assert event["type"] == "chat.files"
    item = event["data"]["items"][0]
    assert item["logical_path"] == "fi:conv_1.turn_1.user.attachments/named_services/task/digest/diagram-scene-hub.svg"
    assert item["physical_path"] == "turn_1/attachments/named_services/task/digest/diagram-scene-hub.svg"
    assert item["hosted_uri"].startswith("s3://bucket/")
    assert item["key"].startswith("cb/tenants/")
    assert item["rn"] == "rn:file"
    assert item["object_ref"] == item["logical_path"]
    assert item["ref"] == item["logical_path"]

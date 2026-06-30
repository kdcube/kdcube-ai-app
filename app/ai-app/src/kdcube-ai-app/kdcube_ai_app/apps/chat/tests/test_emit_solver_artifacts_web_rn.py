# test_emit_solver_artifacts_web_rn.py
import asyncio
from kdcube_ai_app.apps.chat.sdk.solutions.react.solution_workspace import ApplicationHostingService

class _Comm:
    def __init__(self): self.events = []
    async def event(self, **kw): self.events.append(kw)

def _emit(item):
    svc = ApplicationHostingService.__new__(ApplicationHostingService)
    svc.comm = _Comm(); svc.log = __import__("logging").getLogger("t")
    svc._emitted_artifact_files = []
    asyncio.run(
        svc.emit_solver_artifacts(files=[dict(item)], citations=[]))
    return svc.comm.events[-1]["data"]["items"][0]

def test_web_resource_rn_present_and_telegram_fields_stripped():
    out = _emit({"rn": "ef:t:p:file:conv:turn:assistant:map.png",
                 "key": "blobkey123", "hosted_uri": "s3://x",
                 "physical_path": "turn_t1/files/map.png",
                 "filename": "map.png", "mime": "image/png",
                 "logical_path": "fi:turn_t1.files/map.png"})
    assert out["web_resource_rn"] == "ef:t:p:file:conv:turn:assistant:map.png"
    assert "rn" not in out and "hosted_uri" not in out   # Telegram-invisible set unchanged

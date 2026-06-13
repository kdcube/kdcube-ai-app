from __future__ import annotations

from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk.streaming.stream_policy import StreamPolicyViolation
from kdcube_ai_app.infra.service_hub.inventory import ModelServiceBase


class _StreamingService(ModelServiceBase):
    def __init__(self, chunks: list[str]):
        self.config = SimpleNamespace(log_level="ERROR")
        self.chunks = chunks
        self.yielded: list[str] = []

    async def stream_model_text(self, *_args, **_kwargs):
        for chunk in self.chunks:
            self.yielded.append(chunk)
            yield {"event": "text.delta", "text": chunk}
        yield {"event": "final", "usage": {"output_tokens": len(self.yielded)}}


@pytest.mark.asyncio
async def test_stream_policy_violation_propagates_and_stops_streaming():
    service = _StreamingService(["before", "deny", "after"])
    seen: list[str] = []

    async def on_delta(text: str):
        seen.append(text)
        if text == "deny":
            raise StreamPolicyViolation(code="multi_action_bundle_final_answer_after_non_neutral")

    with pytest.raises(StreamPolicyViolation) as exc:
        await service.stream_model_text_tracked(
            object(),
            [],
            on_delta=on_delta,
            client_cfg=SimpleNamespace(provider="fake", model_name="fake-model"),
            role="solver.react.decision",
        )

    assert exc.value.code == "multi_action_bundle_final_answer_after_non_neutral"
    assert seen == ["before", "deny"]
    assert service.yielded == ["before", "deny"]


@pytest.mark.asyncio
async def test_regular_delta_callback_failure_is_logged_but_stream_continues():
    service = _StreamingService(["before", "bad-ui-callback", "after"])
    seen: list[str] = []

    async def on_delta(text: str):
        seen.append(text)
        if text == "bad-ui-callback":
            raise RuntimeError("ui sink failed")

    result = await service.stream_model_text_tracked(
        object(),
        [],
        on_delta=on_delta,
        client_cfg=SimpleNamespace(provider="fake", model_name="fake-model"),
        role="solver.react.decision",
    )

    assert seen == ["before", "bad-ui-callback", "after"]
    assert service.yielded == ["before", "bad-ui-callback", "after"]
    assert result["text"] == "beforebad-ui-callbackafter"
    assert result["service_error"] is None

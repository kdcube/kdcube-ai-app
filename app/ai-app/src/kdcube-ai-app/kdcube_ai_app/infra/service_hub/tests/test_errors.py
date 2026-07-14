from types import SimpleNamespace

from kdcube_ai_app.infra.service_hub.errors import exception_chain, mk_llm_error


def test_exception_chain_preserves_cause_details():
    root = TimeoutError("connect timed out")
    outer = RuntimeError("provider connection failed")
    outer.__cause__ = root

    chain = exception_chain(outer)

    assert chain[0]["type"] == "RuntimeError"
    assert chain[0]["message"] == "provider connection failed"
    assert chain[1]["type"] == "TimeoutError"
    assert chain[1]["message"] == "connect timed out"


def test_mk_llm_error_records_exception_chain_in_context():
    root = OSError("temporary DNS failure")
    outer = RuntimeError("Connection error.")
    outer.__cause__ = root
    cfg = SimpleNamespace(provider="anthropic", model_name="claude-test")

    err = mk_llm_error(
        exc=outer,
        stage="stream_loop",
        cfg=cfg,
        service_name="StreamTracker",
        context={"role": "solver.react.decision"},
    )

    assert err.provider == "anthropic"
    assert err.model_name == "claude-test"
    assert err.context["role"] == "solver.react.decision"
    assert err.context["exception_chain"][0]["type"] == "RuntimeError"
    assert err.context["exception_chain"][1]["type"] == "OSError"

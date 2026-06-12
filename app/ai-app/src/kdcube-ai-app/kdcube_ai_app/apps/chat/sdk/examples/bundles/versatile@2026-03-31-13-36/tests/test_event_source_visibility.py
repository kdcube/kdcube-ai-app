from __future__ import annotations

from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.events import EventSourceSubsystem
from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path
from kdcube_ai_app.apps.chat.sdk.runtime.tool_config import agent_tool_config_from_bundle_props
from kdcube_ai_app.apps.chat.sdk.solutions.canvas.events.defaults import default_canvas_event_source_specs


def _bundle_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _consumer_surfaces():
    _mod_name, module = load_dynamic_module_for_path(_bundle_root() / "consumer_surfaces.py")
    return module


def test_canvas_event_source_visibility_is_separate_from_named_service_actions():
    consumer_surfaces = _consumer_surfaces()
    tool_aliases = {
        str(spec.get("alias") or "")
        for spec in agent_tool_config_from_bundle_props(
            consumer_surfaces.default_as_consumer_surfaces_props(),
            "main",
            bundle_root=_bundle_root(),
        ).tool_specs
        if isinstance(spec, dict)
    }
    assert "canvas" in tool_aliases

    tool_config = agent_tool_config_from_bundle_props(
        consumer_surfaces.default_as_consumer_surfaces_props(),
        "default_agent",
        bundle_root=_bundle_root(),
    )
    assert "object_action" not in (tool_config.allowed_tool_names_by_alias.get("named_services") or [])

    event_sources = EventSourceSubsystem(
        event_specs=default_canvas_event_source_specs(),
        bundle_root=_bundle_root(),
    )

    assert event_sources.namespace_rehoster("cnv") is not None
    assert event_sources.event_source_reader("cnv") is not None
    assert event_sources.by_event_source_id("canvas.read") is not None


def test_reference_default_tool_config_uses_as_consumer_surface():
    props = _consumer_surfaces().default_as_consumer_surfaces_props()
    assert "tools" not in props

    as_consumer = props["surfaces"]["as_consumer"]
    main = as_consumer["agents"]["main"]
    assert as_consumer["default_agent"] == "main"
    assert isinstance(main["tools"], list)
    assert main["event_sources"] == []
    assert as_consumer["ui"]["canvas"]["resolvers"] == []

    tool_config = agent_tool_config_from_bundle_props(props, "main", bundle_root=_bundle_root())
    assert "canvas" in tool_config.allowed_plugins
    assert tool_config.allowed_tool_names_by_alias["canvas"] == ["patch"]
    assert tool_config.allowed_tool_names_by_alias["knowledge"] is None

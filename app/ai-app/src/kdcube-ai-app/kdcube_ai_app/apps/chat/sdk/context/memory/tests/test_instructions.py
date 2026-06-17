from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.context.memory.instructions import (
    resolve_memory_react_additional_instructions,
)


def test_memory_instructions_empty_without_memory_or_named_service_config() -> None:
    assert resolve_memory_react_additional_instructions({}, client_id="main") == ""


def test_memory_instructions_include_read_policy_when_memory_is_announced() -> None:
    text = resolve_memory_react_additional_instructions(
        {
            "memory": {
                "enabled": True,
                "announce": {"enabled": True},
            },
        },
        client_id="main",
    )

    assert "[MEMORY CONTEXT]" in text
    assert "[DURABLE USER MEMORY — POLICY]" in text
    assert "[DURABLE USER MEMORY — NAMED-SERVICE WRITE]" not in text
    assert "memory.record_memory" not in text


def test_memory_instructions_include_named_service_write_when_me_upsert_is_allowed() -> None:
    text = resolve_memory_react_additional_instructions(
        {
            "memory": {
                "enabled": True,
                "announce": {"enabled": True},
            },
            "surfaces": {
                "as_consumer": {
                    "agents": {
                        "main": {
                            "tools": [
                                {
                                    "kind": "named_service",
                                    "namespaces": {
                                        "mem": {
                                            "allowed": ["object.upsert"],
                                            "tool_traits": {
                                                "upsert_object": {
                                                    "strategy": ["neutral"],
                                                },
                                            },
                                        },
                                    },
                                },
                            ],
                        },
                    },
                },
            },
        },
        client_id="main",
    )

    assert "[DURABLE USER MEMORY — NAMED-SERVICE WRITE]" in text
    assert 'named_services.upsert_object(namespace="mem"' in text
    assert "strategy: neutral" in text
    assert "memory.record_memory" not in text

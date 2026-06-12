from __future__ import annotations

from typing import Any


DEFAULT_AGENT_ID = "main"

DEFAULT_AGENT_TOOL_CONNECTIONS: list[dict[str, Any]] = [
    {
        "name": "io",
        "kind": "python",
        "module": "kdcube_ai_app.apps.chat.sdk.tools.io_tools",
        "alias": "io_tools",
        "allowed": ["tool_call"],
    },
    {
        "name": "context",
        "kind": "python",
        "module": "kdcube_ai_app.apps.chat.sdk.tools.ctx_tools",
        "alias": "ctx_tools",
        "allowed": ["merge_sources", "fetch_ctx"],
    },
    {
        "name": "memory",
        "kind": "python",
        "module": "kdcube_ai_app.apps.chat.sdk.context.memory.tools",
        "alias": "memory",
        "allowed": [
            "search_memory",
            "recent_memories",
            "read_memory",
            "record_memory",
            "confirm_memory",
            "retire_memory",
        ],
    },
    {
        "name": "canvas",
        "kind": "python",
        "module": "kdcube_ai_app.apps.chat.sdk.solutions.canvas.tools",
        "alias": "canvas",
        "allowed": ["patch"],
    },
    {
        "name": "exec",
        "kind": "python",
        "module": "kdcube_ai_app.apps.chat.sdk.tools.exec_tools",
        "alias": "exec_tools",
        "allowed": ["execute_code_python"],
    },
    {
        "name": "web",
        "kind": "python",
        "module": "kdcube_ai_app.apps.chat.sdk.tools.web_tools",
        "alias": "web_tools",
        "allowed": ["web_search", "web_fetch"],
        "runtime": {
            "web_search": "local",
            "web_fetch": "local",
        },
    },
    {
        "name": "rendering",
        "kind": "python",
        "module": "kdcube_ai_app.apps.chat.sdk.tools.rendering_tools",
        "alias": "rendering_tools",
        "allowed": ["write_pptx", "write_png", "write_pdf", "write_docx"],
    },
    {
        "name": "browser",
        "kind": "python",
        "module": "kdcube_ai_app.apps.chat.sdk.tools.browser_tools",
        "alias": "browser_tools",
        "allowed": ["open_page", "click", "fill", "scroll", "status", "close"],
        "runtime": {
            "open_page": "none",
            "click": "none",
            "fill": "none",
            "scroll": "none",
            "status": "none",
            "close": "none",
        },
    },
    {
        "name": "knowledge",
        "kind": "mcp",
        "server_id": "knowledge",
        "alias": "knowledge",
        "allowed": ["*"],
    },
]


def default_agent_tool_connections() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_AGENT_TOOL_CONNECTIONS]


def default_as_consumer_surfaces_props(*, agent_id: str = DEFAULT_AGENT_ID) -> dict[str, Any]:
    agent_key = str(agent_id or DEFAULT_AGENT_ID).strip() or DEFAULT_AGENT_ID
    return {
        "surfaces": {
            "as_consumer": {
                "default_agent": agent_key,
                "agents": {
                    agent_key: {
                        "tools": default_agent_tool_connections(),
                        "event_sources": [],
                    },
                },
                "ui": {
                    "canvas": {
                        "resolvers": [],
                    },
                    "scene": {
                        "external_panels": [],
                    },
                },
            },
        },
    }


__all__ = [
    "DEFAULT_AGENT_ID",
    "DEFAULT_AGENT_TOOL_CONNECTIONS",
    "default_agent_tool_connections",
    "default_as_consumer_surfaces_props",
]

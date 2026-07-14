"""The "tools, both ways" seam (platform/tools_mcp.py).

Asserts tool-mode resolution and — critically — clean degradation: with
langchain-mcp-adapters absent (or no servers configured) the agent is still
buildable with the plain vendored tools. Fully offline.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]

PLAIN = ["calc", "unit_convert", "kb_search"]  # stand-ins for tool objects


def _mcp_module():
    _name, module = load_dynamic_module_for_path(BUNDLE_ROOT / "platform" / "tools_mcp.py")
    return module


def test_plain_mode_returns_plain_tools_only() -> None:
    m = _mcp_module()
    tools = asyncio.run(m.resolve_tools({"mode": "plain"}, list(PLAIN)))
    assert tools == PLAIN


def test_default_mode_is_plain() -> None:
    m = _mcp_module()
    tools = asyncio.run(m.resolve_tools({}, list(PLAIN)))
    assert tools == PLAIN


def test_mcp_mode_degrades_to_plain_when_no_servers() -> None:
    m = _mcp_module()
    tools = asyncio.run(m.resolve_tools({"mode": "mcp"}, list(PLAIN)))
    # No configured servers -> no MCP tools -> degrade to plain (never toolless).
    assert tools == PLAIN


def test_both_mode_without_mcp_is_plain() -> None:
    m = _mcp_module()
    tools = asyncio.run(m.resolve_tools({"mode": "both"}, list(PLAIN)))
    # With MCP adapters absent / no reachable server, `both` == plain only.
    assert tools == PLAIN


def test_build_mcp_server_config_shape() -> None:
    m = _mcp_module()
    servers = m.build_mcp_server_config({
        "servers": {
            "knowledge": {
                "url": "https://host/api/mcp/t/p/kb/mcp",
                "headers": {"Authorization": "Bearer x"},
            }
        }
    })
    assert servers["knowledge"]["url"] == "https://host/api/mcp/t/p/kb/mcp"
    # Default transport is streamable_http (KDCube-served MCP endpoints).
    assert servers["knowledge"]["transport"] == "streamable_http"
    assert servers["knowledge"]["headers"]["Authorization"] == "Bearer x"

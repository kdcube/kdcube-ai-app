# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from kdcube_ai_app.apps.chat.sdk.solutions.claude_code.types import ClaudeCodeWorkspaceConfig


def _deep_merge_dict(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in dict(overlay or {}).items():
        if isinstance(result.get(key), dict) and isinstance(value, Mapping):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _write_json(path: Path, payload: Mapping[str, Any], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def prepare_claude_code_workspace(
    workspace_path: str | Path,
    config: ClaudeCodeWorkspaceConfig,
) -> dict[str, Any]:
    """Write standard Claude Code support files into a workspace.

    This helper prepares configuration files only. It does not sandbox Claude,
    resolve secrets, clone repositories, or publish session state.
    """

    workspace = Path(workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    mcp_config = dict(config.mcp_config or {})
    if config.mcp_servers:
        mcp_servers = dict(mcp_config.get("mcpServers") or {})
        mcp_servers.update(dict(config.mcp_servers))
        mcp_config["mcpServers"] = mcp_servers
    if mcp_config:
        path = workspace / ".mcp.json"
        _write_json(path, mcp_config, overwrite=config.overwrite)
        written.append(str(path))

    settings = dict(config.settings or {})
    enabled_servers = config.enabled_mcp_servers
    if enabled_servers is None and config.mcp_servers:
        enabled_servers = tuple(config.mcp_servers.keys())
    if enabled_servers is not None:
        settings.setdefault("enableAllProjectMcpServers", False)
        settings["enabledMcpjsonServers"] = list(enabled_servers)
    if config.allowed_tools or config.denied_tools:
        permissions = dict(settings.get("permissions") or {})
        if config.allowed_tools:
            permissions["allow"] = list(config.allowed_tools)
        if config.denied_tools:
            permissions["deny"] = list(config.denied_tools)
        settings["permissions"] = permissions
    if settings:
        path = workspace / ".claude" / "settings.local.json"
        _write_json(path, settings, overwrite=config.overwrite)
        written.append(str(path))

    if config.instructions_markdown is not None:
        path = workspace / "CLAUDE.md"
        if config.overwrite or not path.exists():
            path.write_text(config.instructions_markdown, encoding="utf-8")
        written.append(str(path))

    return {
        "workspace_path": str(workspace),
        "written_files": written,
        "mcp_servers": list((mcp_config.get("mcpServers") or {}).keys()),
        "enabled_mcp_servers": list(enabled_servers or []),
    }


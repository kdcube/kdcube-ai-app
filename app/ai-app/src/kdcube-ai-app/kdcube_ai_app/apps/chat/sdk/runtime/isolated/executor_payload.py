# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

from __future__ import annotations

from typing import Any, Dict


EXECUTOR_STRIP_RUNTIME_GLOBAL_KEYS = frozenset(
    {
        "BUNDLE_ROOT_HOST",
        "BUNDLE_SPEC",
        "BUNDLE_STORAGE_DIR",
        "BUNDLE_STORAGE_SNAPSHOT_URI",
        "COMM_SPEC",
        "BUNDLE_SNAPSHOT_URI",
        "EXEC_SNAPSHOT",
        "MCP_SERVICES",
        "MCP_TOOL_SPECS",
        "PORTABLE_SPEC",
        "PORTABLE_SPEC_JSON",
        "RAW_TOOL_SPECS",
        "SKILLS_DESCRIPTOR",
        "TOOL_MODULE_FILES",
    }
)


def build_executor_runtime_globals(runtime_globals: Dict[str, Any] | None) -> Dict[str, Any]:
    """Remove privileged/path-bearing runtime state before generated code sees it."""
    exec_globals = dict(runtime_globals or {})
    for key in EXECUTOR_STRIP_RUNTIME_GLOBAL_KEYS:
        exec_globals.pop(key, None)
    return exec_globals

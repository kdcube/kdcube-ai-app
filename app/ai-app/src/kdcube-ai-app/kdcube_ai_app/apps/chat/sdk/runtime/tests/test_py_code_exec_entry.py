# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import json
import types
import pathlib
import sys

from kdcube_ai_app.apps.chat.sdk.runtime.isolated.py_code_exec_entry import (
    _bootstrap_supervisor_runtime,
    _ensure_dynamic_package_chain,
    _hydrate_runtime_payload_from_secret,
)


class _CaptureLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def log(self, message: str, level: str = "INFO") -> None:
        self.messages.append((level, message))


def test_hydrate_runtime_payload_from_secret_restores_env(monkeypatch):
    monkeypatch.delenv("RUNTIME_GLOBALS_JSON", raising=False)
    monkeypatch.delenv("RUNTIME_TOOL_MODULES", raising=False)
    monkeypatch.setenv("KDCUBE_EXEC_PAYLOAD_SECRET_ID", "secret-id")
    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.runtime.isolated.py_code_exec_entry.get_exec_payload_secret",
        lambda **_kwargs: {
            "runtime_globals": {"PORTABLE_SPEC_JSON": "{\"ok\":true}"},
            "tool_module_names": ["dyn_exec_tools_1"],
            "env": {"OPENAI_API_KEY": "secret"},
        },
    )
    logger = _CaptureLogger()

    _hydrate_runtime_payload_from_secret(logger)

    assert json.loads(__import__("os").environ["RUNTIME_GLOBALS_JSON"])["PORTABLE_SPEC_JSON"] == "{\"ok\":true}"
    assert json.loads(__import__("os").environ["RUNTIME_TOOL_MODULES"]) == ["dyn_exec_tools_1"]
    assert __import__("os").environ["OPENAI_API_KEY"] == "secret"
    assert any("hydrate start" in msg for _, msg in logger.messages)
    assert any("Restored runtime payload from secret secret-id" in msg for _, msg in logger.messages)


def test_hydrate_runtime_payload_from_secret_skips_when_inline_payload_present(monkeypatch):
    monkeypatch.setenv("KDCUBE_EXEC_PAYLOAD_SECRET_ID", "secret-id")
    monkeypatch.setenv("RUNTIME_GLOBALS_JSON", "{}")
    monkeypatch.setenv("RUNTIME_TOOL_MODULES", "[]")
    logger = _CaptureLogger()

    _hydrate_runtime_payload_from_secret(logger)

    assert any("hydrate start" in msg for _, msg in logger.messages)
    assert any("skipping secret hydration" in msg for _, msg in logger.messages)


def test_ensure_dynamic_package_chain_creates_parent_packages(tmp_path):
    bundle_root = tmp_path / "bundle"
    tools_dir = bundle_root / "tools"
    tools_dir.mkdir(parents=True)
    tool_file = tools_dir / "preference_tools.py"
    tool_file.write_text("", encoding="utf-8")

    root_name = "dynpkg_60bebbdd6f"
    tools_name = f"{root_name}.tools"
    full_name = f"{tools_name}.preference_tools"

    for name in (root_name, tools_name):
        sys.modules.pop(name, None)

    _ensure_dynamic_package_chain(full_name, tool_file)

    assert root_name in sys.modules
    assert tools_name in sys.modules
    assert pathlib.Path(sys.modules[root_name].__path__[0]).resolve() == bundle_root.resolve()  # type: ignore[attr-defined]
    assert pathlib.Path(sys.modules[tools_name].__path__[0]).resolve() == tools_dir.resolve()  # type: ignore[attr-defined]


def test_bootstrap_supervisor_runtime_resolves_library_module_specs_without_explicit_paths(
    tmp_path,
    monkeypatch,
):
    logger = _CaptureLogger()
    loaded: list[tuple[str, str]] = []
    bootstrapped: dict[str, object] = {}

    def _fake_loader(module_name: str, file_path: str):
        mod = types.ModuleType(module_name)
        mod.__file__ = file_path
        sys.modules[module_name] = mod
        loaded.append((module_name, file_path))
        return mod

    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.runtime.isolated.py_code_exec_entry.load_dynamic_module_from_file",
        _fake_loader,
    )
    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.runtime.isolated.py_code_exec_entry.bootstrap_bind_all",
        lambda ps_str, module_names, bootstrap_env=False: bootstrapped.update(
            {
                "ps_str": ps_str,
                "module_names": list(module_names),
                "bootstrap_env": bootstrap_env,
            }
        ),
    )
    monkeypatch.setattr(
        "kdcube_ai_app.apps.chat.sdk.runtime.isolated.py_code_exec_entry.get_comm",
        lambda: None,
    )

    runtime_globals = {
        "PORTABLE_SPEC_JSON": "{\"ok\": true}",
        "TOOL_ALIAS_MAP": {"io_tools": "dyn_io_tools_test"},
        "TOOL_MODULE_FILES": {},
        "RAW_TOOL_SPECS": [
            {
                "alias": "io_tools",
                "module": "kdcube_ai_app.apps.chat.sdk.tools.io_tools",
            }
        ],
    }

    _bootstrap_supervisor_runtime(runtime_globals, [], logger, tmp_path)

    assert loaded
    assert loaded[0][0] == "dyn_io_tools_test"
    assert loaded[0][1].endswith("/kdcube_ai_app/apps/chat/sdk/tools/io_tools.py")
    assert bootstrapped["ps_str"] == "{\"ok\": true}"
    assert "dyn_io_tools_test" in bootstrapped["module_names"]
    assert any("resolved library module: io_tools" in msg for _, msg in logger.messages)

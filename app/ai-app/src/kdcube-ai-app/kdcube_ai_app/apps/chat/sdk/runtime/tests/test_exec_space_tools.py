import asyncio
import pathlib
import sys
from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import build_dynamic_module_name
from kdcube_ai_app.apps.chat.sdk.runtime.dynamic_module_loader import load_dynamic_module_for_path
from kdcube_ai_app.apps.chat.sdk.runtime.external.base import is_isolated_exec_process


def _load_exec_space_tools_module():
    tool_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "examples"
        / "bundles"
        / "kdcube.copilot@2026-04-03-19-05"
        / "tools"
        / "exec_space_tools.py"
    )
    module_name = build_dynamic_module_name(tool_path)
    root_name = module_name.rsplit(".", 2)[0]
    for name in list(sys.modules):
        if name == root_name or name.startswith(f"{root_name}."):
            sys.modules.pop(name, None)
    module_name, module = load_dynamic_module_for_path(tool_path)
    sys.modules[module_name] = module
    return module


def _load_react_tools_module():
    tool_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "examples"
        / "bundles"
        / "kdcube.copilot@2026-04-03-19-05"
        / "tools"
        / "react_tools.py"
    )
    module_name = build_dynamic_module_name(tool_path)
    root_name = module_name.rsplit(".", 2)[0]
    for name in list(sys.modules):
        if name == root_name or name.startswith(f"{root_name}."):
            sys.modules.pop(name, None)
    module_name, module = load_dynamic_module_for_path(tool_path)
    sys.modules[module_name] = module
    return module


def test_is_isolated_exec_process_requires_runtime_globals(monkeypatch):
    monkeypatch.delenv("RUNTIME_GLOBALS_JSON", raising=False)
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.delenv("WORKDIR", raising=False)
    monkeypatch.delenv("EXECUTION_ID", raising=False)
    monkeypatch.delenv("EXECUTION_SANDBOX", raising=False)
    assert is_isolated_exec_process() is False

    monkeypatch.setenv("RUNTIME_GLOBALS_JSON", "{}")
    monkeypatch.setenv("OUTPUT_DIR", "/workspace/out")
    monkeypatch.setenv("WORKDIR", "/workspace/work")
    assert is_isolated_exec_process() is True


@pytest.mark.asyncio
async def test_kdcube_copilot_exec_space_tool_rejects_non_exec_runtime(monkeypatch):
    monkeypatch.delenv("RUNTIME_GLOBALS_JSON", raising=False)
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.delenv("WORKDIR", raising=False)
    monkeypatch.delenv("BUNDLE_STORAGE_DIR", raising=False)
    sys.modules.pop("_kdcube_copilot_knowledge_resolver", None)

    module = _load_exec_space_tools_module()
    result = await module.tools.resolve_namespace("ks:docs")

    assert result["ok"] is False
    assert result["error"]["code"] == "exec_only_tool"
    assert result["error"]["details"]["logical_ref"] == "ks:docs"
    assert result["ret"]["browseable"] is False
    assert result["ret"]["physical_path"] is None
    assert result["ret"]["access"] == "r"


@pytest.mark.asyncio
async def test_kdcube_copilot_exec_space_tool_resolves_docs_dir_in_exec(tmp_path, monkeypatch):
    knowledge_root = tmp_path / "bundle-storage" / "tenant" / "project" / "kdcube.copilot__main"
    docs_root = knowledge_root / "docs"
    docs_root.mkdir(parents=True)
    (docs_root / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (knowledge_root / "index.md").write_text("# Index\n", encoding="utf-8")

    monkeypatch.setenv("RUNTIME_GLOBALS_JSON", "{}")
    monkeypatch.setenv("OUTPUT_DIR", "/workspace/out")
    monkeypatch.setenv("WORKDIR", "/workspace/work")
    monkeypatch.setenv("BUNDLE_STORAGE_DIR", str(knowledge_root))
    sys.modules.pop("_kdcube_copilot_knowledge_resolver", None)

    module = _load_exec_space_tools_module()
    result = await module.tools.resolve_namespace("ks:docs")

    assert result["ok"] is True
    assert result["error"] is None
    assert result["ret"]["browseable"] is True
    assert result["ret"]["access"] == "r"
    assert result["ret"]["physical_path"] == str(docs_root.resolve())


@pytest.mark.asyncio
async def test_kdcube_copilot_exec_space_tool_returns_managed_error_for_missing_namespace(tmp_path, monkeypatch):
    knowledge_root = tmp_path / "bundle-storage" / "tenant" / "project" / "kdcube.copilot__main"
    knowledge_root.mkdir(parents=True)

    monkeypatch.setenv("RUNTIME_GLOBALS_JSON", "{}")
    monkeypatch.setenv("OUTPUT_DIR", "/workspace/out")
    monkeypatch.setenv("WORKDIR", "/workspace/work")
    monkeypatch.setenv("BUNDLE_STORAGE_DIR", str(knowledge_root))
    sys.modules.pop("_kdcube_copilot_knowledge_resolver", None)

    module = _load_exec_space_tools_module()
    result = await module.tools.resolve_namespace("ks:docs")

    assert result["ok"] is False
    assert result["error"]["code"] == "namespace_not_found"
    assert result["error"]["managed"] is True
    assert "ks:docs" in result["error"]["message"]
    assert result["ret"]["physical_path"] is None
    assert result["ret"]["access"] == "r"
    assert result["ret"]["browseable"] is False


@pytest.mark.asyncio
async def test_kdcube_copilot_exec_space_tool_explains_missing_bundle_storage(monkeypatch):
    monkeypatch.setenv("RUNTIME_GLOBALS_JSON", "{}")
    monkeypatch.setenv("OUTPUT_DIR", "/workspace/out")
    monkeypatch.setenv("WORKDIR", "/workspace/work")
    monkeypatch.delenv("BUNDLE_STORAGE_DIR", raising=False)
    sys.modules.pop("_kdcube_copilot_knowledge_resolver", None)

    module = _load_exec_space_tools_module()
    result = await module.tools.resolve_namespace("ks:src")

    assert result["ok"] is False
    assert result["error"]["code"] == "bundle_storage_unavailable"
    assert result["error"]["managed"] is True
    assert "BUNDLE_STORAGE_DIR is missing" in result["error"]["message"]
    assert "substitute files or inputs" in result["error"]["message"]
    assert result["ret"]["physical_path"] is None


@pytest.mark.asyncio
async def test_kdcube_copilot_react_tools_seed_knowledge_root_from_bound_tool_context(tmp_path, monkeypatch):
    bundle_storage_root = tmp_path / "bundle-storage-root"
    monkeypatch.setenv("BUNDLE_STORAGE_ROOT", str(bundle_storage_root))
    monkeypatch.delenv("BUNDLE_STORAGE_DIR", raising=False)

    knowledge_root = bundle_storage_root / "tenant-a" / "project-a" / "kdcube.copilot__main"
    knowledge_root.mkdir(parents=True, exist_ok=True)
    (knowledge_root / "index.json").write_text(
        '{"items":[{"path":"ks:docs/intro.md","title":"Intro","summary":"KDCube intro guide","tags":["docs"],"keywords":["intro"]}]}',
        encoding="utf-8",
    )

    module = _load_react_tools_module()
    module.knowledge_resolver.KNOWLEDGE_ROOT = None
    module.bind_integrations(
        {
            "tool_subsystem": SimpleNamespace(
                bundle_spec=SimpleNamespace(id="kdcube.copilot", git_commit=None, ref="main", version=None),
                comm=SimpleNamespace(tenant="tenant-a", project="project-a"),
            )
        }
    )

    result = await module.tools.search_knowledge("intro", root="ks:docs")

    assert module.knowledge_resolver.KNOWLEDGE_ROOT == knowledge_root
    assert isinstance(result, list)
    assert result
    assert result[0]["path"] == "ks:docs/intro.md"

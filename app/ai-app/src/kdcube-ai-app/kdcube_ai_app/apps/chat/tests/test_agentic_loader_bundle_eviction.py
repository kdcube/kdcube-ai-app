from __future__ import annotations

import sys
import types
from pathlib import Path

from kdcube_ai_app.infra.plugin.agentic_loader import (
    AgenticBundleSpec,
    _manifest_cache,
    _module_cache,
    _singleton_cache,
    cache_key_for_spec,
    evict_bundle_scope,
)


def test_evict_bundle_scope_removes_only_target_bundle_modules(tmp_path):
    bundle_root = tmp_path / "bundle-a"
    bundle_root.mkdir()
    entrypoint_file = bundle_root / "entrypoint.py"
    utils_file = bundle_root / "utils.py"
    entrypoint_file.write_text("x = 1\n")
    utils_file.write_text("y = 2\n")

    other_root = tmp_path / "bundle-b"
    other_root.mkdir()
    other_file = other_root / "entrypoint.py"
    other_file.write_text("z = 3\n")

    spec = AgenticBundleSpec(path=str(bundle_root), module="entrypoint", singleton=True)
    key = cache_key_for_spec(spec)

    target_module = types.ModuleType("kdcube_bundle_123.entrypoint")
    target_module.__file__ = str(entrypoint_file)
    target_utils = types.ModuleType("kdcube_bundle_123.utils")
    target_utils.__file__ = str(utils_file)
    target_pkg = types.ModuleType("kdcube_bundle_123")
    target_pkg.__path__ = [str(bundle_root)]

    other_module = types.ModuleType("kdcube_bundle_999.entrypoint")
    other_module.__file__ = str(other_file)

    _module_cache[key] = target_module
    _singleton_cache[key] = (object(), target_module)
    _manifest_cache[key] = object()  # type: ignore[assignment]

    sys.modules[target_module.__name__] = target_module
    sys.modules[target_utils.__name__] = target_utils
    sys.modules[target_pkg.__name__] = target_pkg
    sys.modules[other_module.__name__] = other_module

    try:
        result = evict_bundle_scope(spec, drop_sys_modules=True)

        assert result["evicted_modules"] == 1
        assert result["evicted_singletons"] == 1
        assert result["evicted_manifests"] == 1
        assert result["sys_modules_deleted"] >= 3
        assert "kdcube_bundle_123.entrypoint" not in sys.modules
        assert "kdcube_bundle_123.utils" not in sys.modules
        assert "kdcube_bundle_123" not in sys.modules
        assert "kdcube_bundle_999.entrypoint" in sys.modules
    finally:
        _module_cache.pop(key, None)
        _singleton_cache.pop(key, None)
        _manifest_cache.pop(key, None)
        for mod_name in [
            "kdcube_bundle_123.entrypoint",
            "kdcube_bundle_123.utils",
            "kdcube_bundle_123",
            "kdcube_bundle_999.entrypoint",
        ]:
            sys.modules.pop(mod_name, None)

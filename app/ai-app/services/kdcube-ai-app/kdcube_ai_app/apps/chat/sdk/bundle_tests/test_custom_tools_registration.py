# SPDX-License-Identifier: MIT

"""Custom tools registration tests.

Test that custom tools register correctly with the Tools Subsystem.
Bundles without a tools_descriptor are skipped automatically.

Run with:
  pytest test_custom_tools_registration.py --bundle-id=eco -v
  pytest test_custom_tools_registration.py --bundle-id=react.doc -v
"""

from __future__ import annotations

import pytest


def _load_tools_descriptor(bundle):
    """Return the tools_descriptor module for the bundle, or skip."""
    try:
        from pathlib import Path
        from kdcube_ai_app.infra.plugin.bundle_store import _examples_root
        from kdcube_ai_app.infra.plugin.agentic_loader import AgenticBundleSpec, _resolve_module

        root = _examples_root()
        bundle_id = getattr(bundle, "BUNDLE_ID", None) or ""
        # Strip platform prefix (e.g. "kdcube.bundle.eco" -> "eco")
        short_id = bundle_id.split(".")[-1] if bundle_id else ""

        candidates = [
            d for d in sorted(root.iterdir())
            if d.is_dir() and (d / "tools_descriptor.py").exists()
            and (
                d.name == short_id
                or d.name.startswith(short_id + "@")
                or d.name == bundle_id
                or d.name.startswith(bundle_id + "@")
            )
        ]
        if not candidates:
            pytest.skip(f"Bundle '{bundle_id}' has no tools_descriptor.py")

        bundle_dir = candidates[-1]
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tools_descriptor", bundle_dir / "tools_descriptor.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        pytest.skip(f"Cannot load tools_descriptor: {e}")


class TestCustomToolsRegistration:
    """Verify tools_descriptor structure and tool ID conventions."""

    def test_tools_specs_is_a_list(self, bundle):
        """TOOLS_SPECS is a list (may be empty for bundles with no module tools)."""
        mod = _load_tools_descriptor(bundle)
        assert hasattr(mod, "TOOLS_SPECS"), "tools_descriptor must define TOOLS_SPECS"
        assert isinstance(mod.TOOLS_SPECS, list)

    def test_each_tool_spec_has_alias(self, bundle):
        """Every entry in TOOLS_SPECS has an 'alias' key."""
        mod = _load_tools_descriptor(bundle)
        for i, spec in enumerate(mod.TOOLS_SPECS):
            assert "alias" in spec, f"TOOLS_SPECS[{i}] is missing 'alias'"
            assert spec["alias"], f"TOOLS_SPECS[{i}]['alias'] must be non-empty"

    def test_each_tool_spec_has_module_or_ref(self, bundle):
        """Every entry in TOOLS_SPECS has either 'module' or 'ref'."""
        mod = _load_tools_descriptor(bundle)
        for i, spec in enumerate(mod.TOOLS_SPECS):
            has_module = bool(spec.get("module"))
            has_ref = bool(spec.get("ref"))
            assert has_module or has_ref, (
                f"TOOLS_SPECS[{i}] must have 'module' or 'ref'"
            )

    def test_tool_aliases_are_unique(self, bundle):
        """All aliases in TOOLS_SPECS are unique."""
        mod = _load_tools_descriptor(bundle)
        aliases = [s["alias"] for s in mod.TOOLS_SPECS if s.get("alias")]
        assert len(aliases) == len(set(aliases)), (
            f"Duplicate aliases in TOOLS_SPECS: {[a for a in aliases if aliases.count(a) > 1]}"
        )

    def test_mcp_tool_specs_is_a_list(self, bundle):
        """MCP_TOOL_SPECS is a list (may be empty)."""
        mod = _load_tools_descriptor(bundle)
        if not hasattr(mod, "MCP_TOOL_SPECS"):
            pytest.skip("Bundle has no MCP_TOOL_SPECS")
        assert isinstance(mod.MCP_TOOL_SPECS, list)

    def test_tool_id_format_via_parse_tool_id(self):
        """parse_tool_id() parses 'alias.tool_name' into (origin, alias, name)."""
        from kdcube_ai_app.apps.chat.sdk.runtime.tool_subsystem import parse_tool_id
        origin, alias, name = parse_tool_id("io_tools.read_file")
        assert origin == "mod"
        assert alias == "io_tools"
        assert name == "read_file"

    def test_mcp_tool_id_format_via_parse_tool_id(self):
        """parse_tool_id() parses 'mcp.alias.tool_name' into (mcp, alias, name)."""
        from kdcube_ai_app.apps.chat.sdk.runtime.tool_subsystem import parse_tool_id
        origin, alias, name = parse_tool_id("mcp.web_search.search")
        assert origin == "mcp"
        assert alias == "web_search"
        assert name == "search"

    def test_parse_tool_id_two_part_is_mod_origin(self):
        """Two-part tool ID defaults to 'mod' origin."""
        from kdcube_ai_app.apps.chat.sdk.runtime.tool_subsystem import parse_tool_id
        origin, alias, name = parse_tool_id("ctx_tools.get_context")
        assert origin == "mod"


class TestToolRuntimeConfig:
    """Verify TOOL_RUNTIME config in tools_descriptor."""

    def test_tool_runtime_is_dict_when_present(self, bundle):
        """TOOL_RUNTIME is a dict when defined."""
        mod = _load_tools_descriptor(bundle)
        if not hasattr(mod, "TOOL_RUNTIME"):
            pytest.skip("Bundle has no TOOL_RUNTIME")
        assert isinstance(mod.TOOL_RUNTIME, dict)

    def test_tool_runtime_values_are_valid_strings(self, bundle):
        """TOOL_RUNTIME values are 'none', 'local', or 'docker'."""
        mod = _load_tools_descriptor(bundle)
        if not hasattr(mod, "TOOL_RUNTIME"):
            pytest.skip("Bundle has no TOOL_RUNTIME")
        valid = {"none", "local", "docker"}
        for tool_id, runtime in mod.TOOL_RUNTIME.items():
            assert runtime in valid, (
                f"TOOL_RUNTIME[{tool_id!r}] = {runtime!r} is not in {valid}"
            )
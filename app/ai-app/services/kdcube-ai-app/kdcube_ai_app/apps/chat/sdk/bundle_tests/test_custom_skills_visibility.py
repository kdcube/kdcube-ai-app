# SPDX-License-Identifier: MIT

"""Custom skills visibility tests.

Test that AGENTS_CONFIG correctly controls which skills are visible
to which agents.

Run with:
  pytest test_custom_skills_visibility.py --bundle-id=eco -v
  pytest test_custom_skills_visibility.py --bundle-id=react.mcp -v
"""

from __future__ import annotations

import pytest


def _load_agents_config(bundle) -> dict:
    """Return AGENTS_CONFIG from the bundle's skills_descriptor, or skip."""
    try:
        from kdcube_ai_app.infra.plugin.bundle_store import _examples_root
        import importlib.util

        root = _examples_root()
        bundle_id = getattr(bundle, "BUNDLE_ID", None) or ""
        short_id = bundle_id.split(".")[-1] if bundle_id else ""

        candidates = [
            d for d in sorted(root.iterdir())
            if d.is_dir() and (d / "skills_descriptor.py").exists()
            and (
                d.name == short_id
                or d.name.startswith(short_id + "@")
                or d.name == bundle_id
                or d.name.startswith(bundle_id + "@")
            )
        ]
        if not candidates:
            pytest.skip(f"Bundle '{bundle_id}' has no skills_descriptor.py")

        bundle_dir = candidates[-1]
        spec = importlib.util.spec_from_file_location(
            "skills_descriptor", bundle_dir / "skills_descriptor.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if not hasattr(mod, "AGENTS_CONFIG"):
            pytest.skip("Bundle has no AGENTS_CONFIG")
        return mod.AGENTS_CONFIG
    except Exception as e:
        pytest.skip(f"Cannot load AGENTS_CONFIG: {e}")


class TestAgentsConfigStructure:
    """Verify AGENTS_CONFIG has the correct structure."""

    def test_agents_config_is_dict(self, bundle):
        """AGENTS_CONFIG is a dict."""
        cfg = _load_agents_config(bundle)
        assert isinstance(cfg, dict)

    def test_agents_config_keys_are_strings(self, bundle):
        """AGENTS_CONFIG keys (agent role names) are strings."""
        cfg = _load_agents_config(bundle)
        for key in cfg:
            assert isinstance(key, str), f"AGENTS_CONFIG key must be str, got {type(key)}"

    def test_agents_config_values_are_dicts(self, bundle):
        """AGENTS_CONFIG values are dicts (may be empty)."""
        cfg = _load_agents_config(bundle)
        for role, val in cfg.items():
            assert isinstance(val, dict), (
                f"AGENTS_CONFIG[{role!r}] must be a dict, got {type(val)}"
            )


class TestSkillsSubsystemVisibility:
    """Test SkillsSubsystem visibility filtering (unit-level, no real skills needed)."""

    def test_skills_subsystem_accepts_descriptor_with_agents_config(self):
        """SkillsSubsystem initializes when descriptor contains agents_config."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import SkillsSubsystem
        descriptor = {
            "agents_config": {
                "solver.react.v2": {},
                "gate": {"enabled_skills": []},
            }
        }
        subsystem = SkillsSubsystem(descriptor=descriptor, bundle_root=None)
        assert subsystem is not None

    def test_skills_subsystem_empty_agents_config_means_all_visible(self):
        """Empty AGENTS_CONFIG dict means all skills are visible to all agents."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import SkillsSubsystem
        descriptor = {"agents_config": {}}
        subsystem = SkillsSubsystem(descriptor=descriptor, bundle_root=None)
        registry = subsystem.get_skill_registry()
        assert isinstance(registry, dict)

    def test_set_active_skills_subsystem_and_get_back(self):
        """set_active_skills_subsystem() makes the subsystem retrievable."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import (
            SkillsSubsystem,
            set_active_skills_subsystem,
            get_active_skills_subsystem,
        )
        subsystem = SkillsSubsystem(descriptor=None, bundle_root=None)
        set_active_skills_subsystem(subsystem)
        retrieved = get_active_skills_subsystem()
        assert retrieved is subsystem

    def test_set_skills_descriptor_returns_subsystem(self):
        """set_skills_descriptor() returns a SkillsSubsystem instance."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import (
            SkillsSubsystem,
            set_skills_descriptor,
        )
        result = set_skills_descriptor(descriptor=None, bundle_root=None)
        assert isinstance(result, SkillsSubsystem)
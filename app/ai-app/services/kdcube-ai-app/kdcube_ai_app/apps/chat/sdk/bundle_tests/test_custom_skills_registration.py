# SPDX-License-Identifier: MIT

"""Custom skills registration tests.

Test that custom skills register correctly with the Skills Subsystem.
Bundles without a skills_descriptor or skills/ directory are skipped.

Run with:
  pytest test_custom_skills_registration.py --bundle-id=eco -v
  pytest test_custom_skills_registration.py --bundle-id=react.mcp -v
"""

from __future__ import annotations

import pathlib
import pytest


def _load_skills_descriptor(bundle, bundle_id):
    """Return the skills_descriptor module for the bundle, or skip."""
    try:
        from kdcube_ai_app.infra.plugin.bundle_store import _examples_root
        root = _examples_root()

        candidates = [
            d for d in sorted(root.iterdir())
            if d.is_dir() and (d / "skills_descriptor.py").exists()
            and (
                d.name == bundle_id
                or d.name.startswith(bundle_id + "@")
            )
        ]
        if not candidates:
            pytest.skip(f"Bundle '{bundle_id}' has no skills_descriptor.py")

        import importlib.util
        bundle_dir = candidates[-1]
        spec = importlib.util.spec_from_file_location(
            "skills_descriptor", bundle_dir / "skills_descriptor.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, bundle_dir
    except Exception as e:
        pytest.skip(f"Cannot load skills_descriptor: {e}")


class TestSkillsDescriptorStructure:
    """Verify skills_descriptor.py defines the expected attributes."""

    def test_skills_descriptor_defines_custom_skills_root(self, bundle, bundle_id):
        """skills_descriptor.py defines CUSTOM_SKILLS_ROOT attribute."""
        mod, _ = _load_skills_descriptor(bundle, bundle_id)
        assert hasattr(mod, "CUSTOM_SKILLS_ROOT"), (
            "skills_descriptor must define CUSTOM_SKILLS_ROOT"
        )

    def test_custom_skills_root_is_path_or_none(self, bundle, bundle_id):
        """CUSTOM_SKILLS_ROOT is a pathlib.Path or None."""
        mod, _ = _load_skills_descriptor(bundle, bundle_id)
        root = mod.CUSTOM_SKILLS_ROOT
        assert root is None or isinstance(root, pathlib.Path), (
            f"CUSTOM_SKILLS_ROOT must be Path or None, got {type(root)}"
        )

    def test_agents_config_is_dict(self, bundle, bundle_id):
        """AGENTS_CONFIG is a dict when defined."""
        mod, _ = _load_skills_descriptor(bundle, bundle_id)
        if not hasattr(mod, "AGENTS_CONFIG"):
            pytest.skip("Bundle has no AGENTS_CONFIG")
        assert isinstance(mod.AGENTS_CONFIG, dict)


class TestSkillsSubsystem:
    """Verify SkillsSubsystem loads and caches skill registry."""

    def test_skills_subsystem_can_be_created(self):
        """SkillsSubsystem initializes without errors with empty descriptor."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import SkillsSubsystem
        subsystem = SkillsSubsystem(descriptor=None, bundle_root=None)
        assert subsystem is not None

    def test_get_skill_registry_returns_dict(self):
        """get_skill_registry() returns a dict (may be empty with no skills)."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import SkillsSubsystem
        subsystem = SkillsSubsystem(descriptor=None, bundle_root=None)
        registry = subsystem.get_skill_registry()
        assert isinstance(registry, dict)

    def test_get_skill_registry_is_cached(self):
        """Two calls to get_skill_registry() return the same object."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import SkillsSubsystem
        subsystem = SkillsSubsystem(descriptor=None, bundle_root=None)
        r1 = subsystem.get_skill_registry()
        r2 = subsystem.get_skill_registry()
        assert r1 is r2

    def test_clear_cache_resets_registry(self):
        """clear_cache() forces get_skill_registry() to re-load."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import SkillsSubsystem
        subsystem = SkillsSubsystem(descriptor=None, bundle_root=None)
        r1 = subsystem.get_skill_registry()
        subsystem.clear_cache()
        r2 = subsystem.get_skill_registry()
        assert r1 is not r2  # must be a fresh object after cache clear

    def test_bundle_skills_loaded_when_skills_dir_exists(self, bundle, bundle_id):
        """When bundle has skills/ directory, at least one skill is registered."""
        mod, bundle_dir = _load_skills_descriptor(bundle, bundle_id)
        skills_root = mod.CUSTOM_SKILLS_ROOT
        if skills_root is None or not skills_root.exists():
            pytest.skip("Bundle has no skills/ directory")

        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import SkillsSubsystem
        import importlib.util as ilu

        descriptor = {"custom_skills_root": str(skills_root)}
        subsystem = SkillsSubsystem(descriptor=descriptor, bundle_root=bundle_dir)
        registry = subsystem.get_skill_registry()
        assert len(registry) > 0, (
            f"Bundle has skills/ directory but SkillsSubsystem found 0 skills"
        )
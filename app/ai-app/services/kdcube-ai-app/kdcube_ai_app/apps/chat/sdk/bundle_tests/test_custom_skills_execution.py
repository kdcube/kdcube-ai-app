# SPDX-License-Identifier: MIT

"""Custom skills execution tests.

Test that skill instructions are loaded correctly and that the get_skill()
helper resolves skills by ID.

Run with:
  pytest test_custom_skills_execution.py --bundle-id=eco -v
  pytest test_custom_skills_execution.py --bundle-id=react.mcp -v
"""

from __future__ import annotations

import pathlib
import pytest


def _skill_dirs_for_bundle(bundle, bundle_id) -> list[tuple[pathlib.Path, str]]:
    """Return [(skill_dir, qualified_id), ...] for the bundle."""
    try:
        from kdcube_ai_app.infra.plugin.bundle_store import _examples_root
        root = _examples_root()

        candidates = [
            d for d in sorted(root.iterdir())
            if d.is_dir()
            and (
                d.name == bundle_id
                or d.name.startswith(bundle_id + "@")
            )
        ]
        if not candidates:
            pytest.skip(f"Bundle '{bundle_id}' not found")

        bundle_dir = candidates[-1]
        skills_root = bundle_dir / "skills"
        if not skills_root.exists():
            pytest.skip(f"Bundle '{bundle_id}' has no skills/ directory")

        result = []
        for ns_dir in skills_root.iterdir():
            if not ns_dir.is_dir():
                continue
            for skill_dir in ns_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    qualified_id = f"{ns_dir.name}.{skill_dir.name}"
                    result.append((skill_dir, qualified_id))

        if not result:
            pytest.skip(f"Bundle '{bundle_id}' skills/ has no SKILL.md files")
        return result
    except Exception as e:
        pytest.skip(f"Cannot discover skills: {e}")


def _load_skill_spec_from_dir(skill_dir: pathlib.Path):
    """Load a SkillSpec directly from a skill directory."""
    from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import (
        SkillsSubsystem,
    )
    import importlib.util
    subsystem = SkillsSubsystem(
        descriptor={"custom_skills_root": str(skill_dir.parent.parent)},
        bundle_root=skill_dir.parent.parent.parent,
    )
    return subsystem.get_skill_registry()


class TestSkillInstructionLoading:
    """Verify that skill instructions are loaded from SKILL.md."""

    def test_skill_md_body_is_non_empty_instruction(self, bundle, bundle_id):
        """SKILL.md body (after frontmatter) is non-empty instruction text."""
        for skill_dir, _ in _skill_dirs_for_bundle(bundle, bundle_id):
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            end = text.find("---", 3)
            body = text[end + 3:].strip() if end != -1 else text.strip()
            assert body, (
                f"{skill_dir.name}/SKILL.md must have non-empty instruction body"
            )

    def test_skill_body_contains_useful_content(self, bundle, bundle_id):
        """SKILL.md body is at least 20 characters (not just placeholder)."""
        for skill_dir, _ in _skill_dirs_for_bundle(bundle, bundle_id):
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            end = text.find("---", 3)
            body = text[end + 3:].strip() if end != -1 else text.strip()
            assert len(body) >= 20, (
                f"{skill_dir.name}/SKILL.md body too short ({len(body)} chars)"
            )


class TestGetSkillHelper:
    """Test the get_skill() module-level helper."""

    def test_get_skill_returns_none_for_unknown_id(self):
        """get_skill() returns None for an unknown skill ID."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import (
            get_skill,
            set_skills_descriptor,
        )
        set_skills_descriptor(descriptor=None, bundle_root=None)
        result = get_skill("nonexistent.unknown_skill_xyz")
        assert result is None

    def test_get_skill_returns_none_for_empty_id(self):
        """get_skill('') returns None without raising."""
        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import (
            get_skill,
            set_skills_descriptor,
        )
        set_skills_descriptor(descriptor=None, bundle_root=None)
        result = get_skill("")
        assert result is None

    def test_get_skill_resolves_registered_skill(self, bundle, bundle_id):
        """get_skill() returns a SkillSpec for a skill that exists in the bundle."""
        dirs = _skill_dirs_for_bundle(bundle, bundle_id)
        if not dirs:
            pytest.skip("No skills found")

        skill_dir, qualified_id = dirs[0]

        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import (
            SkillsSubsystem,
            set_active_skills_subsystem,
            get_skill,
        )
        # Point subsystem at bundle's skills root (parent of namespace dir)
        skills_root = skill_dir.parent.parent
        subsystem = SkillsSubsystem(
            descriptor={"custom_skills_root": str(skills_root)},
            bundle_root=skills_root.parent,
        )
        set_active_skills_subsystem(subsystem)

        result = get_skill(qualified_id)
        assert result is not None, (
            f"get_skill({qualified_id!r}) returned None; "
            f"expected a SkillSpec for bundle skill"
        )

    def test_skill_spec_has_id_and_namespace(self, bundle, bundle_id):
        """SkillSpec loaded from bundle has non-empty id and namespace."""
        dirs = _skill_dirs_for_bundle(bundle, bundle_id)
        if not dirs:
            pytest.skip("No skills found")

        skill_dir, qualified_id = dirs[0]

        from kdcube_ai_app.apps.chat.sdk.skills.skills_registry import (
            SkillsSubsystem,
            set_active_skills_subsystem,
            get_skill,
        )
        skills_root = skill_dir.parent.parent
        subsystem = SkillsSubsystem(
            descriptor={"custom_skills_root": str(skills_root)},
            bundle_root=skills_root.parent,
        )
        set_active_skills_subsystem(subsystem)

        spec = get_skill(qualified_id)
        if spec is None:
            pytest.skip(f"Skill {qualified_id!r} not found in registry")

        assert spec.id, "SkillSpec.id must be non-empty"
        assert spec.namespace, "SkillSpec.namespace must be non-empty"
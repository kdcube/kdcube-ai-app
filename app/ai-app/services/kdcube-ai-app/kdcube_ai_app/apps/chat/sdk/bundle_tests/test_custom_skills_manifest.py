# SPDX-License-Identifier: MIT

"""Custom skills manifest tests.

Test that SKILL.md files have valid frontmatter, and that tools.yaml /
sources.yaml pass schema validation when present.

Run with:
  pytest test_custom_skills_manifest.py --bundle-id=eco -v
  pytest test_custom_skills_manifest.py --bundle-id=react.mcp -v
"""

from __future__ import annotations

import pathlib
import pytest


def _skill_dirs(bundle, bundle_id) -> list[pathlib.Path]:
    """Return list of skill directories for the bundle, or skip."""
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

        dirs = [d for d in skills_root.iterdir() if d.is_dir()]
        skill_dirs = []
        for ns_dir in dirs:
            for skill_dir in ns_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skill_dirs.append(skill_dir)
        if not skill_dirs:
            pytest.skip(f"Bundle '{bundle_id}' skills/ has no skill subdirectories with SKILL.md")
        return skill_dirs
    except Exception as e:
        pytest.skip(f"Cannot discover skill dirs: {e}")


def _parse_frontmatter(path: pathlib.Path) -> dict:
    """Parse YAML frontmatter from a markdown file."""
    import yaml
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end].strip()
    return yaml.safe_load(fm_text) or {}


class TestSkillMdFrontmatter:
    """Verify SKILL.md files have required frontmatter."""

    def test_skill_md_has_frontmatter(self, bundle, bundle_id):
        """Every SKILL.md has a YAML frontmatter block."""
        for skill_dir in _skill_dirs(bundle, bundle_id):
            skill_md = skill_dir / "SKILL.md"
            text = skill_md.read_text(encoding="utf-8")
            assert text.startswith("---"), (
                f"{skill_md}: SKILL.md must start with '---' frontmatter block"
            )

    def test_skill_md_frontmatter_has_name(self, bundle, bundle_id):
        """SKILL.md frontmatter has a 'name' field."""
        for skill_dir in _skill_dirs(bundle, bundle_id):
            fm = _parse_frontmatter(skill_dir / "SKILL.md")
            assert fm.get("name"), (
                f"{skill_dir.name}/SKILL.md frontmatter missing 'name'"
            )

    def test_skill_md_frontmatter_has_id(self, bundle, bundle_id):
        """SKILL.md frontmatter has an 'id' field."""
        for skill_dir in _skill_dirs(bundle, bundle_id):
            fm = _parse_frontmatter(skill_dir / "SKILL.md")
            assert fm.get("id"), (
                f"{skill_dir.name}/SKILL.md frontmatter missing 'id'"
            )

    def test_skill_md_frontmatter_has_description(self, bundle, bundle_id):
        """SKILL.md frontmatter has a 'description' field."""
        for skill_dir in _skill_dirs(bundle, bundle_id):
            fm = _parse_frontmatter(skill_dir / "SKILL.md")
            assert fm.get("description"), (
                f"{skill_dir.name}/SKILL.md frontmatter missing 'description'"
            )

    def test_skill_md_has_body_content(self, bundle, bundle_id):
        """SKILL.md has content after the frontmatter block."""
        for skill_dir in _skill_dirs(bundle, bundle_id):
            skill_md = skill_dir / "SKILL.md"
            text = skill_md.read_text(encoding="utf-8")
            end = text.find("---", 3)
            body = text[end + 3:].strip() if end != -1 else ""
            assert body, (
                f"{skill_md}: SKILL.md must have content after frontmatter"
            )


class TestToolsYaml:
    """Verify tools.yaml is valid when present."""

    def test_tools_yaml_parses_as_dict_or_list(self, bundle, bundle_id):
        """tools.yaml parses as a list or dict when present."""
        import yaml
        for skill_dir in _skill_dirs(bundle, bundle_id):
            tools_path = skill_dir / "tools.yaml"
            if not tools_path.exists():
                continue
            data = yaml.safe_load(tools_path.read_text(encoding="utf-8"))
            assert isinstance(data, (list, dict, type(None))), (
                f"{tools_path}: tools.yaml must be a list or dict"
            )


class TestSourcesYaml:
    """Verify sources.yaml is valid when present."""

    def test_sources_yaml_parses_as_list(self, bundle, bundle_id):
        """sources.yaml parses as a list or a dict with 'sources' key when present."""
        import yaml
        for skill_dir in _skill_dirs(bundle, bundle_id):
            sources_path = skill_dir / "sources.yaml"
            if not sources_path.exists():
                continue
            data = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
            # sources.yaml can be None, a plain list, or a dict with a 'sources' key
            if isinstance(data, dict):
                assert "sources" in data and isinstance(data["sources"], list), (
                    f"{sources_path}: sources.yaml dict must have a 'sources' list"
                )
            else:
                assert data is None or isinstance(data, list), (
                    f"{sources_path}: sources.yaml must be a list or dict with 'sources'"
                )

    def test_each_source_has_required_fields(self, bundle, bundle_id):
        """Each entry in sources.yaml has at least 'title' or 'url'."""
        import yaml
        for skill_dir in _skill_dirs(bundle, bundle_id):
            sources_path = skill_dir / "sources.yaml"
            if not sources_path.exists():
                continue
            raw = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
            data = raw["sources"] if isinstance(raw, dict) and "sources" in raw else (raw or [])
            for i, src in enumerate(data):
                if not isinstance(src, dict):
                    continue
                has_title = bool(src.get("title"))
                has_url = bool(src.get("url"))
                assert has_title or has_url, (
                    f"{sources_path}[{i}]: source entry must have 'title' or 'url'"
                )
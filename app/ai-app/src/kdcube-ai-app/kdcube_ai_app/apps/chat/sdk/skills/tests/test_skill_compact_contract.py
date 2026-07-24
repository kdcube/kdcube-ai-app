# SPDX-License-Identifier: MIT

"""The compact-form contract for public skills.

The ``skills_form: compact`` presentation facet serves each skill's
``compact.md`` on ``sk:`` loads, so a stale stub silently degrades every
serving-constrained agent. This contract keeps the compact bodies honest:

- every public skill ships a compact.md with real substance (not a stub);
- every tool id the skill declares in ``tools.yaml`` is named in the compact
  body — a compact form that omits a tool teaches an incomplete surface.
"""

from __future__ import annotations

import pathlib
import re

import pytest

SKILLS_ROOT = (
    pathlib.Path(__file__).resolve().parents[1] / "skills" / "public"
)

# A compact body must be a real condensed guide. The shortest maintained one
# (url-gen, a 44-line full guide) sits at ~23 lines; stubs were 3-6.
MIN_COMPACT_LINES = 15

_TOOL_ID_RE = re.compile(r"^\s*-\s*id:\s*([A-Za-z0-9_.\-]+)", re.MULTILINE)


def _public_skills() -> list[pathlib.Path]:
    return sorted(p for p in SKILLS_ROOT.iterdir() if (p / "SKILL.md").exists())


def test_public_skills_exist():
    assert _public_skills(), f"no public skills under {SKILLS_ROOT}"


@pytest.mark.parametrize("skill_dir", _public_skills(), ids=lambda p: p.name)
def test_compact_form_has_substance(skill_dir: pathlib.Path):
    compact_path = skill_dir / "compact.md"
    assert compact_path.exists(), f"{skill_dir.name}: compact.md missing"
    text = compact_path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) >= MIN_COMPACT_LINES, (
        f"{skill_dir.name}: compact.md has {len(lines)} non-empty lines "
        f"(< {MIN_COMPACT_LINES}) — a stub, not a condensed guide"
    )


@pytest.mark.parametrize("skill_dir", _public_skills(), ids=lambda p: p.name)
def test_compact_form_names_every_declared_tool(skill_dir: pathlib.Path):
    tools_path = skill_dir / "tools.yaml"
    if not tools_path.exists():
        pytest.skip("skill declares no tools")
    tool_ids = _TOOL_ID_RE.findall(tools_path.read_text(encoding="utf-8"))
    if not tool_ids:
        pytest.skip("tools.yaml declares no tool ids")
    compact = (skill_dir / "compact.md").read_text(encoding="utf-8")
    missing = [tool_id for tool_id in tool_ids if tool_id not in compact]
    assert not missing, (
        f"{skill_dir.name}: compact.md omits declared tool ids {missing}"
    )

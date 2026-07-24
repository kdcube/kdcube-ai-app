# SPDX-License-Identifier: MIT

"""The built-in block catalog: every block distinguishable by its MEANING —
curated signals, semantic tags, profile memberships, full text for details."""

from kdcube_ai_app.apps.chat.sdk.skills.instructions.shared_instructions_lite import (
    REACT_LITE_PROFILE_BLOCKS,
)
from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions import (
    builtin_block_catalog,
)


def test_catalog_covers_both_tiers_with_meaning():
    catalog = builtin_block_catalog()
    by_name = {entry["name"]: entry for entry in catalog}
    # every moderate block of every profile is present
    for blocks in REACT_LITE_PROFILE_BLOCKS.values():
        for name in blocks:
            assert name in by_name
    # both tiers present
    tiers = {entry["tier"] for entry in catalog}
    assert tiers == {"moderate", "extra-lite"}
    # every entry carries its MEANING: signals, semantic tags, and text
    for entry in catalog:
        assert entry["signals"], f"{entry['name']}: no curated signals"
        assert entry["description"], entry["name"]
        assert entry["tags"], f"{entry['name']}: no semantic tags"
        # tags reflect meaning, not mechanics — tier lives in its own field
        assert entry["tier"] not in entry["tags"]
        assert entry["text"], entry["name"]
        # every block carries its token weight for the constructor
        assert isinstance(entry["tokens"], int) and entry["tokens"] > 0, entry["name"]
    # profile membership is its own facet, not a tag
    skills = by_name["REACT_LITE_SKILLS"]
    assert "all_capabilities" in skills["profiles"]
    assert "core" in skills["profiles"]
    assert "all_capabilities" not in skills["tags"]
    # curated meaning example
    web = by_name["REACT_LITE_WEB_TOOLS"]
    assert web["tags"] == ["web", "search", "fetch"]
    assert any("external information" in s for s in web["signals"])

# SPDX-License-Identifier: MIT

"""The built-in block catalog: every block distinguishable by description+tags."""

from kdcube_ai_app.apps.chat.sdk.skills.instructions.shared_instructions_lite import (
    REACT_LITE_PROFILE_BLOCKS,
)
from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions import (
    builtin_block_catalog,
)


def test_catalog_covers_both_tiers_with_descriptions_and_tags():
    catalog = builtin_block_catalog()
    by_name = {entry["name"]: entry for entry in catalog}
    # every moderate block of every profile is present
    for blocks in REACT_LITE_PROFILE_BLOCKS.values():
        for name in blocks:
            assert name in by_name
    # both tiers present
    tiers = {entry["tier"] for entry in catalog}
    assert tiers == {"moderate", "extra-lite"}
    # each entry is DISTINGUISHABLE: non-empty description + tier tag
    for entry in catalog:
        assert entry["description"], entry["name"]
        assert entry["tier"] in entry["tags"]
    # moderate blocks carry their profile memberships as tags
    skills = by_name["REACT_LITE_SKILLS"]
    assert "all_capabilities" in skills["tags"]
    assert "core" in skills["tags"]

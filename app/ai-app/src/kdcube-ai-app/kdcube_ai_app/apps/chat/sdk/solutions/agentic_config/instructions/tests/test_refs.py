# SPDX-License-Identifier: MIT

"""The ``instr:`` ref grammar: parsing, formatting, validation."""

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.refs import (
    CustomInstructionRef,
    find_custom_refs,
    format_custom_ref,
    is_valid_instruction_id,
    parse_custom_ref,
    resolve_profile_alias,
)


def test_profile_aliases_resolve_and_unknown_is_none():
    assert resolve_profile_alias("instr:profile:full") == "full"
    assert resolve_profile_alias("instr:profile:lite") == "lite:all_capabilities"
    assert resolve_profile_alias("instr:profile:extra-lite") == "xlite:workspace_exec"
    assert resolve_profile_alias("INSTR:PROFILE:LITE") == "lite:all_capabilities"
    assert resolve_profile_alias("instr:profile:nope") is None
    assert resolve_profile_alias("lite:all_capabilities") is None  # not an instr ref


def test_custom_ref_parse_and_roundtrip():
    ref = parse_custom_ref("instr:custom:support-tone:3")
    assert ref == CustomInstructionRef(instruction_id="support-tone", version=3)
    assert ref.token() == "instr:custom:support-tone:3"
    unpinned = parse_custom_ref("instr:custom:support-tone")
    assert unpinned == CustomInstructionRef(instruction_id="support-tone", version=None)
    assert unpinned.token() == "instr:custom:support-tone"
    assert format_custom_ref("a-b", 7) == "instr:custom:a-b:7"


def test_malformed_custom_refs_are_none():
    assert parse_custom_ref("instr:custom:") is None
    assert parse_custom_ref("instr:custom:Bad_Slug") is None
    assert parse_custom_ref("instr:custom:-lead-dash") is None
    assert parse_custom_ref("instr:custom:ok:0") is None       # versions start at 1
    assert parse_custom_ref("instr:custom:ok:v2") is None
    assert parse_custom_ref("lite:all_capabilities") is None   # not a custom ref


def test_instruction_id_validation():
    assert is_valid_instruction_id("support-tone")
    assert is_valid_instruction_id("a1")
    assert not is_valid_instruction_id("")
    assert not is_valid_instruction_id("Upper")
    assert not is_valid_instruction_id("under_score")
    assert not is_valid_instruction_id("-lead")
    assert not is_valid_instruction_id("x" * 65)


def test_find_custom_refs_scans_in_order_keeping_duplicates():
    refs = find_custom_refs(
        [
            "REACT_LITE_SKILLS",
            "instr:custom:a:1",
            "instr:profile:lite",
            "instr:custom:b",
            "instr:custom:a:1",
            "instr:custom:BAD SLUG",  # malformed -> skipped
        ]
    )
    assert [r.token() for r in refs] == [
        "instr:custom:a:1",
        "instr:custom:b",
        "instr:custom:a:1",
    ]

# SPDX-License-Identifier: MIT

from kdcube_ai_app.apps.chat.sdk.solutions.react.artifacts import (
    build_logical_artifact_path,
    build_physical_artifact_path,
    normalize_physical_path,
    physical_path_to_logical_path,
    split_logical_artifact_ref,
    split_logical_artifact_path,
    split_physical_artifact_ref,
)


def test_normalize_physical_path_accepts_generic_fi_for_outdir_tools():
    physical, rel, rewritten = normalize_physical_path(
        "conv:fi:logs/docker.err.log",
        turn_id="turn_cur",
        allow_generic_fi=True,
    )

    assert physical == "logs/docker.err.log"
    assert rel == "logs/docker.err.log"
    assert rewritten is False


def test_physical_path_to_logical_path_supports_generic_outdir_paths():
    assert physical_path_to_logical_path("logs/docker.err.log") == "conv:fi:logs/docker.err.log"
    assert physical_path_to_logical_path("turn_prev/git/projects/repo/README.md") == "conv:fi:turn_prev.git/projects/repo/README.md"
    assert physical_path_to_logical_path("turn_prev/files/report.md") == "conv:fi:turn_prev.files/report.md"
    assert physical_path_to_logical_path("turn_prev/git/snapshots/wizard-state.yaml") == "conv:fi:turn_prev.git/snapshots/wizard-state.yaml"
    assert (
        physical_path_to_logical_path("turn_2026-05-19-01-01-49-177/files/report.md")
        == "conv:fi:turn_2026-05-19-01-01-49-177.files/report.md"
    )
    assert physical_path_to_logical_path("turn_prev.files/report.md") == "conv:fi:turn_prev.files/report.md"
    assert (
        physical_path_to_logical_path("turn_prev/external/followup/attachments/mabc123/brief.txt")
        == "conv:fi:turn_prev.external.followup.attachments/mabc123/brief.txt"
    )


def test_cross_conversation_fi_paths_round_trip_with_conv_segment():
    logical = build_logical_artifact_path(
        turn_id="turn_prev",
        namespace="git/snapshots",
        relpath="wizard/current.yaml",
        conversation_id="conv_2",
    )
    physical = build_physical_artifact_path(
        turn_id="turn_prev",
        namespace="git/snapshots",
        relpath="wizard/current.yaml",
        conversation_id="conv_2",
    )

    assert logical == "conv:fi:conv_conv_2.turn_prev.git/snapshots/wizard/current.yaml"
    assert physical == "conv_conv_2/turn_prev/git/snapshots/wizard/current.yaml"
    assert split_logical_artifact_ref(logical) == (
        "conv_2",
        "turn_prev",
        "git/snapshots",
        "wizard/current.yaml",
    )
    assert split_physical_artifact_ref(physical) == (
        "conv_2",
        "turn_prev",
        "git/snapshots",
        "wizard/current.yaml",
    )
    assert physical_path_to_logical_path(physical) == logical


def test_cross_conversation_fi_paths_round_trip_all_artifact_namespaces():
    cases = [
        ("git/projects", "workspace/spec.md", "conv:fi:conv_c2.turn_prev.git/projects/workspace/spec.md", "conv_c2/turn_prev/git/projects/workspace/spec.md"),
        ("files", "report.pdf", "conv:fi:conv_c2.turn_prev.files/report.pdf", "conv_c2/turn_prev/files/report.pdf"),
        ("git/snapshots", "wizard/current.yaml", "conv:fi:conv_c2.turn_prev.git/snapshots/wizard/current.yaml", "conv_c2/turn_prev/git/snapshots/wizard/current.yaml"),
        ("attachments", "evidence.png", "conv:fi:conv_c2.turn_prev.user.attachments/evidence.png", "conv_c2/turn_prev/attachments/evidence.png"),
        (
            "attachments",
            "external/followup/attachments/msg_1/evidence.png",
            "conv:fi:conv_c2.turn_prev.external.followup.attachments/msg_1/evidence.png",
            "conv_c2/turn_prev/external/followup/attachments/msg_1/evidence.png",
        ),
    ]

    for namespace, relpath, logical_expected, physical_expected in cases:
        logical = build_logical_artifact_path(
            turn_id="turn_prev",
            namespace=namespace,
            relpath=relpath,
            conversation_id="c2",
        )
        physical = build_physical_artifact_path(
            turn_id="turn_prev",
            namespace=namespace,
            relpath=relpath,
            conversation_id="c2",
        )

        assert logical == logical_expected
        assert physical == physical_expected
        assert split_logical_artifact_ref(logical) == ("c2", "turn_prev", namespace, relpath)
        assert split_physical_artifact_ref(physical) == ("c2", "turn_prev", namespace, relpath)
        assert physical_path_to_logical_path(physical) == logical


def test_normalize_physical_path_preserves_cross_conversation_scope():
    physical, rel, rewritten = normalize_physical_path(
        "conv:fi:conv_c2.turn_prev.git/snapshots/wizard/current.yaml",
        turn_id="turn_current",
    )

    assert physical == "conv_c2/turn_prev/git/snapshots/wizard/current.yaml"
    assert rel == "wizard/current.yaml"
    assert rewritten is True


def test_old_bare_fi_refs_are_not_canonical_artifact_refs():
    assert split_logical_artifact_path("fi:turn_prev.files/report.md") == ("", "", "")
    assert split_logical_artifact_ref("fi:turn_prev.files/report.md") == ("", "", "", "")


def test_normalize_physical_path_rewrites_relative_project_namespace_to_current_turn():
    physical, rel, rewritten = normalize_physical_path(
        "git/projects/demo_proj/README.md",
        turn_id="turn_cur",
    )

    assert physical == "turn_cur/git/projects/demo_proj/README.md"
    assert rel == "demo_proj/README.md"
    assert rewritten is True


def test_normalize_physical_path_rewrites_relative_files_namespace_to_current_turn():
    physical, rel, rewritten = normalize_physical_path(
        "files/demo_proj/test_results.txt",
        turn_id="turn_cur",
    )

    assert physical == "turn_cur/files/demo_proj/test_results.txt"
    assert rel == "demo_proj/test_results.txt"
    assert rewritten is True


def test_normalize_physical_path_rewrites_relative_snapshots_namespace_to_current_turn():
    physical, rel, rewritten = normalize_physical_path(
        "git/snapshots/wizard/current.yaml",
        turn_id="turn_cur",
    )

    assert physical == "turn_cur/git/snapshots/wizard/current.yaml"
    assert rel == "wizard/current.yaml"
    assert rewritten is True

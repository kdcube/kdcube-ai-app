# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""`pull_refs_into_dir` — the framework-neutral core of a "pull" tool.

Refs resolve through the registered namespace byte resolver
(`react/events/resolver.read_event_ref_bytes`) and land as plain local files
under the destination directory (e.g. an exec workspace). Offline: the
resolver is faked; no store."""
from __future__ import annotations

import asyncio

import kdcube_ai_app.apps.chat.sdk.solutions.react.events.resolver as resolver
from kdcube_ai_app.apps.chat.sdk.runtime.workspace import pull_refs_into_dir


def _fake_resolver(payload: dict):
    async def read_event_ref_bytes(*, ref, tenant, project, user_id, storage_path=None, conversation_id=""):
        if ref not in payload:
            raise FileNotFoundError(f"conv:fi: artifact bytes not found for {ref}")
        body, relpath = payload[ref]
        return body, {"relpath": relpath, "turn_id": "turn_1", "namespace": "files"}
    return read_event_ref_bytes


def test_pull_writes_each_ref_under_its_own_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver, "read_event_ref_bytes", _fake_resolver({
        "conv:fi:conv_c.turn_1.files/report.xlsx": (b"XLSX", "report.xlsx"),
        "conv:fi:conv_c.turn_1.user.attachments/notes.docx": (b"DOCX", "notes.docx"),
    }))

    reports = asyncio.run(pull_refs_into_dir(
        refs=[
            "conv:fi:conv_c.turn_1.files/report.xlsx",
            "conv:fi:conv_c.turn_1.user.attachments/notes.docx",
        ],
        dest_dir=tmp_path, tenant="t", project="p", user_id="u",
    ))

    assert [r["ok"] for r in reports] == [True, True]
    assert (tmp_path / "report.xlsx").read_bytes() == b"XLSX"
    assert (tmp_path / "notes.docx").read_bytes() == b"DOCX"
    assert reports[0]["size"] == 4
    assert reports[1]["mime"].startswith("application/")


def test_a_failing_ref_reports_and_never_aborts_the_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver, "read_event_ref_bytes", _fake_resolver({
        "conv:fi:conv_c.turn_1.files/good.txt": (b"ok", "good.txt"),
    }))

    reports = asyncio.run(pull_refs_into_dir(
        refs=["conv:fi:conv_c.turn_1.files/missing.txt", "conv:fi:conv_c.turn_1.files/good.txt"],
        dest_dir=tmp_path, tenant="t", project="p", user_id="u",
    ))

    assert reports[0]["ok"] is False and "not found" in reports[0]["error"]
    assert reports[1]["ok"] is True
    assert (tmp_path / "good.txt").read_bytes() == b"ok"


def test_pulled_filenames_are_sanitized_to_the_ref_tail(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver, "read_event_ref_bytes", _fake_resolver({
        "conv:fi:conv_c.turn_1.files/nested/deep/../report v2.csv": (b"CSV", "nested/deep/../report v2.csv"),
    }))

    reports = asyncio.run(pull_refs_into_dir(
        refs=["conv:fi:conv_c.turn_1.files/nested/deep/../report v2.csv"],
        dest_dir=tmp_path, tenant="t", project="p", user_id="u",
    ))

    assert reports[0]["ok"] is True
    assert reports[0]["filename"] == "report v2.csv"
    assert (tmp_path / "report v2.csv").exists()
    # Nothing escapes the destination directory.
    assert all(p.parent == tmp_path for p in tmp_path.iterdir())

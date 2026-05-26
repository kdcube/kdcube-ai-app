from __future__ import annotations

import zipfile
from io import BytesIO
from types import SimpleNamespace

import pytest

from kdcube_ai_app.apps.chat.sdk.infra.control_plane import storage


def _fake_settings(shared_root):
    return SimpleNamespace(STORAGE_PATH=f"file://{shared_root}")


def test_bundle_storage_list_export_delete(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle-storage"
    managed_root = tmp_path / "managed-bundles"
    shared_root = tmp_path / "shared"
    target_dir = bundle_root / "tenant-a" / "project-a" / "bundle-a" / "data"
    target_dir.mkdir(parents=True)
    (target_dir / "sample.txt").write_text("hello", encoding="utf-8")
    managed_root.mkdir()
    shared_root.mkdir()

    monkeypatch.setattr(storage, "resolve_bundle_storage_root", lambda: bundle_root)
    monkeypatch.setattr(storage, "resolve_managed_bundles_root", lambda: managed_root)
    monkeypatch.setattr(storage, "get_settings", lambda: _fake_settings(shared_root))

    listed = storage.list_storage_path(
        root_id="bundle_storage",
        tenant="tenant-a",
        project="project-a",
        path="bundle-a",
    )
    assert [entry["name"] for entry in listed["entries"]] == ["data"]

    exported, filename = storage.export_storage_paths(
        root_id="bundle_storage",
        tenant="tenant-a",
        project="project-a",
        paths=["bundle-a/data"],
    )
    assert filename.startswith("bundle_storage-export-")
    with zipfile.ZipFile(BytesIO(exported), "r") as archive:
        assert archive.read("bundle-a/data/sample.txt") == b"hello"

    deleted = storage.delete_storage_paths(
        root_id="bundle_storage",
        tenant="tenant-a",
        project="project-a",
        paths=["bundle-a/data"],
        confirm=True,
    )
    assert deleted["deleted_count"] == 1
    assert not target_dir.exists()


def test_storage_root_path_can_be_listed(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle-storage"
    managed_root = tmp_path / "managed-bundles"
    shared_root = tmp_path / "shared"
    (bundle_root / "tenant-a" / "project-a" / "bundle-a").mkdir(parents=True)
    managed_root.mkdir()
    shared_root.mkdir()

    monkeypatch.setattr(storage, "resolve_bundle_storage_root", lambda: bundle_root)
    monkeypatch.setattr(storage, "resolve_managed_bundles_root", lambda: managed_root)
    monkeypatch.setattr(storage, "get_settings", lambda: _fake_settings(shared_root))

    listed = storage.list_storage_path(
        root_id="bundle_storage",
        tenant="tenant-a",
        project="project-a",
        path="",
    )

    assert listed["path"] == ""
    assert [entry["name"] for entry in listed["entries"]] == ["bundle-a"]


def test_shared_storage_falls_back_to_root_when_scope_folder_absent(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle-storage"
    managed_root = tmp_path / "managed-bundles"
    shared_root = tmp_path / "shared"
    bundle_root.mkdir()
    managed_root.mkdir()
    shared_root.mkdir()
    (shared_root / "global.txt").write_text("ok", encoding="utf-8")

    monkeypatch.setattr(storage, "resolve_bundle_storage_root", lambda: bundle_root)
    monkeypatch.setattr(storage, "resolve_managed_bundles_root", lambda: managed_root)
    monkeypatch.setattr(storage, "get_settings", lambda: _fake_settings(shared_root))

    listed = storage.list_storage_path(
        root_id="shared_storage",
        tenant="tenant-a",
        project="project-a",
        path="",
    )

    assert listed["base_path"] == str(shared_root)
    assert [entry["name"] for entry in listed["entries"]] == ["global.txt"]


def test_storage_path_escape_is_rejected(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle-storage"
    managed_root = tmp_path / "managed-bundles"
    shared_root = tmp_path / "shared"
    (bundle_root / "tenant-a" / "project-a").mkdir(parents=True)
    managed_root.mkdir()
    shared_root.mkdir()

    monkeypatch.setattr(storage, "resolve_bundle_storage_root", lambda: bundle_root)
    monkeypatch.setattr(storage, "resolve_managed_bundles_root", lambda: managed_root)
    monkeypatch.setattr(storage, "get_settings", lambda: _fake_settings(shared_root))

    with pytest.raises(storage.StorageAdminError) as exc:
        storage.list_storage_path(
            root_id="bundle_storage",
            tenant="tenant-a",
            project="project-a",
            path="../other",
        )
    assert exc.value.code == "invalid_path"


def test_registry_summary_tracks_active_managed_folders(monkeypatch, tmp_path):
    managed_root = tmp_path / "managed-bundles"
    active_path = managed_root / "repo__bundle__ref" / "src" / "demo"
    active_path.mkdir(parents=True)
    monkeypatch.setattr(storage, "resolve_managed_bundles_root", lambda: managed_root)

    summary = storage.summarize_registry_bundles(
        {
            "demo.bundle": SimpleNamespace(
                name="Demo",
                description="",
                path=str(active_path),
                module="entrypoint",
                singleton=False,
                version=None,
                repo="https://example.invalid/repo.git",
                ref="v1",
                subdir="src/demo",
                git_commit=None,
            )
        },
        default_bundle_id="demo.bundle",
    )

    assert summary["active_managed_folders"] == ["repo__bundle__ref"]
    assert summary["bundles"][0]["managed_folder"] == "repo__bundle__ref"
    assert summary["bundles"][0]["default"] is True

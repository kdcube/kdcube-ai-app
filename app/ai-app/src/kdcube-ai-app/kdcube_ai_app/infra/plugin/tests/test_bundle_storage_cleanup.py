import os
import time
from pathlib import Path

from kdcube_ai_app.infra.plugin.bundle_storage import cleanup_old_bundle_storage


def _mk(path: Path, *, age_seconds: int = 0) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    if age_seconds > 0:
        ts = time.time() - age_seconds
        os.utime(path, (ts, ts))
    return path


def test_cleanup_old_bundle_storage_keeps_active_version(monkeypatch, tmp_path):
    monkeypatch.setenv("BUNDLE_STORAGE_ROOT", str(tmp_path))

    scope = tmp_path / "tenant-a" / "project-a"
    active = _mk(scope / "demo-bundle__new", age_seconds=10)
    stale = _mk(scope / "demo-bundle__old", age_seconds=100)

    removed = cleanup_old_bundle_storage(
        bundle_id="demo-bundle",
        tenant="tenant-a",
        project="project-a",
        keep=0,
        active_paths=[str(active)],
    )

    assert removed == 1
    assert active.exists()
    assert not stale.exists()


def test_cleanup_old_bundle_storage_never_deletes_unversioned_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("BUNDLE_STORAGE_ROOT", str(tmp_path))

    scope = tmp_path / "tenant-a" / "project-a"
    unversioned = _mk(scope / "demo-bundle", age_seconds=100)
    stale = _mk(scope / "demo-bundle__old", age_seconds=100)

    removed = cleanup_old_bundle_storage(
        bundle_id="demo-bundle",
        tenant="tenant-a",
        project="project-a",
        keep=0,
    )

    assert removed == 1
    assert unversioned.exists()
    assert not stale.exists()


def test_cleanup_old_bundle_storage_respects_keep_count(monkeypatch, tmp_path):
    monkeypatch.setenv("BUNDLE_STORAGE_ROOT", str(tmp_path))

    scope = tmp_path / "tenant-a" / "project-a"
    newest = _mk(scope / "demo-bundle__v3", age_seconds=10)
    middle = _mk(scope / "demo-bundle__v2", age_seconds=20)
    oldest = _mk(scope / "demo-bundle__v1", age_seconds=30)

    removed = cleanup_old_bundle_storage(
        bundle_id="demo-bundle",
        tenant="tenant-a",
        project="project-a",
        keep=2,
    )

    assert removed == 1
    assert newest.exists()
    assert middle.exists()
    assert not oldest.exists()

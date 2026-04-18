# SPDX-License-Identifier: MIT

"""Storage integration tests for bundles.

Test multi-storage workflows: local FS AIBundleStorage, bundle_storage_dir,
path scoping, and concurrent access safety.

Run with:
  pytest test_storage_integration.py -v
"""

from __future__ import annotations

import pathlib
import threading
import pytest


def _make_storage(tmp_path, *, tenant="t", project="p", bundle_id="b"):
    from kdcube_ai_app.apps.chat.sdk.storage.ai_bundle_storage import AIBundleStorage
    return AIBundleStorage(
        tenant=tenant, project=project, ai_bundle_id=bundle_id,
        storage_uri=f"file://{tmp_path}",
    )


class TestStorageFallbackChain:
    """Test that storage resolves correctly even under degraded conditions."""

    def test_bundle_storage_root_falls_back_to_default_path(self):
        """resolve_bundle_storage_root() returns a path without requiring env vars."""
        import os
        from kdcube_ai_app.infra.plugin.bundle_storage import resolve_bundle_storage_root
        # Remove env var temporarily to test default path resolution
        old = os.environ.pop("BUNDLE_STORAGE_ROOT", None)
        try:
            root = resolve_bundle_storage_root()
            assert isinstance(root, pathlib.Path)
        finally:
            if old:
                os.environ["BUNDLE_STORAGE_ROOT"] = old

    def test_bundle_storage_root_respects_config(self, tmp_path, monkeypatch):
        """resolve_bundle_storage_root() uses BUNDLE_STORAGE_ROOT from settings when set."""
        from kdcube_ai_app.infra.plugin.bundle_storage import resolve_bundle_storage_root
        from kdcube_ai_app.apps.chat.sdk.config import get_settings
        monkeypatch.setattr(get_settings().PLATFORM.APPLICATIONS, "BUNDLE_STORAGE_ROOT", str(tmp_path))
        root = resolve_bundle_storage_root()
        assert root == tmp_path.resolve()


class TestStorageContextIsolation:
    """Test that storage paths are properly scoped to bundle context."""

    def test_cross_tenant_access_prevented(self, tmp_path):
        """Files written by tenant-a are not visible to tenant-b."""
        sa = _make_storage(tmp_path, tenant="tenant-a")
        sb = _make_storage(tmp_path, tenant="tenant-b")
        sa.write("secret.txt", "private-a")
        assert not sb.exists("secret.txt")

    def test_cross_project_access_prevented(self, tmp_path):
        """Files written in project-a are not visible in project-b."""
        sp = _make_storage(tmp_path, project="proj-a")
        sq = _make_storage(tmp_path, project="proj-b")
        sp.write("data.txt", "proj-a-data")
        assert not sq.exists("data.txt")

    def test_cross_bundle_access_prevented(self, tmp_path):
        """Files written in bundle-x are not visible in bundle-y."""
        sx = _make_storage(tmp_path, bundle_id="bundle-x")
        sy = _make_storage(tmp_path, bundle_id="bundle-y")
        sx.write("file.txt", "from-x")
        assert not sy.exists("file.txt")

    def test_storage_paths_include_all_scope_segments(self, tmp_path):
        """Root URI includes tenant / project / bundle_id all present."""
        s = _make_storage(tmp_path, tenant="acme", project="main", bundle_id="my-bundle")
        uri = s.root_uri
        assert "acme" in uri
        assert "main" in uri
        assert "my-bundle" in uri


class TestConcurrentStorageAccess:
    """Test that concurrent writes to the same storage don't corrupt data."""

    def test_concurrent_writes_to_different_keys(self, tmp_path):
        """Multiple threads can write different keys without data corruption."""
        storage = _make_storage(tmp_path)
        errors = []

        def write_key(i):
            try:
                storage.write(f"file-{i}.txt", f"content-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_key, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent writes raised errors: {errors}"

        # All keys should be readable
        for i in range(10):
            result = storage.read(f"file-{i}.txt", as_text=True)
            assert result == f"content-{i}"

    def test_concurrent_reads_are_consistent(self, tmp_path):
        """Multiple threads reading the same key get consistent data."""
        storage = _make_storage(tmp_path)
        storage.write("shared.txt", "stable-content")
        errors = []
        results = []

        def read_key():
            try:
                results.append(storage.read("shared.txt", as_text=True))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_key) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(r == "stable-content" for r in results)


class TestStorageMultiWorkflow:
    """Test multi-step storage workflows (write → list → read → delete)."""

    def test_full_lifecycle_write_list_read_delete(self, tmp_path):
        """Full lifecycle: write → exists → list → read → delete → not exists."""
        storage = _make_storage(tmp_path)

        # Write
        storage.write("lifecycle.txt", "value")

        # Exists
        assert storage.exists("lifecycle.txt")

        # List
        files = storage.list()
        assert any("lifecycle.txt" in f for f in files)

        # Read
        assert storage.read("lifecycle.txt", as_text=True) == "value"

        # Delete
        storage.delete("lifecycle.txt")

        # Gone
        assert not storage.exists("lifecycle.txt")

    def test_write_multiple_files_list_returns_all(self, tmp_path):
        """Writing N files and listing returns at least N entries."""
        storage = _make_storage(tmp_path)
        n = 5
        for i in range(n):
            storage.write(f"batch-{i}.txt", f"val-{i}")
        files = storage.list()
        found = sum(1 for f in files if any(f"batch-{i}.txt" in f for i in range(n)))
        assert found == n

# SPDX-License-Identifier: MIT

"""Custom tools storage tests.

Test that AIBundleStorage (S3 / local FS) works correctly for tool use.
Uses an in-memory / local-file backend — no real S3 required.

Run with:
  pytest test_custom_tools_storage.py -v
"""

from __future__ import annotations

import tempfile
import pathlib

import pytest


def _make_local_storage(tmp_path: pathlib.Path, *, tenant="t", project="p", bundle_id="test"):
    """Create an AIBundleStorage backed by a local temp directory."""
    from kdcube_ai_app.apps.chat.sdk.storage.ai_bundle_storage import AIBundleStorage
    uri = f"file://{tmp_path}"
    return AIBundleStorage(
        tenant=tenant,
        project=project,
        ai_bundle_id=bundle_id,
        storage_uri=uri,
    )


class TestAIBundleStorageLocalFS:
    """Test AIBundleStorage operations against the local filesystem backend."""

    def test_storage_can_be_created(self, tmp_path):
        """AIBundleStorage initializes without errors."""
        storage = _make_local_storage(tmp_path)
        assert storage is not None

    def test_storage_root_uri_contains_bundle_segments(self, tmp_path):
        """root_uri includes tenant/project/bundle_id path segments."""
        storage = _make_local_storage(tmp_path, tenant="acme", project="main", bundle_id="my-bundle")
        uri = storage.root_uri
        assert "acme" in uri
        assert "main" in uri
        assert "my-bundle" in uri

    def test_write_and_read_bytes(self, tmp_path):
        """write() stores bytes; read() returns them unchanged."""
        storage = _make_local_storage(tmp_path)
        storage.write("test.bin", b"\x00\x01\x02")
        result = storage.read("test.bin")
        assert result == b"\x00\x01\x02"

    def test_write_and_read_text(self, tmp_path):
        """write() stores text; read(as_text=True) returns it unchanged."""
        storage = _make_local_storage(tmp_path)
        storage.write("hello.txt", "hello world")
        result = storage.read("hello.txt", as_text=True)
        assert result == "hello world"

    def test_exists_returns_true_after_write(self, tmp_path):
        """exists() returns True for a key that was written."""
        storage = _make_local_storage(tmp_path)
        storage.write("exists.txt", "data")
        assert storage.exists("exists.txt") is True

    def test_exists_returns_false_for_missing_key(self, tmp_path):
        """exists() returns False for a key that was never written."""
        storage = _make_local_storage(tmp_path)
        assert storage.exists("no-such-file.txt") is False

    def test_list_returns_written_files(self, tmp_path):
        """list() returns files written under the bundle root."""
        storage = _make_local_storage(tmp_path)
        storage.write("file-a.txt", "a")
        storage.write("file-b.txt", "b")
        files = storage.list()
        assert any("file-a.txt" in f for f in files)
        assert any("file-b.txt" in f for f in files)

    def test_delete_removes_file(self, tmp_path):
        """delete() removes the file so exists() returns False."""
        storage = _make_local_storage(tmp_path)
        storage.write("to-delete.txt", "bye")
        storage.delete("to-delete.txt")
        assert storage.exists("to-delete.txt") is False

    def test_write_rejects_path_traversal(self, tmp_path):
        """write() raises ValueError for keys with '..' traversal."""
        storage = _make_local_storage(tmp_path)
        with pytest.raises(ValueError, match="path traversal"):
            storage.write("../escape.txt", "bad")

    def test_write_rejects_empty_key(self, tmp_path):
        """write() raises ValueError for empty key."""
        storage = _make_local_storage(tmp_path)
        with pytest.raises((ValueError, Exception)):
            storage.write("", "data")


class TestAIBundleStorageTenantIsolation:
    """Test that different tenant/project scopes produce isolated paths."""

    def test_different_tenants_have_different_root_uris(self, tmp_path):
        """Storages with different tenants have different root_uris."""
        s1 = _make_local_storage(tmp_path, tenant="tenant-a", project="p", bundle_id="b")
        s2 = _make_local_storage(tmp_path, tenant="tenant-b", project="p", bundle_id="b")
        assert s1.root_uri != s2.root_uri

    def test_different_projects_have_different_root_uris(self, tmp_path):
        """Storages with different projects have different root_uris."""
        s1 = _make_local_storage(tmp_path, tenant="t", project="proj-a", bundle_id="b")
        s2 = _make_local_storage(tmp_path, tenant="t", project="proj-b", bundle_id="b")
        assert s1.root_uri != s2.root_uri

    def test_write_to_one_tenant_not_visible_to_other(self, tmp_path):
        """A file written in tenant-a is not visible in tenant-b."""
        s1 = _make_local_storage(tmp_path, tenant="tenant-a", project="p", bundle_id="b")
        s2 = _make_local_storage(tmp_path, tenant="tenant-b", project="p", bundle_id="b")
        s1.write("secret.txt", "private")
        assert not s2.exists("secret.txt")
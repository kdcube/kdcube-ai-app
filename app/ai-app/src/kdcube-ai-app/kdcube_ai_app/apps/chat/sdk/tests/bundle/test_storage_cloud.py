# SPDX-License-Identifier: MIT

"""Cloud storage (S3) tests for bundles.

Test AIBundleStorage operations against an S3-like backend.
These tests use a local-file backend as a stand-in unless a real S3 URI is set
via CB_BUNDLE_STORAGE_URL env var.

Run with:
  pytest test_storage_cloud.py -v
"""

from __future__ import annotations

import os
import pathlib
import pytest


def _make_storage(tmp_path: pathlib.Path, *, tenant="t", project="p", bundle_id="b"):
    """Create AIBundleStorage with local or env-provided URI."""
    from kdcube_ai_app.apps.chat.sdk.storage.ai_bundle_storage import AIBundleStorage
    uri = os.environ.get("CB_BUNDLE_STORAGE_URL") or f"file://{tmp_path}"
    return AIBundleStorage(tenant=tenant, project=project, ai_bundle_id=bundle_id, storage_uri=uri)


class TestCloudStorageReadWrite:
    """Test read / write operations on the cloud storage backend."""

    def test_write_bytes_returns_uri(self, tmp_path):
        """write() returns a non-empty URI string."""
        storage = _make_storage(tmp_path)
        uri = storage.write("doc.txt", b"hello")
        assert isinstance(uri, str)
        assert uri

    def test_write_and_read_bytes_roundtrip(self, tmp_path):
        """Bytes written are read back unchanged."""
        storage = _make_storage(tmp_path)
        payload = b"binary\x00\xff\xfe"
        storage.write("bin.dat", payload)
        assert storage.read("bin.dat") == payload

    def test_write_and_read_text_roundtrip(self, tmp_path):
        """Text written is read back unchanged."""
        storage = _make_storage(tmp_path)
        storage.write("readme.md", "# Hello\nWorld")
        assert storage.read("readme.md", as_text=True) == "# Hello\nWorld"

    def test_write_uri_contains_bundle_segments(self, tmp_path):
        """Returned URI contains tenant/project/bundle_id path segments."""
        storage = _make_storage(tmp_path, tenant="acme", project="prod", bundle_id="myb")
        uri = storage.write("x.txt", "data")
        assert "acme" in uri
        assert "prod" in uri
        assert "myb" in uri

    def test_write_nested_key(self, tmp_path):
        """Writing a nested key ('dir/file.txt') works correctly."""
        storage = _make_storage(tmp_path)
        storage.write("subdir/nested.txt", "nested")
        assert storage.read("subdir/nested.txt", as_text=True) == "nested"


class TestCloudStorageExistsDelete:
    """Test exists() and delete() operations."""

    def test_exists_true_after_write(self, tmp_path):
        """exists() returns True after writing a file."""
        storage = _make_storage(tmp_path)
        storage.write("present.txt", "yes")
        assert storage.exists("present.txt") is True

    def test_exists_false_for_missing_key(self, tmp_path):
        """exists() returns False for a file that was never written."""
        storage = _make_storage(tmp_path)
        assert storage.exists("ghost.txt") is False

    def test_delete_makes_exists_return_false(self, tmp_path):
        """After delete(), exists() returns False."""
        storage = _make_storage(tmp_path)
        storage.write("temp.txt", "x")
        storage.delete("temp.txt")
        assert storage.exists("temp.txt") is False

    def test_list_returns_written_file(self, tmp_path):
        """list() includes a file that was written."""
        storage = _make_storage(tmp_path)
        storage.write("listed.txt", "ok")
        files = storage.list()
        assert any("listed.txt" in f for f in files)

    def test_write_non_existent_read_raises_or_returns_empty(self, tmp_path):
        """Reading a non-existent file raises an exception (backend-specific)."""
        storage = _make_storage(tmp_path)
        with pytest.raises(Exception):
            storage.read("nonexistent-xyz.txt")


class TestCloudStorageErrorHandling:
    """Test graceful error handling in storage operations."""

    def test_write_path_traversal_raises(self, tmp_path):
        """write() raises ValueError for '../' path traversal."""
        storage = _make_storage(tmp_path)
        with pytest.raises(ValueError):
            storage.write("../../escape.txt", "bad")

    def test_write_empty_key_raises(self, tmp_path):
        """write() raises for an empty key."""
        storage = _make_storage(tmp_path)
        with pytest.raises(Exception):
            storage.write("", "data")

    def test_delete_nonexistent_does_not_crash(self, tmp_path):
        """Deleting a key that doesn't exist does not raise."""
        storage = _make_storage(tmp_path)
        try:
            storage.delete("never-existed.txt")
        except Exception as e:
            pytest.fail(f"delete() of nonexistent key should not raise, got: {e}")
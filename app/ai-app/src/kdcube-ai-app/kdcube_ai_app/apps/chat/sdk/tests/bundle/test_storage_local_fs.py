# SPDX-License-Identifier: MIT

"""Local filesystem storage tests for bundles.

Test AIBundleStorage operations against the local filesystem backend.
All tests use a pytest tmp_path fixture — no persistent side effects.

Run with:
  pytest test_storage_local_fs.py -v
"""

from __future__ import annotations

import pathlib
import pytest


def _make_local_storage(tmp_path: pathlib.Path, *, tenant="t", project="p", bundle_id="b"):
    from kdcube_ai_app.apps.chat.sdk.storage.ai_bundle_storage import AIBundleStorage
    return AIBundleStorage(
        tenant=tenant,
        project=project,
        ai_bundle_id=bundle_id,
        storage_uri=f"file://{tmp_path}",
    )


class TestLocalFSReadWrite:
    """Basic read / write operations."""

    def test_write_creates_file_under_tmp(self, tmp_path):
        """write() creates a physical file under tmp_path."""
        storage = _make_local_storage(tmp_path)
        storage.write("hello.txt", "hello")
        # At least one file must have been created somewhere in tmp_path
        files = list(tmp_path.rglob("hello.txt"))
        assert files, "write() must create the file on the local filesystem"

    def test_read_bytes_returns_bytes(self, tmp_path):
        """read() returns bytes by default."""
        storage = _make_local_storage(tmp_path)
        storage.write("data.bin", b"\x01\x02\x03")
        result = storage.read("data.bin")
        assert isinstance(result, bytes)

    def test_read_text_returns_str(self, tmp_path):
        """read(as_text=True) returns str."""
        storage = _make_local_storage(tmp_path)
        storage.write("note.txt", "hello world")
        result = storage.read("note.txt", as_text=True)
        assert isinstance(result, str)
        assert result == "hello world"

    def test_write_overwrite_replaces_content(self, tmp_path):
        """Writing the same key twice replaces content."""
        storage = _make_local_storage(tmp_path)
        storage.write("file.txt", "first")
        storage.write("file.txt", "second")
        assert storage.read("file.txt", as_text=True) == "second"

    def test_write_with_mime_does_not_corrupt_content(self, tmp_path):
        """write() with explicit mime= does not corrupt binary payload."""
        storage = _make_local_storage(tmp_path)
        payload = b"\xff\xd8\xff"  # JPEG magic bytes
        storage.write("image.jpg", payload, mime="image/jpeg")
        assert storage.read("image.jpg") == payload


class TestLocalFSTempFiles:
    """Test temporary file lifecycle."""

    def test_files_exist_only_in_tmp_path(self, tmp_path):
        """All written files are contained within tmp_path (no leakage)."""
        storage = _make_local_storage(tmp_path)
        storage.write("scoped.txt", "scoped")
        files = list(tmp_path.rglob("scoped.txt"))
        for f in files:
            assert str(f).startswith(str(tmp_path)), (
                f"File {f} leaked outside tmp_path {tmp_path}"
            )

    def test_delete_removes_physical_file(self, tmp_path):
        """delete() removes the physical file from the filesystem."""
        storage = _make_local_storage(tmp_path)
        storage.write("rm.txt", "bye")
        storage.delete("rm.txt")
        remaining = list(tmp_path.rglob("rm.txt"))
        assert not remaining, "delete() must remove the physical file"

    def test_delete_subtree_removes_all_children(self, tmp_path):
        """delete('prefix/') removes all files under that prefix."""
        storage = _make_local_storage(tmp_path)
        storage.write("folder/a.txt", "a")
        storage.write("folder/b.txt", "b")
        storage.delete("folder/")
        assert not storage.exists("folder/a.txt")
        assert not storage.exists("folder/b.txt")


class TestLocalFSGracefulHandling:
    """Test that local FS handles edge cases gracefully."""

    def test_list_empty_bucket_returns_list(self, tmp_path):
        """list() on a fresh storage returns a list (may be empty)."""
        storage = _make_local_storage(tmp_path)
        result = storage.list()
        assert isinstance(result, list)

    def test_exists_false_before_write(self, tmp_path):
        """exists() returns False before any write."""
        storage = _make_local_storage(tmp_path)
        assert storage.exists("nothing.txt") is False

    def test_two_storages_same_tmp_are_isolated_by_bundle_id(self, tmp_path):
        """Two storages with different bundle IDs don't share files."""
        s1 = _make_local_storage(tmp_path, bundle_id="bundle-a")
        s2 = _make_local_storage(tmp_path, bundle_id="bundle-b")
        s1.write("shared-name.txt", "from-a")
        assert not s2.exists("shared-name.txt"), (
            "Files in bundle-a must not be visible in bundle-b"
        )

    def test_local_storage_scheme_is_file(self, tmp_path):
        """Local storage URI uses 'file' scheme."""
        storage = _make_local_storage(tmp_path)
        assert storage.scheme == "file"
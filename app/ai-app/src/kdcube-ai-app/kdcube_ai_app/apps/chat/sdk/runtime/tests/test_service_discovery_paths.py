# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.runtime.external import service_discovery


def test_translate_git_bundles_container_path_to_host(monkeypatch):
    monkeypatch.setenv("HOST_GIT_BUNDLES_PATH", "/host/git-bundles")

    translated = service_discovery._translate_container_path_to_host(
        Path("/git-bundles/demo.bundle/entrypoint.py")
    )

    assert translated == Path("/host/git-bundles/demo.bundle/entrypoint.py")


def test_translate_git_bundles_falls_back_to_host_bundles(monkeypatch):
    monkeypatch.delenv("HOST_GIT_BUNDLES_PATH", raising=False)
    monkeypatch.setenv("HOST_BUNDLES_PATH", "/host/bundles")

    translated = service_discovery._translate_container_path_to_host(
        Path("/git-bundles/demo.bundle")
    )

    assert translated == Path("/host/bundles/demo.bundle")

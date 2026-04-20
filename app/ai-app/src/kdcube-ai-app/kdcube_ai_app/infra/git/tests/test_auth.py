# SPDX-License-Identifier: MIT

from __future__ import annotations

import subprocess
from pathlib import Path

from kdcube_ai_app.infra.git import auth as git_auth


def test_build_git_env_uses_explicit_http_credentials(tmp_path: Path):
    askpass_path = tmp_path / "git_askpass.sh"

    env = git_auth.build_git_env(
        git_http_token="pat-token",
        git_http_user="git-user",
        askpass_script_path=askpass_path,
        base_env={},
    )

    assert env["GIT_HTTP_TOKEN"] == "pat-token"
    assert env["GIT_HTTP_USER"] == "git-user"
    assert env["GIT_ASKPASS"] == str(askpass_path)
    assert env["GIT_ASKPASS_REQUIRE"] == "force"
    assert askpass_path.exists()


def test_build_git_env_uses_explicit_ssh_settings_without_key():
    env = git_auth.build_git_env(
        git_ssh_known_hosts="/run/secrets/git_known_hosts",
        git_ssh_strict_host_key_checking="yes",
        base_env={},
    )

    assert env["GIT_SSH_COMMAND"] == (
        "ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/run/secrets/git_known_hosts"
    )


def test_normalize_git_remote_url_rewrites_ssh_when_pat_is_present():
    assert git_auth.normalize_git_remote_url(
        "git@github.com:org/workspace.git",
        git_http_token="pat-token",
        base_env={},
    ) == "https://github.com/org/workspace.git"


def test_normalize_git_remote_url_leaves_ssh_when_pat_is_absent():
    assert git_auth.normalize_git_remote_url(
        "git@github.com:org/workspace.git",
        base_env={},
    ) == "git@github.com:org/workspace.git"


def test_ensure_git_commit_identity_sets_repo_local_identity(tmp_path: Path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)

    git_auth.ensure_git_commit_identity(
        repo_root=repo,
        name="Local Bundle Bot",
        email="bundle.bot@local.invalid",
    )

    name = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "user.name"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    email = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "user.email"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert name == "Local Bundle Bot"
    assert email == "bundle.bot@local.invalid"


def test_ensure_git_commit_identity_updates_existing_repo_local_identity(tmp_path: Path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Old Name"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "old@local.invalid"], check=True, capture_output=True, text=True)

    git_auth.ensure_git_commit_identity(
        repo_root=repo,
        name="New Name",
        email="new@local.invalid",
    )

    name = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "user.name"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    email = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "user.email"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert name == "New Name"
    assert email == "new@local.invalid"

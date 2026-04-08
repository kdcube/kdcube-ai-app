# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import asyncio
import logging
import pathlib
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Literal

from kdcube_ai_app.apps.chat.sdk.solutions.claude_code.agent import ClaudeCodeAgent
from kdcube_ai_app.apps.chat.sdk.solutions.claude_code.types import (
    ClaudeCodeRunResult,
    ClaudeCodeTurnKind,
)
from kdcube_ai_app.infra.plugin.git_bundle import _build_git_env


ClaudeCodeSessionStoreImplementation = Literal["local", "git"]


def _safe_segment(value: str | None, *, fallback: str) -> str:
    raw = str(value or "").strip()
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in raw).strip("-_.")
    return safe or fallback


@dataclass(frozen=True)
class ClaudeCodeSessionStoreConfig:
    implementation: ClaudeCodeSessionStoreImplementation = "local"
    local_root: pathlib.Path = pathlib.Path(".")
    tenant: str = "home"
    project: str = "default-project"
    user_id: str = "anonymous"
    conversation_id: str = "conversation"
    agent_name: str = "claude-code"
    git_repo: str | None = None
    bootstrap_turn_kinds: tuple[ClaudeCodeTurnKind, ...] = field(default_factory=lambda: ("regular",))
    publish_turn_kinds: tuple[ClaudeCodeTurnKind, ...] = field(default_factory=lambda: ("regular",))

    def __post_init__(self) -> None:
        object.__setattr__(self, "implementation", str(self.implementation or "local").strip().lower() or "local")
        object.__setattr__(self, "local_root", pathlib.Path(self.local_root))
        object.__setattr__(self, "tenant", _safe_segment(self.tenant, fallback="home"))
        object.__setattr__(self, "project", _safe_segment(self.project, fallback="default-project"))
        object.__setattr__(self, "user_id", _safe_segment(self.user_id, fallback="anonymous"))
        object.__setattr__(self, "conversation_id", _safe_segment(self.conversation_id, fallback="conversation"))
        object.__setattr__(self, "agent_name", _safe_segment(self.agent_name, fallback="claude-code"))
        object.__setattr__(self, "git_repo", str(self.git_repo or "").strip() or None)
        object.__setattr__(
            self,
            "bootstrap_turn_kinds",
            tuple(kind for kind in self.bootstrap_turn_kinds if str(kind).strip()),
        )
        object.__setattr__(
            self,
            "publish_turn_kinds",
            tuple(kind for kind in self.publish_turn_kinds if str(kind).strip()),
        )
        if self.implementation not in {"local", "git"}:
            raise ValueError(f"unsupported_claude_code_session_store:{self.implementation}")


def claude_code_session_branch_ref(config: ClaudeCodeSessionStoreConfig) -> str:
    return (
        "refs/heads/kdcube/claude/"
        f"{config.tenant}/{config.project}/{config.user_id}/{config.conversation_id}/{config.agent_name}"
    )


def _session_cache_root(config: ClaudeCodeSessionStoreConfig) -> pathlib.Path:
    local_root = pathlib.Path(config.local_root)
    return (
        local_root.parent
        / ".claude_session_git"
        / f"{config.tenant}__{config.project}__{config.user_id}__{config.conversation_id}__{config.agent_name}"
    )


def _session_lineage_repo_root(config: ClaudeCodeSessionStoreConfig) -> pathlib.Path:
    return _session_cache_root(config) / "lineage.git"


def _run_git_capture(
    repo_root: pathlib.Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _git_has_ref(*, repo_root: pathlib.Path, ref_name: str) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet", ref_name],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _git_has_head(*, repo_root: pathlib.Path) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _git_has_staged_changes(*, repo_root: pathlib.Path) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    return proc.returncode != 0


def _git_head_sha(*, repo_root: pathlib.Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return (proc.stdout or "").strip()


def _ensure_session_repo(
    *,
    config: ClaudeCodeSessionStoreConfig,
) -> pathlib.Path:
    if config.implementation != "git":
        raise ValueError("claude_code_session_store_not_git")
    repo_url = str(config.git_repo or "").strip()
    if not repo_url:
        raise ValueError("missing_claude_code_session_git_repo")
    env = _build_git_env()
    cache_root = _session_cache_root(config)
    repo_root = _session_lineage_repo_root(config)
    cache_root.mkdir(parents=True, exist_ok=True)
    if not (repo_root / "HEAD").exists():
        subprocess.run(
            ["git", "init", "--bare", str(repo_root)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "remote", "add", "origin", repo_url],
            check=True,
            capture_output=True,
            env=env,
        )
        try:
            subprocess.run(
                ["git", "-C", str(repo_root), "config", "--unset-all", "remote.origin.fetch"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass
        subprocess.run(
            ["git", "-C", str(repo_root), "config", "remote.origin.tagOpt", "--no-tags"],
            check=True,
            capture_output=True,
        )
    else:
        try:
            subprocess.run(
                ["git", "-C", str(repo_root), "remote", "set-url", "origin", repo_url],
                check=True,
                capture_output=True,
                env=env,
            )
        except Exception:
            pass
    return repo_root


def _ensure_local_lineage_branch_ref(
    *,
    repo_root: pathlib.Path,
    config: ClaudeCodeSessionStoreConfig,
) -> str:
    env = _build_git_env()
    remote_ref = claude_code_session_branch_ref(config)
    local_ref = "refs/heads/workspace"
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "fetch", "--no-tags", "origin", f"+{remote_ref}:{local_ref}"],
            check=True,
            capture_output=True,
            env=env,
        )
    except subprocess.CalledProcessError:
        if _git_has_ref(repo_root=repo_root, ref_name=local_ref):
            return local_ref
        return ""
    return local_ref


def _session_commit_identity(config: ClaudeCodeSessionStoreConfig) -> tuple[str, str]:
    safe_user = _safe_segment(config.user_id, fallback="claude")
    return f"Claude Session ({config.user_id})", f"{safe_user}@local.invalid"


def _ensure_local_git_repo(*, local_root: pathlib.Path, config: ClaudeCodeSessionStoreConfig) -> None:
    if (local_root / ".git").exists():
        return
    local_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", str(local_root)],
        check=True,
        capture_output=True,
    )
    name, email = _session_commit_identity(config)
    subprocess.run(
        ["git", "-C", str(local_root), "config", "user.name", name],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(local_root), "config", "user.email", email],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(local_root), "config", "advice.detachedHead", "false"],
        check=True,
        capture_output=True,
    )


def _clear_session_root(*, local_root: pathlib.Path) -> None:
    if not local_root.exists():
        local_root.mkdir(parents=True, exist_ok=True)
        return
    for child in local_root.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def bootstrap_claude_code_session_store(
    *,
    config: ClaudeCodeSessionStoreConfig,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    log = logger or logging.getLogger("ClaudeCodeRuntime")
    local_root = pathlib.Path(config.local_root)
    local_root.mkdir(parents=True, exist_ok=True)
    if config.implementation != "git":
        return {
            "implementation": config.implementation,
            "local_root": str(local_root),
            "bootstrapped": False,
            "reason": "local_session_store",
        }

    repo_root = _ensure_session_repo(config=config)
    lineage_ref = _ensure_local_lineage_branch_ref(repo_root=repo_root, config=config)
    _ensure_local_git_repo(local_root=local_root, config=config)
    if lineage_ref:
        _clear_session_root(local_root=local_root)
        subprocess.run(
            ["git", "-C", str(local_root), "fetch", "--no-tags", str(repo_root), f"+{lineage_ref}:refs/heads/workspace"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(local_root), "checkout", "-B", "workspace", "refs/heads/workspace"],
            check=True,
            capture_output=True,
        )
        action = "checked_out_remote_branch"
    else:
        if not _git_has_head(repo_root=local_root):
            subprocess.run(
                ["git", "-C", str(local_root), "checkout", "--orphan", "workspace"],
                check=True,
                capture_output=True,
            )
            action = "initialized_empty_workspace"
        else:
            action = "reused_local_workspace"
    log.info(
        "[ClaudeCodeRuntime] bootstrapped session store agent=%s conversation=%s local_root=%s action=%s branch=%s",
        config.agent_name,
        config.conversation_id,
        local_root,
        action,
        claude_code_session_branch_ref(config),
    )
    return {
        "implementation": config.implementation,
        "local_root": str(local_root),
        "repo_root": str(repo_root),
        "lineage_ref": claude_code_session_branch_ref(config),
        "bootstrapped": bool(lineage_ref),
        "action": action,
    }


def publish_claude_code_session_store(
    *,
    config: ClaudeCodeSessionStoreConfig,
    logger: logging.Logger | None = None,
) -> dict[str, object]:
    log = logger or logging.getLogger("ClaudeCodeRuntime")
    local_root = pathlib.Path(config.local_root)
    local_root.mkdir(parents=True, exist_ok=True)
    if config.implementation != "git":
        return {
            "implementation": config.implementation,
            "local_root": str(local_root),
            "published": False,
            "reason": "local_session_store",
        }

    repo_root = _ensure_session_repo(config=config)
    _ensure_local_git_repo(local_root=local_root, config=config)
    subprocess.run(
        ["git", "-C", str(local_root), "add", "-A", "--", "."],
        check=True,
        capture_output=True,
    )
    committed = False
    message = f"Claude session snapshot {config.conversation_id}"
    has_head = _git_has_head(repo_root=local_root)
    if not has_head:
        subprocess.run(
            ["git", "-C", str(local_root), "commit", "--allow-empty", "-m", message],
            check=True,
            capture_output=True,
        )
        committed = True
    elif _git_has_staged_changes(repo_root=local_root):
        subprocess.run(
            ["git", "-C", str(local_root), "commit", "-m", message],
            check=True,
            capture_output=True,
        )
        committed = True

    head_sha = _git_head_sha(repo_root=local_root)
    subprocess.run(
        ["git", "-C", str(local_root), "push", str(repo_root), "HEAD:refs/heads/workspace"],
        check=True,
        capture_output=True,
    )
    env = _build_git_env()
    lineage_ref = claude_code_session_branch_ref(config)
    subprocess.run(
        ["git", "-C", str(repo_root), "push", "origin", f"refs/heads/workspace:{lineage_ref}"],
        check=True,
        capture_output=True,
        env=env,
    )
    log.info(
        "[ClaudeCodeRuntime] published session store agent=%s conversation=%s local_root=%s branch=%s commit=%s committed=%s",
        config.agent_name,
        config.conversation_id,
        local_root,
        lineage_ref,
        head_sha,
        committed,
    )
    return {
        "implementation": config.implementation,
        "local_root": str(local_root),
        "repo_root": str(repo_root),
        "lineage_ref": lineage_ref,
        "commit_sha": head_sha,
        "committed": committed,
        "published": True,
    }


async def run_claude_code_turn(
    *,
    agent: ClaudeCodeAgent,
    prompt: str,
    kind: ClaudeCodeTurnKind = "regular",
    resume_existing: bool = False,
    session_store: ClaudeCodeSessionStoreConfig | None = None,
    refresh_support_files: Callable[[], None] | None = None,
    logger: logging.Logger | None = None,
) -> ClaudeCodeRunResult:
    should_bootstrap = bool(
        session_store
        and session_store.implementation == "git"
        and kind in set(session_store.bootstrap_turn_kinds)
    )
    should_publish = bool(
        session_store
        and session_store.implementation == "git"
        and kind in set(session_store.publish_turn_kinds)
    )

    if should_bootstrap and session_store is not None:
        await asyncio.to_thread(
            bootstrap_claude_code_session_store,
            config=session_store,
            logger=logger,
        )
        if refresh_support_files is not None:
            refresh_support_files()

    try:
        return await agent.run_turn(
            prompt,
            kind=kind,
            resume_existing=resume_existing,
        )
    finally:
        if should_publish and session_store is not None:
            await asyncio.to_thread(
                publish_claude_code_session_store,
                config=session_store,
                logger=logger,
            )

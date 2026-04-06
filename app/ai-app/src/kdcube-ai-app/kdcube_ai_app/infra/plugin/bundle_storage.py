# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

from __future__ import annotations

import asyncio
import os
import pathlib
from typing import Optional

from kdcube_ai_app.infra.service_hub.inventory import AgentLogger

from kdcube_ai_app.infra.plugin.git_bundle import resolve_bundles_root


def _sanitize_segment(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in (raw or ""))
    safe = safe.strip("-_")
    return safe or "default"


def resolve_bundle_storage_root() -> pathlib.Path:
    """
    Resolve the shared storage root for bundle-managed assets (indexes, repos, etc).
    Prefer explicit env, otherwise default under bundles root.
    """
    root = os.environ.get("BUNDLE_SHARED_STORAGE_ROOT") or os.environ.get("BUNDLE_STORAGE_ROOT")
    if root:
        # Accept plain filesystem paths. If a file:// URI is provided, normalize to path.
        if isinstance(root, str) and root.startswith("file://"):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(root)
                if parsed.scheme == "file" and parsed.path:
                    return pathlib.Path(parsed.path).expanduser().resolve()
            except Exception:
                pass
        return pathlib.Path(root).expanduser().resolve()
    bundles_root = resolve_bundles_root()
    return (bundles_root / "_bundle_storage").resolve()


def bundle_storage_dir(
    *,
    bundle_id: str,
    version: Optional[str] = None,
    tenant: Optional[str] = None,
    project: Optional[str] = None,
    ensure: bool = True,
) -> pathlib.Path:
    """
    Compute a per-bundle storage directory.
    If tenant/project are provided, isolate under <tenant>/<project>/...
    If version/git_commit/ref is provided, append it to avoid stale data reuse.
    """
    root = resolve_bundle_storage_root()
    parts = []
    if tenant:
        parts.append(_sanitize_segment(tenant))
    if project:
        parts.append(_sanitize_segment(project))
    bid = _sanitize_segment(bundle_id or "bundle")
    if version:
        parts.append(f"{bid}__{_sanitize_segment(version)}")
    else:
        parts.append(bid)
    storage = root.joinpath(*parts).resolve()
    if ensure:
        storage.mkdir(parents=True, exist_ok=True)
    return storage


def storage_for_spec(
    *,
    spec: Optional[object],
    tenant: Optional[str] = None,
    project: Optional[str] = None,
    ensure: bool = True,
) -> Optional[pathlib.Path]:
    """
    Convenience helper that accepts a BundleSpec-like object.
    Expects attributes: id, version, git_commit, ref.
    """
    if spec is None:
        return None
    bundle_id = getattr(spec, "id", None) or ""
    # Prefer git_commit/ref for stable, user-controlled versioning.
    # Fall back to spec.version only if neither is present.
    version = (
        getattr(spec, "git_commit", None)
        or getattr(spec, "ref", None)
        or getattr(spec, "version", None)
    )
    if not bundle_id:
        return None
    return bundle_storage_dir(
        bundle_id=bundle_id,
        version=version,
        tenant=tenant,
        project=project,
        ensure=ensure,
    )


def cleanup_old_bundle_storage(
    *,
    bundle_id: str,
    tenant: Optional[str],
    project: Optional[str],
    storage_root: Optional[pathlib.Path] = None,
    keep: Optional[int] = None,
    ttl_hours: Optional[int] = None,
    active_paths: Optional[list[str]] = None,
    logger: Optional[AgentLogger] = None,
) -> int:
    """
    Remove old versioned bundle storage directories for a bundle within a tenant/project scope.

    Only versioned storage dirs are considered:
      <root>/<tenant>/<project>/<bundle_id>__<version>

    The unversioned storage dir:
      <root>/<tenant>/<project>/<bundle_id>
    is never deleted by this helper.
    """
    log = logger or AgentLogger("bundle.storage")
    root = storage_root or resolve_bundle_storage_root()
    keep = keep if keep is not None else int(os.environ.get("BUNDLE_STORAGE_KEEP", "3") or "3")
    ttl_hours = ttl_hours if ttl_hours is not None else int(os.environ.get("BUNDLE_STORAGE_TTL_HOURS", "0") or "0")

    scope_root = root
    if tenant:
        scope_root = scope_root / _sanitize_segment(tenant)
    if project:
        scope_root = scope_root / _sanitize_segment(project)
    if not scope_root.exists():
        return 0

    prefix = f"{_sanitize_segment(bundle_id or 'bundle')}__"
    active_set: set[pathlib.Path] = set()
    if active_paths:
        for raw in active_paths:
            try:
                active_set.add(pathlib.Path(raw).resolve())
            except Exception:
                continue

    def _is_active_dir(path: pathlib.Path) -> bool:
        if not active_set:
            return False
        for active in active_set:
            try:
                active.relative_to(path)
                return True
            except Exception:
                continue
        return False

    candidates: list[pathlib.Path] = []
    for item in scope_root.iterdir():
        if not item.is_dir():
            continue
        if not item.name.startswith(prefix):
            continue
        candidates.append(item)

    candidates.sort(
        key=lambda item: (
            int(item.stat().st_mtime) if item.exists() else 0,
            item.name,
        ),
        reverse=True,
    )

    removed = 0
    if ttl_hours and ttl_hours > 0:
        import time as _time
        cutoff = _time.time() - (ttl_hours * 3600)
        for item in list(candidates):
            try:
                if _is_active_dir(item):
                    continue
                if item.stat().st_mtime < cutoff:
                    import shutil
                    shutil.rmtree(item, ignore_errors=True)
                    removed += 1
                    candidates = [candidate for candidate in candidates if candidate != item]
            except Exception:
                continue

    for item in candidates[keep:]:
        try:
            if _is_active_dir(item):
                continue
            import shutil
            shutil.rmtree(item, ignore_errors=True)
            removed += 1
        except Exception:
            continue

    if removed:
        log.log(
            f"[bundle.storage] cleaned {removed} old storage dirs for {bundle_id} "
            f"(tenant={tenant or 'default'}, project={project or 'default'})",
            level="INFO",
        )
    return removed


async def cleanup_old_bundle_storage_async(
    *,
    bundle_id: str,
    tenant: Optional[str],
    project: Optional[str],
    storage_root: Optional[pathlib.Path] = None,
    keep: Optional[int] = None,
    ttl_hours: Optional[int] = None,
    active_paths: Optional[list[str]] = None,
    logger: Optional[AgentLogger] = None,
) -> int:
    return await asyncio.to_thread(
        cleanup_old_bundle_storage,
        bundle_id=bundle_id,
        tenant=tenant,
        project=project,
        storage_root=storage_root,
        keep=keep,
        ttl_hours=ttl_hours,
        active_paths=active_paths,
        logger=logger,
    )

from __future__ import annotations

import io
import os
import shutil
import stat
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from kdcube_ai_app.apps.chat.sdk.config import get_settings
from kdcube_ai_app.infra.plugin.bundle_storage import resolve_bundle_storage_root
from kdcube_ai_app.infra.plugin.git_bundle import resolve_managed_bundles_root


class StorageAdminError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "storage_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass
class StorageRoot:
    id: str
    label: str
    description: str
    kind: str
    uri: str
    path: Optional[str]
    exists: bool
    writable: bool
    tenant_project_mode: str
    capabilities: List[str]


@dataclass
class StorageEntry:
    name: str
    path: str
    kind: str
    size_bytes: Optional[int]
    modified_at: Optional[float]
    child_count: Optional[int]
    deletable: bool
    exportable: bool
    symlink_target: Optional[str] = None


def _file_uri_to_path(raw: str) -> Optional[Path]:
    value = str(raw or "").strip()
    if not value:
        return None
    if value.startswith("file://"):
        parsed = urlparse(value)
        return Path(parsed.path).expanduser().resolve() if parsed.path else None
    if "://" in value:
        return None
    return Path(value).expanduser().resolve()


def _path_writable(path: Optional[Path]) -> bool:
    if path is None or not path.exists():
        return False
    return os.access(path, os.W_OK)


def _root_descriptor(
    *,
    root_id: str,
    label: str,
    description: str,
    kind: str,
    uri: str,
    path: Optional[Path],
    tenant_project_mode: str,
) -> StorageRoot:
    local = path is not None
    exists = bool(path and path.exists())
    capabilities = ["list"] if local else []
    if local:
        capabilities.extend(["export", "delete"])
    return StorageRoot(
        id=root_id,
        label=label,
        description=description,
        kind=kind,
        uri=uri,
        path=str(path) if path else None,
        exists=exists,
        writable=_path_writable(path),
        tenant_project_mode=tenant_project_mode,
        capabilities=capabilities,
    )


def storage_roots() -> List[Dict[str, Any]]:
    settings = get_settings()
    bundle_root = resolve_bundle_storage_root()
    managed_root = resolve_managed_bundles_root()
    shared_uri = (
        str(getattr(settings, "STORAGE_PATH", None) or "").strip()
        or str(os.environ.get("KDCUBE_STORAGE_PATH") or "").strip()
    )
    shared_path = _file_uri_to_path(shared_uri)

    roots = [
        _root_descriptor(
            root_id="bundle_storage",
            label="Bundle storage",
            description="Per-tenant/project bundle runtime storage, including built widget artifacts and bundle-owned data.",
            kind="local-fs",
            uri=str(bundle_root),
            path=bundle_root,
            tenant_project_mode="required",
        ),
        _root_descriptor(
            root_id="managed_bundles",
            label="Managed bundles",
            description="Materialized bundles resolved from git or built-in managed sources.",
            kind="local-fs",
            uri=str(managed_root),
            path=managed_root,
            tenant_project_mode="none",
        ),
        _root_descriptor(
            root_id="shared_storage",
            label="Shared storage",
            description="Configured shared application storage. Local file roots can be browsed here; remote object storage is reported by URI.",
            kind="local-fs" if shared_path else ("remote" if shared_uri else "unconfigured"),
            uri=shared_uri,
            path=shared_path,
            tenant_project_mode="optional",
        ),
    ]
    return [asdict(root) for root in roots]


def _root_by_id(root_id: str) -> StorageRoot:
    for root in storage_roots():
        if root["id"] == root_id:
            return StorageRoot(**root)
    raise StorageAdminError(f"Unknown storage root: {root_id}", status_code=404, code="unknown_root")


def _require_local_root(root_id: str) -> tuple[StorageRoot, Path]:
    root = _root_by_id(root_id)
    if not root.path:
        raise StorageAdminError(
            f"Storage root '{root_id}' is not a local filesystem root",
            status_code=400,
            code="non_local_root",
        )
    return root, Path(root.path).expanduser().resolve()


def _clean_scope_segment(value: Optional[str], *, name: str) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise StorageAdminError(f"Invalid {name}", status_code=400, code="invalid_scope")
    return cleaned


def _normalize_relpath(value: Optional[str]) -> PurePosixPath:
    raw = str(value or "").strip().replace("\\", "/")
    raw = raw.lstrip("/")
    if not raw or raw == ".":
        return PurePosixPath(".")
    rel = PurePosixPath(raw)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise StorageAdminError("Invalid storage path", status_code=400, code="invalid_path")
    return rel


def _scope_base(root_id: str, root_path: Path, *, tenant: Optional[str], project: Optional[str]) -> Path:
    tenant_id = _clean_scope_segment(tenant, name="tenant")
    project_id = _clean_scope_segment(project, name="project")
    if root_id == "managed_bundles":
        return root_path
    if root_id == "bundle_storage":
        if not tenant_id or not project_id:
            raise StorageAdminError("Tenant and project are required for bundle storage", code="missing_scope")
        return (root_path / tenant_id / project_id).resolve()
    if root_id == "shared_storage" and tenant_id and project_id:
        candidates = [
            root_path / "cb" / "tenants" / tenant_id / "projects" / project_id,
            root_path / "tenants" / tenant_id / "projects" / project_id,
            root_path / tenant_id / project_id,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return root_path
    return root_path


def _target_under(base: Path, relpath: Optional[str]) -> Path:
    rel = _normalize_relpath(relpath)
    if str(rel) == ".":
        return base
    parts = [] if str(rel) == "." else list(rel.parts)
    candidate = base.joinpath(*parts)
    parent = candidate.parent.resolve(strict=False)
    try:
        parent.relative_to(base.resolve(strict=False))
    except ValueError:
        raise StorageAdminError("Storage path escapes the selected root", status_code=400, code="path_escape")
    return candidate


def _relative_to_base(path: Path, base: Path) -> str:
    try:
        rel = path.relative_to(base)
    except ValueError:
        return ""
    return "" if str(rel) == "." else rel.as_posix()


def _count_children(path: Path, *, limit: int = 1000) -> Optional[int]:
    if not path.exists() or path.is_symlink() or not path.is_dir():
        return None
    count = 0
    try:
        for _ in path.iterdir():
            count += 1
            if count >= limit:
                return count
    except OSError:
        return None
    return count


def _entry_for(path: Path, *, base: Path, root_rel: str = "") -> StorageEntry:
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise StorageAdminError("Storage path does not exist", status_code=404, code="not_found")

    mode = info.st_mode
    if stat.S_ISLNK(mode):
        kind = "symlink"
        symlink_target = os.readlink(path)
        size_bytes = info.st_size
    elif stat.S_ISDIR(mode):
        kind = "directory"
        symlink_target = None
        size_bytes = None
    elif stat.S_ISREG(mode):
        kind = "file"
        symlink_target = None
        size_bytes = info.st_size
    else:
        kind = "other"
        symlink_target = None
        size_bytes = info.st_size

    rel = _relative_to_base(path, base)
    if root_rel and rel:
        rel = f"{root_rel.rstrip('/')}/{rel}"
    elif root_rel and not rel:
        rel = root_rel.strip("/")
    return StorageEntry(
        name=path.name,
        path=rel,
        kind=kind,
        size_bytes=size_bytes,
        modified_at=info.st_mtime,
        child_count=_count_children(path),
        deletable=bool(rel),
        exportable=kind in {"file", "directory"},
        symlink_target=symlink_target,
    )


def list_tenant_projects(root_id: str) -> Dict[str, Any]:
    root, root_path = _require_local_root(root_id)
    tenants: List[Dict[str, Any]] = []
    if root_id == "managed_bundles":
        return {"root": asdict(root), "tenants": tenants}

    tenant_bases = [root_path]
    if root_id == "shared_storage":
        tenant_bases = [root_path / "cb" / "tenants", root_path / "tenants", root_path]

    seen: set[str] = set()
    for tenant_base in tenant_bases:
        if not tenant_base.exists() or not tenant_base.is_dir():
            continue
        for tenant_dir in sorted((p for p in tenant_base.iterdir() if p.is_dir() and not p.is_symlink()), key=lambda p: p.name):
            if tenant_dir.name in seen:
                continue
            project_parent = tenant_dir / "projects"
            project_dirs = project_parent if project_parent.exists() else tenant_dir
            projects = [
                p.name
                for p in sorted((p for p in project_dirs.iterdir() if p.is_dir() and not p.is_symlink()), key=lambda p: p.name)
            ] if project_dirs.exists() else []
            tenants.append({"tenant": tenant_dir.name, "projects": projects})
            seen.add(tenant_dir.name)
    return {"root": asdict(root), "tenants": tenants}


def list_storage_path(
    *,
    root_id: str,
    tenant: Optional[str] = None,
    project: Optional[str] = None,
    path: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    root, root_path = _require_local_root(root_id)
    base = _scope_base(root_id, root_path, tenant=tenant, project=project)
    target = _target_under(base, path)
    if target.is_symlink():
        entries: List[StorageEntry] = []
        current = _entry_for(target, base=base)
    elif target.exists() and target.is_dir():
        current = _entry_for(target, base=base)
        entries = [
            _entry_for(child, base=base)
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[: max(1, min(limit, 2000))]
        ]
    elif target.exists():
        current = _entry_for(target, base=base)
        entries = []
    else:
        raise StorageAdminError("Storage path does not exist", status_code=404, code="not_found")

    return {
        "root": asdict(root),
        "tenant": tenant,
        "project": project,
        "base_path": str(base),
        "path": current.path,
        "current": asdict(current),
        "entries": [asdict(entry) for entry in entries],
        "generated_at": time.time(),
    }


def _iter_export_files(path: Path) -> Iterable[Path]:
    if path.is_symlink():
        return
    if path.is_file():
        yield path
        return
    if path.is_dir():
        stack = [path]
        while stack:
            current = stack.pop()
            try:
                children = list(current.iterdir())
            except OSError:
                continue
            for child in children:
                if child.is_symlink():
                    continue
                if child.is_file():
                    yield child
                    continue
                if child.is_dir():
                    stack.append(child)


def export_storage_paths(
    *,
    root_id: str,
    paths: List[str],
    tenant: Optional[str] = None,
    project: Optional[str] = None,
) -> tuple[bytes, str]:
    if not paths:
        raise StorageAdminError("At least one path is required for export", code="missing_paths")
    root, root_path = _require_local_root(root_id)
    base = _scope_base(root_id, root_path, tenant=tenant, project=project)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for raw_path in paths:
            rel = _normalize_relpath(raw_path)
            if str(rel) == ".":
                raise StorageAdminError("Export the selected root by choosing its children", code="root_export_refused")
            target = _target_under(base, raw_path)
            if not target.exists():
                raise StorageAdminError(f"Storage path does not exist: {raw_path}", status_code=404, code="not_found")
            for file_path in _iter_export_files(target):
                arcname = file_path.relative_to(base).as_posix()
                zf.write(file_path, arcname)
    archive.seek(0)
    filename = f"{root.id}-export-{int(time.time())}.zip"
    return archive.getvalue(), filename


def delete_storage_paths(
    *,
    root_id: str,
    paths: List[str],
    tenant: Optional[str] = None,
    project: Optional[str] = None,
    confirm: bool = False,
) -> Dict[str, Any]:
    if not confirm:
        raise StorageAdminError("Deletion requires confirm=true", code="delete_not_confirmed")
    if not paths:
        raise StorageAdminError("At least one path is required for deletion", code="missing_paths")
    root, root_path = _require_local_root(root_id)
    base = _scope_base(root_id, root_path, tenant=tenant, project=project)
    deleted: List[Dict[str, Any]] = []
    for raw_path in paths:
        rel = _normalize_relpath(raw_path)
        if str(rel) == ".":
            raise StorageAdminError("Deleting the selected root is not supported", code="root_delete_refused")
        target = _target_under(base, raw_path)
        if not target.exists() and not target.is_symlink():
            deleted.append({"path": raw_path, "status": "missing"})
            continue
        entry = _entry_for(target, base=base)
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        deleted.append({"path": entry.path, "kind": entry.kind, "status": "deleted"})
    return {
        "root": asdict(root),
        "tenant": tenant,
        "project": project,
        "deleted": deleted,
        "deleted_count": sum(1 for item in deleted if item.get("status") == "deleted"),
        "generated_at": time.time(),
    }


def managed_folder_for_path(path: Optional[str]) -> Optional[str]:
    raw = str(path or "").strip()
    if not raw:
        return None
    try:
        managed_root = resolve_managed_bundles_root().resolve()
        candidate = Path(raw).expanduser().resolve()
        rel = candidate.relative_to(managed_root)
    except Exception:
        return None
    return rel.parts[0] if rel.parts else None


def summarize_registry_bundles(
    bundles: Dict[str, Any],
    *,
    default_bundle_id: Optional[str] = None,
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    active_managed_folders: set[str] = set()
    for bundle_id, entry in sorted((bundles or {}).items(), key=lambda item: item[0]):
        path = getattr(entry, "path", None)
        managed_folder = managed_folder_for_path(path)
        if managed_folder:
            active_managed_folders.add(managed_folder)
        items.append(
            {
                "id": bundle_id,
                "name": getattr(entry, "name", None),
                "description": getattr(entry, "description", None),
                "path": path,
                "module": getattr(entry, "module", None),
                "singleton": bool(getattr(entry, "singleton", False)),
                "version": getattr(entry, "version", None),
                "repo": getattr(entry, "repo", None),
                "ref": getattr(entry, "ref", None),
                "subdir": getattr(entry, "subdir", None),
                "git_commit": getattr(entry, "git_commit", None),
                "managed_folder": managed_folder,
                "default": bundle_id == default_bundle_id,
            }
        )
    return {
        "bundles": items,
        "active_managed_folders": sorted(active_managed_folders),
        "default_bundle_id": default_bundle_id,
        "count": len(items),
    }

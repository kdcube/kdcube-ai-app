from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from kdcube_ai_app.apps.chat.ingress.resolvers import auth_without_pressure
from kdcube_ai_app.auth.sessions import UserSession
from kdcube_ai_app.apps.chat.sdk.infra.control_plane.storage import (
    StorageAdminError,
    delete_storage_paths,
    export_storage_paths,
    list_storage_path,
    list_tenant_projects,
    storage_roots,
)


router = APIRouter()


class StorageExportRequest(BaseModel):
    root_id: str = Field(..., min_length=1)
    tenant: Optional[str] = None
    project: Optional[str] = None
    paths: List[str] = Field(default_factory=list)


class StorageDeleteRequest(BaseModel):
    root_id: str = Field(..., min_length=1)
    tenant: Optional[str] = None
    project: Optional[str] = None
    paths: List[str] = Field(default_factory=list)
    confirm: bool = False


def _raise_storage_error(exc: StorageAdminError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@router.get("/roots")
async def get_storage_roots(
    session: UserSession = Depends(auth_without_pressure()),
):
    del session
    return {"roots": storage_roots()}


@router.get("/tenants-projects")
async def get_storage_tenants_projects(
    root_id: str = Query(..., min_length=1),
    session: UserSession = Depends(auth_without_pressure()),
):
    del session
    try:
        return list_tenant_projects(root_id)
    except StorageAdminError as exc:
        _raise_storage_error(exc)


@router.get("/list")
async def get_storage_list(
    root_id: str = Query(..., min_length=1),
    tenant: Optional[str] = None,
    project: Optional[str] = None,
    path: Optional[str] = "",
    limit: int = Query(default=500, ge=1, le=2000),
    session: UserSession = Depends(auth_without_pressure()),
):
    del session
    try:
        return list_storage_path(
            root_id=root_id,
            tenant=tenant,
            project=project,
            path=path,
            limit=limit,
        )
    except StorageAdminError as exc:
        _raise_storage_error(exc)


@router.post("/export")
async def export_storage(payload: StorageExportRequest, session: UserSession = Depends(auth_without_pressure())):
    del session
    try:
        content, filename = export_storage_paths(
            root_id=payload.root_id,
            tenant=payload.tenant,
            project=payload.project,
            paths=payload.paths,
        )
    except StorageAdminError as exc:
        _raise_storage_error(exc)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/delete")
async def delete_storage(payload: StorageDeleteRequest, session: UserSession = Depends(auth_without_pressure())):
    del session
    try:
        return delete_storage_paths(
            root_id=payload.root_id,
            tenant=payload.tenant,
            project=payload.project,
            paths=payload.paths,
            confirm=payload.confirm,
        )
    except StorageAdminError as exc:
        _raise_storage_error(exc)

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The ``instr`` named-service namespace: stored instruction sets, governed.

Objects are versioned instruction sets from
:class:`~kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.store.AgenticInstructionsStore`;
the object ref IS the wiring ref — ``instr:custom:<id>[:<version>]`` — so what
an admin sees in this namespace is exactly what a descriptor or profile block
list wires to an agent.

Reads are open to the surface's callers. Writes (``object.upsert``,
``object.delete``) are ADMIN-gated here at the service layer: the store below
performs no role checks, and a widget must never be the only gate. Provenance
is first-class — every write records who did it, and records carry
``created_by``/``updated_by`` back to the caller.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.refs import (
    format_custom_ref,
    parse_custom_ref,
)
from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.store import (
    AgenticInstructionsStore,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.provider import (
    NamedServiceProvider,
    named_service_provider,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.types import (
    NamedServiceContext,
    NamedServiceRequest,
    NamedServiceResponse,
)

LOGGER = logging.getLogger(__name__)

INSTR_NAMESPACE = "instr"

_ADMIN_USER_TYPES = {"admin", "super_admin", "privileged"}
_ADMIN_ROLE_TOKENS = {"admin", "super_admin", "super-admin", "kdcube:role:super-admin"}

_INTRO = (
    "Stored instruction sets for agents. Each object is one versioned "
    "instruction set: an ordered list of composition tokens (predefined "
    "profile tokens, single instruction blocks, or literal text) saved under "
    "a slug id. Versions are immutable — an edit creates the next version — "
    "so a ref pinned to a version always resolves to the same content. The "
    "object ref (instr:custom:<id>[:<version>]) is the same ref an agent's "
    "instruction configuration wires."
)


def _is_admin(ctx: NamedServiceContext) -> bool:
    user_type = str(getattr(ctx, "user_type", "") or "").strip().lower()
    if user_type in _ADMIN_USER_TYPES:
        return True
    roles = {str(r or "").strip().lower() for r in (getattr(ctx, "roles", ()) or ())}
    return bool(roles & _ADMIN_ROLE_TOKENS)


def _author(ctx: NamedServiceContext) -> str:
    return str(getattr(ctx, "user_id", "") or getattr(ctx, "principal_id", "") or "").strip()


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _wire_object(record: Mapping[str, Any]) -> dict:
    instruction_id = str(record.get("instruction_id") or "")
    version = record.get("version")
    return {
        "ref": format_custom_ref(instruction_id, int(version) if version else None),
        "instruction_id": instruction_id,
        "version": version,
        "name": record.get("name") or "",
        "description": record.get("description") or "",
        "tags": [str(t) for t in (record.get("tags") or [])],
        "items": list(record.get("items") or []),
        "status": record.get("status") or "",
        "created_by": record.get("created_by") or "",
        "created_at": _iso(record.get("created_at")),
        "updated_by": record.get("updated_by") or "",
        "updated_at": _iso(record.get("updated_at")),
    }


@named_service_provider(
    provider_id="agentic-instructions",
    namespace=INSTR_NAMESPACE,
    refs=("instr:custom:<id>[:<version>]",),
    object_kinds=("instruction_set",),
    label="Agent instruction sets",
    description="Versioned, stored instruction sets wired to agents by ref.",
    intro=_INTRO,
)
class AgenticInstructionsNamedService(NamedServiceProvider):
    """CRUD over stored instruction sets; writes admin-gated at this layer."""

    def __init__(
        self,
        *,
        pg_pool: Any | None = None,
        pool_factory: Any | None = None,
        store_factory: Any | None = None,
    ) -> None:
        super().__init__()
        self._pg_pool = pg_pool
        self._pool_factory = pool_factory
        self._store_factory = store_factory

    def _store(self, ctx: NamedServiceContext) -> AgenticInstructionsStore:
        if self._store_factory is not None:
            return self._store_factory(ctx.tenant, ctx.project)
        pool = self._pg_pool
        if pool is None and self._pool_factory is not None:
            pool = self._pool_factory()
        return AgenticInstructionsStore(
            pg_pool=pool,
            tenant=ctx.tenant or "default",
            project=ctx.project or "default",
        )

    def _provider_identity(self) -> dict:
        return {
            "provider_id": self.spec.provider_id,
            "namespace": INSTR_NAMESPACE,
            "label": self.spec.label or "",
        }

    def _namespace(self, request: NamedServiceRequest) -> str:
        return request.namespace or INSTR_NAMESPACE

    def _deny_write(self, request: NamedServiceRequest) -> NamedServiceResponse:
        return NamedServiceResponse.error_response(
            code="admin_required",
            message=(
                "Creating, editing, or retiring stored instruction sets is an "
                "administrator operation."
            ),
            status=403,
            provider=self._provider_identity(),
            namespace=self._namespace(request),
            object_ref=request.object_ref,
        )

    # ── reads ─────────────────────────────────────────────────────────────

    async def provider_about(
        self, ctx: NamedServiceContext, request: NamedServiceRequest
    ) -> NamedServiceResponse:
        del ctx
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=self._namespace(request),
            extra={"intro": self.spec.intro},
        )

    async def object_list(
        self, ctx: NamedServiceContext, request: NamedServiceRequest
    ) -> NamedServiceResponse:
        filters = request.filters or {}
        store = self._store(ctx)
        records = await store.list_instructions(
            include_retired=bool(filters.get("include_retired")),
            q=str(filters.get("q") or ""),
            tags=filters.get("tags"),
        )
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=self._namespace(request),
            items=[_wire_object(r) for r in records],
        )

    async def object_get(
        self, ctx: NamedServiceContext, request: NamedServiceRequest
    ) -> NamedServiceResponse:
        ref = parse_custom_ref(request.object_ref or "")
        if ref is None:
            return NamedServiceResponse.error_response(
                code="instruction_ref_required",
                message="object.get requires object_ref instr:custom:<id>[:<version>].",
                status=400,
                provider=self._provider_identity(),
                namespace=self._namespace(request),
                object_ref=request.object_ref,
            )
        store = self._store(ctx)
        record = await store.get(ref.instruction_id, ref.version)
        if record is None:
            return NamedServiceResponse.error_response(
                code="instruction_not_found",
                message=f"No stored instruction resolves for {request.object_ref}.",
                status=404,
                provider=self._provider_identity(),
                namespace=self._namespace(request),
                object_ref=request.object_ref,
            )
        wire = _wire_object(record)
        versions = await store.list_versions(ref.instruction_id)
        wire["versions"] = [
            {
                "version": r.get("version"),
                "status": r.get("status"),
                "created_by": r.get("created_by"),
                "created_at": _iso(r.get("created_at")),
            }
            for r in versions
        ]
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=self._namespace(request),
            object_ref=wire["ref"],
            object=wire,
        )

    # ── writes (admin-gated) ──────────────────────────────────────────────

    async def object_upsert(
        self, ctx: NamedServiceContext, request: NamedServiceRequest
    ) -> NamedServiceResponse:
        if not _is_admin(ctx):
            return self._deny_write(request)
        payload = dict(request.payload or {})
        ref = parse_custom_ref(request.object_ref or "")
        instruction_id = str(
            payload.get("instruction_id") or (ref.instruction_id if ref else "")
        ).strip()
        author = _author(ctx)
        store = self._store(ctx)
        try:
            record = await store.save_version(
                instruction_id,
                name=str(payload.get("name") or "").strip(),
                description=str(payload.get("description") or "").strip(),
                items=payload.get("items"),
                author=author,
                tags=payload.get("tags"),
            )
        except ValueError as exc:
            return NamedServiceResponse.error_response(
                code="instruction_invalid",
                message=str(exc),
                status=400,
                provider=self._provider_identity(),
                namespace=self._namespace(request),
                object_ref=request.object_ref,
            )
        wire = _wire_object(record)
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=self._namespace(request),
            object_ref=wire["ref"],
            object=wire,
        )

    async def object_delete(
        self, ctx: NamedServiceContext, request: NamedServiceRequest
    ) -> NamedServiceResponse:
        if not _is_admin(ctx):
            return self._deny_write(request)
        ref = parse_custom_ref(request.object_ref or "")
        if ref is None:
            return NamedServiceResponse.error_response(
                code="instruction_ref_required",
                message="object.delete requires object_ref instr:custom:<id>[:<version>].",
                status=400,
                provider=self._provider_identity(),
                namespace=self._namespace(request),
                object_ref=request.object_ref,
            )
        store = self._store(ctx)
        retired = await store.retire(ref.instruction_id, ref.version, author=_author(ctx))
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=self._namespace(request),
            object_ref=request.object_ref,
            attrs={"retired": retired},
        )


__all__ = ["AgenticInstructionsNamedService", "INSTR_NAMESPACE"]

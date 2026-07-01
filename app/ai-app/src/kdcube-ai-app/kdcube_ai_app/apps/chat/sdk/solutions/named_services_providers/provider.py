# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Mapping, Sequence

from .types import (
    NamedServiceContext,
    NamedServiceProviderSpec,
    NamedServiceRequest,
    NamedServiceResponse,
    build_default_operations,
)

LOGGER = logging.getLogger("kdcube.sdk.named_services.provider")

# Uniform batch get: a single object.get carrying a list of refs
# (filters.refs / filters.object_refs) fans out to the provider's single-object
# object.get and returns the objects as items. Handled once here so EVERY provider
# (mem, task, conv, canvas, ...) supports batch get identically — providers only
# ever implement single-object object.get.
BATCH_GET_MAX = 50
_BATCH_GET_KEYS = ("refs", "object_refs")


def batch_get_refs(request: NamedServiceRequest) -> list[str] | None:
    """Extract the batch ref list from an object.get request, or None if single.

    Returns a de-duplicated, order-preserving list of ref strings when
    filters.refs (or filters.object_refs) is present (even if empty), else None.
    """
    filters = request.filters or {}
    raw = None
    for key in _BATCH_GET_KEYS:
        if key in filters and filters.get(key) is not None:
            raw = filters.get(key)
            break
    if raw is None:
        return None
    values = list(raw) if isinstance(raw, (list, tuple)) else [raw]
    seen: set[str] = set()
    refs: list[str] = []
    for value in values:
        ref = str(value or "").strip()
        if ref and ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def named_service_provider(
    *,
    provider_id: str,
    bundle_id: str | None = None,
    namespace: str | None = None,
    namespaces: Sequence[str] = (),
    refs: Sequence[str] = (),
    object_kinds: Sequence[str] = (),
    search_scopes: Sequence[Any] = (),
    operations: Mapping[str, Any] | None = None,
    label: str | None = None,
    description: str | None = None,
    intro: str = "",
    metadata: Mapping[str, Any] | None = None,
):
    """Attach named service provider metadata to a class or factory.

    Runtime loader integration is intentionally separate. This decorator only
    provides stable metadata that a bundle or registry can inspect.
    """

    spec = NamedServiceProviderSpec(
        provider_id=provider_id,
        bundle_id=bundle_id,
        namespace=namespace,
        namespaces=tuple(namespaces or ()),
        refs=tuple(refs or ()),
        object_kinds=tuple(object_kinds or ()),
        search_scopes=tuple(search_scopes or ()),
        operations=dict(operations or build_default_operations()),
        label=label,
        description=description,
        intro=str(intro or "").strip(),
        metadata=dict(metadata or {}),
    )

    def decorate(target):
        setattr(target, "__kdcube_named_service_provider__", spec)
        return target

    return decorate


class NamedServiceProvider:
    """Base class for async named service providers.

    Providers may override ``dispatch`` directly, or implement async methods
    named after operations, for example ``object_search`` or ``object_action``.
    """

    spec: NamedServiceProviderSpec

    def __init__(self, spec: NamedServiceProviderSpec | None = None) -> None:
        inferred = spec or getattr(self, "__kdcube_named_service_provider__", None)
        if inferred is None:
            inferred = NamedServiceProviderSpec(
                provider_id=self.__class__.__name__,
                operations=build_default_operations(),
            )
        self.spec = inferred

    async def dispatch(
        self,
        ctx: NamedServiceContext,
        request: NamedServiceRequest,
    ) -> NamedServiceResponse | Mapping[str, Any]:
        # Uniform batch get: object.get + a list of refs -> fan out to single get.
        if request.operation == "object.get":
            batch_refs = batch_get_refs(request)
            if batch_refs is not None:
                return await self._dispatch_batch_get(ctx, request, batch_refs)
        method_name = request.operation.replace(".", "_")
        method = getattr(self, method_name, None)
        if method is None:
            LOGGER.warning(
                "Named-service provider operation missing: provider=%s namespace=%s operation=%s object_ref=%s",
                self.spec.provider_id,
                request.namespace,
                request.operation,
                request.object_ref or "",
            )
            return NamedServiceResponse.error_response(
                code="named_service_operation_not_supported",
                message=f"Provider does not implement {request.operation}",
                status=404,
                provider=self.provider_identity(),
                namespace=request.namespace,
                object_ref=request.object_ref,
            )
        LOGGER.info(
            "Named-service provider dispatch start: provider=%s namespace=%s operation=%s object_ref=%s user_type=%s user_id=%s",
            self.spec.provider_id,
            request.namespace,
            request.operation,
            request.object_ref or "",
            ctx.user_type or "",
            ctx.user_id or "",
        )
        result = method(ctx, request)
        if not hasattr(result, "__await__"):
            raise TypeError(f"Named service provider method {method_name} must be async")
        response = await result
        ok = response.ok if isinstance(response, NamedServiceResponse) else bool(response.get("ok")) if isinstance(response, Mapping) else True
        LOGGER.info(
            "Named-service provider dispatch complete: provider=%s namespace=%s operation=%s object_ref=%s ok=%s",
            self.spec.provider_id,
            request.namespace,
            request.operation,
            request.object_ref or "",
            ok,
        )
        return response

    async def _dispatch_batch_get(
        self,
        ctx: NamedServiceContext,
        request: NamedServiceRequest,
        refs: list[str],
    ) -> NamedServiceResponse:
        object_get = getattr(self, "object_get", None)
        if object_get is None:
            return NamedServiceResponse.error_response(
                code="named_service_operation_not_supported",
                message="Provider does not implement object.get",
                status=404,
                provider=self.provider_identity(),
                namespace=request.namespace,
            )
        if not refs:
            return NamedServiceResponse.error_response(
                code="object_refs_required",
                message="Batch object.get requires filters.refs: a non-empty list of object refs.",
                status=400,
                provider=self.provider_identity(),
                namespace=request.namespace,
            )
        capped = refs[:BATCH_GET_MAX]
        base_filters = {k: v for k, v in (request.filters or {}).items() if k not in _BATCH_GET_KEYS}
        items: list[Any] = []
        missing: list[str] = []
        for ref in capped:
            sub_request = dataclasses.replace(
                request, object_ref=ref, object_id=None, filters=dict(base_filters),
            )
            resp = await object_get(ctx, sub_request)
            obj: Any = None
            if isinstance(resp, NamedServiceResponse):
                obj = resp.object or None if resp.ok else None
            elif isinstance(resp, Mapping) and resp.get("ok"):
                ret = resp.get("ret")
                obj = ret.get("object") if isinstance(ret, Mapping) else None
            if obj:
                items.append(obj)
            else:
                missing.append(ref)
        extra: dict[str, Any] = {"count": len(items), "requested": len(capped)}
        if missing:
            extra["missing"] = missing
        if len(refs) > BATCH_GET_MAX:
            extra["truncated"] = len(refs) - BATCH_GET_MAX
        LOGGER.info(
            "Named-service batch get: provider=%s namespace=%s requested=%s returned=%s missing=%s",
            self.spec.provider_id,
            request.namespace,
            len(capped),
            len(items),
            len(missing),
        )
        return NamedServiceResponse.ok_response(
            provider=self.provider_identity(),
            namespace=request.namespace,
            items=items,
            extra=extra,
        )

    def provider_identity(self) -> dict[str, Any]:
        return {
            "provider_id": self.spec.provider_id,
            "bundle_id": self.spec.bundle_id,
        }

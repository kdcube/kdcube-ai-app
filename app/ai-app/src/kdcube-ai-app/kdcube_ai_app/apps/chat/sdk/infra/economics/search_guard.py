# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""Economics support for semantic search.

Semantic search runs a (cheap but non-zero) embedder call per query. The
preferred integration is to pass `EconomicSearchModelService` to the searchable
component as its `model_service`. The component calls `embed_search_query(...)`;
the facade reserves, binds accounting, runs the underlying embedder, and settles
the embedding call at the service boundary. If the facade is entered inside
another active `EconomicsGuard` for a local composite flow, that inner guard
degrades to verify-only and the active guard settles the tracked event.

`make_semantic_search_guard(...)` remains as a legacy verify-only predicate for
older components that still expose a separate `semantic_guard` hook.

The reservation estimate is grounded in the live price table (text-embedding-3-small
= $0.02 / 1M tokens), sized to the query — pennies-to-fractions, enough for the
feasibility/quota/funding check.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional, Sequence
from uuid import uuid4

from kdcube_ai_app.apps.chat.sdk.infra.economics.enforcement import (
    EconomicsGuard,
    EconomicsEstimate,
    EconomicsSubject,
    FlowPolicy,
    economic_preflight,
)
from kdcube_ai_app.apps.chat.sdk.infra.economics.policy import EconomicsLimitException
from kdcube_ai_app.infra.accounting.usage import (
    embedding_price_usd_per_1m,
    estimate_embedding_tokens,
    quote_embedding_usd,
)

DEFAULT_EMBEDDING_PROVIDER = "openai"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
_MIN_RESERVATION_USD = 1e-6
logger = logging.getLogger(__name__)


def embedding_rate_per_1m(
    model: str = DEFAULT_EMBEDDING_MODEL,
    *,
    provider: str = DEFAULT_EMBEDDING_PROVIDER,
) -> float:
    """USD per 1M embedding tokens for provider/model, read from the price table."""
    rate = embedding_price_usd_per_1m(provider=provider, model=model)
    if rate > 0:
        return rate
    if provider == DEFAULT_EMBEDDING_PROVIDER and model == DEFAULT_EMBEDDING_MODEL:
        return 0.02
    return 0.0


def embedding_reservation_usd(
    query: str,
    *,
    model: str = DEFAULT_EMBEDDING_MODEL,
    provider: str = DEFAULT_EMBEDDING_PROVIDER,
) -> float:
    """Estimated USD to embed one query: price-table rate × shared token estimate."""
    return embedding_reservation_usd_for_texts(
        [query],
        provider=provider,
        model=model,
    )


def embedding_reservation_usd_for_texts(
    texts: Sequence[str],
    *,
    model: str = DEFAULT_EMBEDDING_MODEL,
    provider: str = DEFAULT_EMBEDDING_PROVIDER,
) -> float:
    """Estimated USD to embed a batch, floored to a non-zero feasibility amount."""
    cost = quote_embedding_usd(
        [str(text or "") for text in texts],
        provider=provider,
        model=model,
        min_tokens_per_text=16,
    )
    return max(_MIN_RESERVATION_USD, float(cost or 0.0))


def make_semantic_search_guard(
    entrypoint: Any,
    *,
    subject: EconomicsSubject,
    provider: str = DEFAULT_EMBEDDING_PROVIDER,
    model: str = DEFAULT_EMBEDDING_MODEL,
    flow: str = "search.semantic",
    policy: Optional[FlowPolicy] = None,
) -> Callable[[str], Awaitable[bool]]:
    """Build the async legacy `semantic_guard` predicate for a search index.

    Returns an async `(query) -> bool`: True when the user may incur the embed
    (feasibility verified via `economic_preflight`), False on `EconomicsLimitException`
    so the index degrades to lexical. New components should prefer
    `EconomicSearchModelService`.
    """
    flow_policy = policy or FlowPolicy(enforce_concurrency=False, emit_user_events=False)

    async def guard(query: str) -> bool:
        try:
            await economic_preflight(
                entrypoint,
                subject=subject,
                estimate=EconomicsEstimate(
                    reservation_usd=embedding_reservation_usd(
                        query,
                        provider=provider,
                        model=model,
                    ),
                    min_tokens=max(1, estimate_embedding_tokens(query, min_tokens=16)),
                ),
                flow=flow,
                policy=flow_policy,
            )
            return True
        except EconomicsLimitException:
            return False

    return guard


class EconomicSearchModelService:
    """Economics-aware model-service facade for searchable components.

    Components receive this as their `model_service` and only call model-service
    methods. They do not compose economics guards, provider/model pricing, or
    settlement scopes themselves.
    """

    def __init__(
        self,
        *,
        entrypoint: Any,
        model_service: Any,
        subject: EconomicsSubject,
        provider: str = DEFAULT_EMBEDDING_PROVIDER,
        model: str = DEFAULT_EMBEDDING_MODEL,
        default_flow: str = "search.semantic",
        policy: Optional[FlowPolicy] = None,
    ) -> None:
        self.entrypoint = entrypoint
        self.model_service = model_service
        self.subject = subject
        self.provider = provider
        self.model = model
        self.default_flow = default_flow
        self.policy = policy or FlowPolicy(enforce_concurrency=False, emit_user_events=False)

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Document/index embeddings. Accounting comes from the underlying service."""
        return await self.model_service.embed_texts(list(texts))

    async def embed_search_query(self, query: str, *, flow: Optional[str] = None) -> list[float] | None:
        """Query embedding with economics around the actual model call.

        This reserves, binds accounting, runs the embedding, and settles at the
        service boundary. Inside another active `EconomicsGuard`, the guard
        degrades to verify-only and the active guard settles the tracked event.
        """
        text = str(query or "").strip()
        if not text:
            return None
        flow_name = flow or self.default_flow
        reservation_usd = embedding_reservation_usd(
            text,
            provider=self.provider,
            model=self.model,
        )
        scope_id = f"{flow_name.replace('.', '_')}_{uuid4().hex}"
        try:
            async with EconomicsGuard(
                self.entrypoint,
                subject=self.subject,
                scope_id=scope_id,
                flow=flow_name,
                estimate=EconomicsEstimate(
                    reservation_usd=reservation_usd,
                    min_tokens=max(1, estimate_embedding_tokens(text, min_tokens=16)),
                ),
                policy=self.policy,
            ) as decision:
                if bool(getattr(decision, "nested", False)):
                    from kdcube_ai_app.infra import accounting as acct

                    async with acct.with_accounting(
                        flow_name,
                        request_id=scope_id,
                        metadata={
                            "flow": flow_name,
                            "scope_id": scope_id,
                        },
                    ):
                        vectors = await self.model_service.embed_texts([text])
                        return vectors[0] if vectors else None
                vectors = await self.model_service.embed_texts([text])
                return vectors[0] if vectors else None
        except EconomicsLimitException as exc:
            logger.info(
                "[economics.enforcement] semantic search denied; degrading to lexical flow=%s scope_id=%s provider=%s model=%s code=%s",
                flow_name,
                scope_id,
                self.provider,
                self.model,
                getattr(exc, "code", "rate_limited"),
            )
            return None


__all__ = [
    "make_semantic_search_guard",
    "EconomicSearchModelService",
    "embedding_reservation_usd",
    "embedding_reservation_usd_for_texts",
    "embedding_rate_per_1m",
    "DEFAULT_EMBEDDING_PROVIDER",
    "DEFAULT_EMBEDDING_MODEL",
]

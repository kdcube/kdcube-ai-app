# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Tests for SDK-owned conversation export.

Export domain logic (request normalization/validation, the pool guard, and
limiting) now lives in `sdk.solutions.conversation.export`. The bundle MCP
surface only wraps it. These tests drive the SDK classes directly; the datasource
call is stubbed so no database is required.
"""

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.conversation import export as export_mod
from kdcube_ai_app.apps.chat.sdk.solutions.conversation.export import (
    DEFAULT_EXPORT_LIMIT,
    MAX_EXPORT_LIMIT,
    ConversationExportRequest,
    ConversationExportService,
)


def test_request_normalization_and_limit_clamping():
    req = ConversationExportRequest(since="  2026-01-01  ", tenant=" t ", project=" p ", limit=0)
    assert req.normalized_since == "2026-01-01"
    assert req.normalized_tenant == "t"
    assert req.normalized_project == "p"
    # limit 0 falls back to the default; over-max clamps to MAX.
    assert req.normalized_limit == DEFAULT_EXPORT_LIMIT
    assert ConversationExportRequest(limit=10_000).normalized_limit == MAX_EXPORT_LIMIT
    assert ConversationExportRequest(limit=5).normalized_limit == 5


def test_validate_requires_tenant_and_project_together():
    assert ConversationExportRequest(tenant="t").validate() == "tenant and project must be provided together"
    assert ConversationExportRequest(project="p").validate() == "tenant and project must be provided together"
    assert ConversationExportRequest().validate() is None
    assert ConversationExportRequest(tenant="t", project="p").validate() is None


@pytest.mark.asyncio
async def test_export_without_pool_returns_error():
    service = ConversationExportService(pg_pool=None)
    result = await service.export(ConversationExportRequest())
    assert result == {"ok": False, "error": "database pool unavailable"}


@pytest.mark.asyncio
async def test_export_reports_validation_error():
    service = ConversationExportService(pg_pool=object())
    result = await service.export(ConversationExportRequest(tenant="t"))
    assert result["ok"] is False
    assert result["error"] == "tenant and project must be provided together"


@pytest.mark.asyncio
async def test_export_limits_and_reports_totals(monkeypatch):
    # Stub the datasource-backed fetch so no DB is touched; the service owns the
    # limiting/counting contract on top of it.
    records = [{"conversation_id": f"c{i}"} for i in range(7)]

    async def _fake_export_conversations(datasource, *, since=None, tenant=None, project=None):
        del datasource, since, tenant, project
        return records

    monkeypatch.setattr(export_mod, "export_conversations", _fake_export_conversations)

    service = ConversationExportService(pg_pool=object())
    result = await service.export(ConversationExportRequest(limit=5))
    assert result["ok"] is True
    assert result["total_available"] == 7
    assert result["count"] == 5
    assert result["limited"] is True
    assert result["conversations"] == records[:5]


@pytest.mark.asyncio
async def test_export_not_limited_when_within_bound(monkeypatch):
    records = [{"conversation_id": "c1"}, {"conversation_id": "c2"}]

    async def _fake_export_conversations(datasource, *, since=None, tenant=None, project=None):
        del datasource, since, tenant, project
        return records

    monkeypatch.setattr(export_mod, "export_conversations", _fake_export_conversations)

    service = ConversationExportService(pg_pool=object())
    result = await service.export(ConversationExportRequest(limit=100))
    assert result["ok"] is True
    assert result["total_available"] == 2
    assert result["count"] == 2
    assert result["limited"] is False

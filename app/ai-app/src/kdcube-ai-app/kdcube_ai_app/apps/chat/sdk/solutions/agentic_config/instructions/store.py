# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""The versioned store for custom instruction sets (tenant/project scoped).

One row per (instruction_id, version). **Versions are immutable** — editing
saves the next version, so an agent pinned to ``instr:custom:<id>:<n>`` never
shifts. Rows carry provenance (who created; who retired). Writes are
admin-gated at the SERVICE layer — this module is storage only and performs no
role checks.

The table lives in the project schema
(``ops/deployment/sql/chatbot/deploy-kdcube-proj-schema.sql``); the store also
carries the same DDL for self-migration in scripts/tests, mirroring other SDK
context stores. ``items`` (the ordered composer-token list) is the structural
truth and lives in the DB; the ``body_ref`` column is reserved for offloading
oversized literal bodies into bundle storage
(``docs/sdk/bundle/bundle-storage-and-cache-README.md``) when sizes demand it.

The store expects an asyncpg-like pool and does not own transactions beyond
single statements.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from kdcube_ai_app.apps.chat.sdk.solutions.agentic_config.instructions.refs import (
    is_valid_instruction_id,
)

LOGGER = logging.getLogger(__name__)

INSTRUCTIONS_TABLE = "agentic_instructions"

STATUS_ACTIVE = "active"
STATUS_RETIRED = "retired"


def _safe_identifier(value: str, *, fallback: str = "kdcube_default_default") -> str:
    raw = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "")).strip("_").lower()
    if not raw:
        raw = fallback
    if raw[0].isdigit():
        raw = f"_{raw}"
    return raw


def _schema_from_scope(tenant: str, project: str) -> str:
    tenant_part = _safe_identifier(tenant or "default", fallback="default")
    project_part = _safe_identifier(project or "default", fallback="default")
    schema = f"{tenant_part}_{project_part}"
    if not schema.startswith("kdcube_"):
        schema = f"kdcube_{schema}"
    return schema


def _normalized_items(items: Any) -> list[str]:
    if isinstance(items, str):
        items = [items]
    if not isinstance(items, (list, tuple)):
        raise ValueError("items must be a list of instruction tokens")
    out = [str(v or "").strip() for v in items]
    out = [v for v in out if v]
    if not out:
        raise ValueError("items must contain at least one non-empty token")
    return out


def _record(row: Any) -> dict:
    data = dict(row)
    items = data.get("items")
    if isinstance(items, str):
        try:
            data["items"] = json.loads(items)
        except Exception:
            data["items"] = []
    return data


class AgenticInstructionsStore:
    """CRUD over the ``agentic_instructions`` table.

    ``pg_pool`` is the processor's shared asyncpg pool in production;
    ``init_from_settings()`` builds an owned pool for scripts/tests.
    """

    def __init__(
        self,
        *,
        pg_pool: Any | None = None,
        tenant: str | None = None,
        project: str | None = None,
        schema: str | None = None,
    ) -> None:
        self._pool = pg_pool
        self._owns_pool = False
        self.schema = _safe_identifier(schema) if schema else _schema_from_scope(
            tenant or "default", project or "default"
        )

    async def init_from_settings(self) -> None:
        if self._pool is not None:
            return
        import asyncpg

        from kdcube_ai_app.apps.chat.sdk.config import get_settings, resolve_asyncpg_ssl

        settings = get_settings()
        self._pool = await asyncpg.create_pool(
            host=settings.PGHOST,
            port=settings.PGPORT,
            user=settings.PGUSER,
            password=settings.PGPASSWORD,
            database=settings.PGDATABASE,
            ssl=resolve_asyncpg_ssl(settings),
        )
        self._owns_pool = True

    async def close(self) -> None:
        if self._pool is not None and self._owns_pool:
            await self._pool.close()
        self._pool = None

    def _require_pool(self) -> Any:
        if self._pool is None:
            raise RuntimeError(
                "AgenticInstructionsStore requires pg_pool or init_from_settings()"
            )
        return self._pool

    # ── schema ────────────────────────────────────────────────────────────

    def _schema_statements(self) -> list[str]:
        schema = self.schema
        return [
            f"CREATE SCHEMA IF NOT EXISTS {schema}",
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.{INSTRUCTIONS_TABLE} (
                instruction_id TEXT NOT NULL,
                version INT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                items JSONB NOT NULL,
                body_ref TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '{STATUS_ACTIVE}',
                created_by TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_by TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ,
                PRIMARY KEY (instruction_id, version)
            )
            """,
            f"""
            CREATE INDEX IF NOT EXISTS idx_{INSTRUCTIONS_TABLE}_status
            ON {schema}.{INSTRUCTIONS_TABLE} (instruction_id, status)
            """,
        ]

    async def ensure_schema(self) -> None:
        pool = self._require_pool()
        async with pool.acquire() as con:
            for statement in self._schema_statements():
                await con.execute(statement)

    # ── writes (admin-gated at the service layer) ─────────────────────────

    async def save_version(
        self,
        instruction_id: str,
        *,
        name: str,
        items: Any,
        author: str,
        description: str = "",
    ) -> dict:
        """Insert the next version for ``instruction_id`` (1 for a new id).

        Immutable-version contract: this NEVER updates an existing row.
        """
        instruction_id = str(instruction_id or "").strip().lower()
        if not is_valid_instruction_id(instruction_id):
            raise ValueError(
                "instruction_id must be a slug of lowercase alphanumerics and dashes"
            )
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("name is required")
        clean_author = str(author or "").strip()
        if not clean_author:
            raise ValueError("author is required (provenance)")
        clean_items = _normalized_items(items)
        pool = self._require_pool()
        async with pool.acquire() as con:
            row = await con.fetchrow(
                f"""
                INSERT INTO {self.schema}.{INSTRUCTIONS_TABLE}
                    (instruction_id, version, name, description, items, created_by)
                VALUES (
                    $1,
                    COALESCE((
                        SELECT MAX(version) FROM {self.schema}.{INSTRUCTIONS_TABLE}
                        WHERE instruction_id = $1
                    ), 0) + 1,
                    $2, $3, $4::jsonb, $5
                )
                RETURNING *
                """,
                instruction_id,
                clean_name,
                str(description or "").strip(),
                json.dumps(clean_items, ensure_ascii=False),
                clean_author,
            )
        return _record(row)

    async def retire(
        self,
        instruction_id: str,
        version: Optional[int] = None,
        *,
        author: str,
    ) -> int:
        """Retire one version, or every version of an id when version is None.

        The only mutation on existing rows — a status flip carrying who did it.
        Returns the number of rows retired.
        """
        clean_author = str(author or "").strip()
        if not clean_author:
            raise ValueError("author is required (provenance)")
        instruction_id = str(instruction_id or "").strip().lower()
        pool = self._require_pool()
        params: list[Any] = [instruction_id, STATUS_RETIRED, clean_author]
        version_clause = ""
        if version is not None:
            version_clause = "AND version = $4"
            params.append(int(version))
        async with pool.acquire() as con:
            result = await con.execute(
                f"""
                UPDATE {self.schema}.{INSTRUCTIONS_TABLE}
                SET status = $2, updated_by = $3, updated_at = now()
                WHERE instruction_id = $1 AND status <> $2 {version_clause}
                """,
                *params,
            )
        try:
            return int(str(result).rsplit(" ", 1)[-1])
        except Exception:
            return 0

    # ── reads ─────────────────────────────────────────────────────────────

    async def get(self, instruction_id: str, version: Optional[int] = None) -> Optional[dict]:
        """One version, or the latest ACTIVE version when ``version`` is None.

        A pinned version is returned regardless of status: an agent explicitly
        wired to ``instr:custom:<id>:<n>`` keeps working after later versions
        retire; only the unpinned "latest" read filters to active.
        """
        instruction_id = str(instruction_id or "").strip().lower()
        if not instruction_id:
            return None
        pool = self._require_pool()
        async with pool.acquire() as con:
            if version is not None:
                row = await con.fetchrow(
                    f"""
                    SELECT * FROM {self.schema}.{INSTRUCTIONS_TABLE}
                    WHERE instruction_id = $1 AND version = $2
                    """,
                    instruction_id,
                    int(version),
                )
            else:
                row = await con.fetchrow(
                    f"""
                    SELECT * FROM {self.schema}.{INSTRUCTIONS_TABLE}
                    WHERE instruction_id = $1 AND status = $2
                    ORDER BY version DESC LIMIT 1
                    """,
                    instruction_id,
                    STATUS_ACTIVE,
                )
        return _record(row) if row is not None else None

    async def fetch_items(
        self, instruction_id: str, version: Optional[int] = None
    ) -> Optional[list[str]]:
        record = await self.get(instruction_id, version)
        if record is None:
            return None
        items = record.get("items")
        return [str(v or "") for v in items] if isinstance(items, list) else None

    async def list_instructions(self, *, include_retired: bool = False) -> list[dict]:
        """Latest version per id (latest ACTIVE unless ``include_retired``)."""
        pool = self._require_pool()
        status_clause = "" if include_retired else f"WHERE status = '{STATUS_ACTIVE}'"
        async with pool.acquire() as con:
            rows = await con.fetch(
                f"""
                SELECT DISTINCT ON (instruction_id) *
                FROM {self.schema}.{INSTRUCTIONS_TABLE}
                {status_clause}
                ORDER BY instruction_id, version DESC
                """
            )
        return [_record(row) for row in rows]

    async def list_versions(self, instruction_id: str) -> list[dict]:
        instruction_id = str(instruction_id or "").strip().lower()
        pool = self._require_pool()
        async with pool.acquire() as con:
            rows = await con.fetch(
                f"""
                SELECT * FROM {self.schema}.{INSTRUCTIONS_TABLE}
                WHERE instruction_id = $1
                ORDER BY version DESC
                """,
                instruction_id,
            )
        return [_record(row) for row in rows]


__all__ = [
    "AgenticInstructionsStore",
    "INSTRUCTIONS_TABLE",
    "STATUS_ACTIVE",
    "STATUS_RETIRED",
]

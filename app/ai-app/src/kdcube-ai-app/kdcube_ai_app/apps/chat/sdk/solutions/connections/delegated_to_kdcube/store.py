# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Connection Hub-owned delegated to KDCube storage.

Connected account metadata lives in user properties. Provider credentials live
in user secrets. Callers should use the broker/client, not these keys directly.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Iterable

from kdcube_ai_app.apps.chat.sdk import config as sdk_config
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube.models import (
    CONNECTION_HUB_BUNDLE_ID,
    STATUS_REVOKED,
    ConnectedAccount,
    as_str,
    utc_now,
)

ACCOUNT_INDEX_KEY = "delegated_to_kdcube.account_index"
ACCOUNT_KEY_PREFIX = "delegated_to_kdcube.accounts"
CREDENTIAL_KEY_PREFIX = "delegated_to_kdcube.credentials"


def safe_segment(raw: str, *, fallback: str = "item") -> str:
    value = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(raw or "")).strip("-")
    return value or fallback


def account_id_for(*, provider_id: str, connector_app_id: str = "", external_subject: str = "", workspace: str = "") -> str:
    seed = "|".join([provider_id, connector_app_id, workspace, external_subject])
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16] if seed.strip("|") else uuid.uuid4().hex[:16]
    return f"{safe_segment(provider_id, fallback='provider')}_{digest}"


def credential_id_for(account_id: str) -> str:
    return f"cred_{hashlib.sha256(as_str(account_id).encode('utf-8')).hexdigest()[:24]}"


class DelegatedToKdcubeStore:
    def __init__(self, *, user_id: str, bundle_id: str = CONNECTION_HUB_BUNDLE_ID) -> None:
        self.user_id = as_str(user_id)
        if not self.user_id:
            raise ValueError("user_id is required for delegated to KDCube storage")
        self.bundle_id = as_str(bundle_id) or CONNECTION_HUB_BUNDLE_ID

    # ── user prop helpers ───────────────────────────────────────────────────

    def _prop(self, key: str, default: Any = None) -> Any:
        return sdk_config.get_user_prop(key, user_id=self.user_id, bundle_id=self.bundle_id, default=default)

    def _set_prop(self, key: str, value: Any) -> None:
        sdk_config.set_user_prop(key, value, user_id=self.user_id, bundle_id=self.bundle_id)

    def _delete_prop(self, key: str) -> None:
        sdk_config.delete_user_prop(key, user_id=self.user_id, bundle_id=self.bundle_id)

    def _index(self) -> list[str]:
        raw = self._prop(ACCOUNT_INDEX_KEY, default=[])
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = []
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            value = as_str(item)
            if value and value not in seen:
                seen.add(value)
                out.append(value)
        return out

    def _write_index(self, account_ids: Iterable[str]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in account_ids:
            value = as_str(item)
            if value and value not in seen:
                seen.add(value)
                cleaned.append(value)
        self._set_prop(ACCOUNT_INDEX_KEY, cleaned)

    @staticmethod
    def account_prop_key(account_id: str) -> str:
        return f"{ACCOUNT_KEY_PREFIX}.{safe_segment(account_id, fallback='account')}"

    @staticmethod
    def credential_secret_key(credential_id: str) -> str:
        return f"{CREDENTIAL_KEY_PREFIX}.{safe_segment(credential_id, fallback='credential')}"

    # ── account metadata ────────────────────────────────────────────────────

    async def list_accounts(self, *, provider_id: str = "") -> list[ConnectedAccount]:
        wanted = as_str(provider_id)
        accounts: list[ConnectedAccount] = []
        for account_id in self._index():
            raw = self._prop(self.account_prop_key(account_id), default=None)
            if not isinstance(raw, dict):
                continue
            account = ConnectedAccount.from_dict(raw)
            if not account.account_id:
                continue
            if wanted and account.provider_id != wanted:
                continue
            accounts.append(account)
        return sorted(accounts, key=lambda item: (item.provider_id, item.display_name or item.account_id))

    async def get_account(self, account_id: str) -> ConnectedAccount | None:
        raw = self._prop(self.account_prop_key(account_id), default=None)
        if not isinstance(raw, dict):
            return None
        account = ConnectedAccount.from_dict(raw)
        return account if account.account_id else None

    async def upsert_account(self, account: ConnectedAccount) -> ConnectedAccount:
        account_id = as_str(account.account_id) or account_id_for(
            provider_id=account.provider_id,
            connector_app_id=account.connector_app_id,
            external_subject=account.external_subject,
            workspace=account.workspace,
        )
        now = utc_now()
        stored = ConnectedAccount(
            account_id=account_id,
            provider_id=account.provider_id,
            connector_app_id=account.connector_app_id,
            external_subject=account.external_subject,
            display_name=account.display_name,
            email=account.email,
            workspace=account.workspace,
            claims=account.claims,
            credential_id=account.credential_id or credential_id_for(account_id),
            status=account.status,
            connected_at=account.connected_at or now,
            updated_at=now,
            metadata=dict(account.metadata or {}),
        )
        self._set_prop(self.account_prop_key(account_id), stored.to_dict())
        self._write_index([*self._index(), account_id])
        return stored

    async def disconnect_account(self, account_id: str, *, delete_credential: bool = True) -> bool:
        existing = await self.get_account(account_id)
        if existing is None:
            return False
        self._delete_prop(self.account_prop_key(account_id))
        self._write_index([item for item in self._index() if item != existing.account_id])
        if delete_credential and existing.credential_id:
            await self.delete_credential(existing.credential_id)
        return True

    async def mark_revoked(self, account_id: str) -> ConnectedAccount | None:
        existing = await self.get_account(account_id)
        if existing is None:
            return None
        revoked = ConnectedAccount(
            account_id=existing.account_id,
            provider_id=existing.provider_id,
            connector_app_id=existing.connector_app_id,
            external_subject=existing.external_subject,
            display_name=existing.display_name,
            email=existing.email,
            workspace=existing.workspace,
            claims=existing.claims,
            credential_id=existing.credential_id,
            status=STATUS_REVOKED,
            connected_at=existing.connected_at,
            updated_at=utc_now(),
            metadata=dict(existing.metadata or {}),
        )
        self._set_prop(self.account_prop_key(account_id), revoked.to_dict())
        return revoked

    # ── credentials ─────────────────────────────────────────────────────────

    async def set_credential(self, credential_id: str, credential: dict[str, Any]) -> None:
        if not credential_id:
            raise ValueError("credential_id is required")
        await sdk_config.set_user_secret(
            self.credential_secret_key(credential_id),
            json.dumps(dict(credential or {}), sort_keys=True, ensure_ascii=True),
            user_id=self.user_id,
            bundle_id=self.bundle_id,
        )

    async def get_credential(self, credential_id: str) -> dict[str, Any]:
        if not credential_id:
            return {}
        raw = await sdk_config.get_secret(
            f"u:{self.credential_secret_key(credential_id)}",
            user_id=self.user_id,
            bundle_id=self.bundle_id,
        )
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return dict(parsed or {}) if isinstance(parsed, dict) else {}

    async def delete_credential(self, credential_id: str) -> None:
        if not credential_id:
            return
        await sdk_config.delete_user_secret(
            self.credential_secret_key(credential_id),
            user_id=self.user_id,
            bundle_id=self.bundle_id,
        )


__all__ = [
    "ACCOUNT_INDEX_KEY",
    "ACCOUNT_KEY_PREFIX",
    "CREDENTIAL_KEY_PREFIX",
    "DelegatedToKdcubeStore",
    "account_id_for",
    "credential_id_for",
    "safe_segment",
]

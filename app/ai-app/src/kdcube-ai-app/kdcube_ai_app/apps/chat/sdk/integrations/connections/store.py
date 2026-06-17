"""ConnectionStore — provider-neutral generalization of LinkedInAccountStore.

Invariants (unchanged from the LinkedIn implementation):
  - Account JSON holds metadata + `has_token` only — never tokens.
  - Tokens / refresh tokens live in the user-secret API, user-scoped.
  - `consume_oauth_state` verifies the signed `state` (carries `user_id`,
    `account_id`, `provider`, `app_id`, `source`) — single-use, anti-CSRF.
  - An account records the `app_id` of the client app it was connected through;
    idempotency is keyed by (provider, app_id, external_user_id, workspace).

Storage layout (faithful to LinkedIn, with provider folded in):
  <root>/connections/<safe_user_id>/accounts.json   (records carry "provider")
  <root>/connections/_oauth_states/<sha256(state)>.json
Listing can filter by provider.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import aiofiles
import aiofiles.os

try:
    from kdcube_ai_app.apps.chat.sdk.config import (
        delete_user_secret,
        get_secret,
        set_user_secret,
    )
except Exception:
    delete_user_secret = None  # type: ignore[assignment]
    get_secret = None  # type: ignore[assignment]
    set_user_secret = None  # type: ignore[assignment]


DEFAULT_BUNDLE_ID = "task-and-memo-app@1-0"
SCHEMA_VERSION = "connections-accounts.v1"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_segment(raw: str, *, fallback: str = "default") -> str:
    import re

    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(raw or "")).strip("-")
    return value or fallback


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_json(data: Mapping[str, Any]) -> str:
    return _b64url(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _unb64url_json(data: str) -> Dict[str, Any]:
    padded = data + ("=" * (-len(data) % 4))
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("state payload is invalid")
    return parsed


class ConnectionStore:
    def __init__(self, root: str | Path, *, user_id: str, bundle_id: str = DEFAULT_BUNDLE_ID, shared_tokens: bool = True):
        self.root = Path(root).resolve()
        self.user_id = str(user_id or "anonymous").strip() or "anonymous"
        self.bundle_id = str(bundle_id or DEFAULT_BUNDLE_ID).strip() or DEFAULT_BUNDLE_ID
        # Connections are a user-level hub: tokens are stored at USER scope
        # (`users.<user_id>.secrets…`, bundle_id=None) so any bundle acting for this
        # user can resolve them. Pass shared_tokens=False for the legacy per-bundle
        # scope (a bundle connecting only its own account).
        self._token_bundle_id = None if shared_tokens else self.bundle_id
        self.safe_user_id = _safe_segment(self.user_id, fallback="anonymous")
        self.connections_dir = self.root / "connections" / self.safe_user_id
        self.accounts_path = self.connections_dir / "accounts.json"
        self.states_dir = self.root / "connections" / "_oauth_states"
        self.connections_dir.mkdir(parents=True, exist_ok=True)
        self.states_dir.mkdir(parents=True, exist_ok=True)

    # ── accounts doc I/O ────────────────────────────────────────────────────

    def _empty_accounts(self) -> Dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "updated_at": _utc_now(), "accounts": []}

    async def _read_accounts_doc_async(self) -> Dict[str, Any]:
        if not self.accounts_path.exists():
            return self._empty_accounts()
        try:
            async with aiofiles.open(self.accounts_path, "r", encoding="utf-8") as fh:
                data = json.loads(await fh.read())
        except Exception:
            return self._empty_accounts()
        if not isinstance(data, dict):
            return self._empty_accounts()
        if not isinstance(data.get("accounts"), list):
            data["accounts"] = []
        return data

    async def _write_accounts_doc_async(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data["schema_version"] = SCHEMA_VERSION
        data["updated_at"] = _utc_now()
        tmp = self.accounts_path.with_suffix(".json.tmp")
        async with aiofiles.open(tmp, "w", encoding="utf-8") as fh:
            await fh.write(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
        tmp.replace(self.accounts_path)
        return data

    async def list_accounts_async(self, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        wanted = str(provider or "").strip()
        rows: List[Dict[str, Any]] = []
        for raw in (await self._read_accounts_doc_async()).get("accounts") or []:
            if not isinstance(raw, dict):
                continue
            account_id = str(raw.get("account_id") or "").strip()
            if not account_id:
                continue
            if wanted and str(raw.get("provider") or "").strip() != wanted:
                continue
            item = dict(raw)
            item["has_token"] = bool(await self.get_tokens_async(account_id))
            rows.append(item)
        return sorted(rows, key=lambda item: str(item.get("display_name") or item.get("account_id") or ""))

    async def upsert_account_async(self, account: Mapping[str, Any]) -> Dict[str, Any]:
        now = _utc_now()
        provider = str(account.get("provider") or "").strip()
        # app_id = the client app this account was connected THROUGH (which OAuth
        # application client's credentials apply for refresh). Part of the
        # idempotency key, so connecting the same user via two client apps yields
        # two accounts.
        app_id = str(account.get("app_id") or "").strip()
        # external_user_id = the connected USER's id in the external system (Slack
        # user, LinkedIn `sub`, Gmail address). `workspace` is a separate org/team
        # dimension; the same user across two workspaces is two accounts.
        external_user_id = str(
            account.get("external_user_id") or account.get("external_id") or account.get("person_id") or ""
        ).strip()
        workspace = str(account.get("workspace") or "").strip()
        account_id = str(account.get("account_id") or "").strip()
        if not account_id:
            # app_id is part of the idempotency key, so two client apps for the
            # same (workspace, user) are distinct accounts — seed it in too.
            seed = ":".join(p for p in (app_id, workspace, external_user_id) if p) or uuid.uuid4().hex
            prefix = provider or "connection"
            account_id = f"{prefix}_{_safe_segment(seed, fallback='account')}"
        row = {
            "account_id": account_id,
            "provider": provider,
            "app_id": app_id,
            "external_user_id": external_user_id,
            "workspace": workspace,
            "email": str(account.get("email") or "").strip(),
            "display_name": str(account.get("display_name") or external_user_id or account_id).strip(),
            "status": str(account.get("status") or "connected").strip().lower() or "connected",
            "scope": list(account.get("scope") or []),
            "connected_at": str(account.get("connected_at") or now),
            "updated_at": now,
            "last_error": str(account.get("last_error") or "").strip(),
        }
        data = await self._read_accounts_doc_async()
        rows = [item for item in data.get("accounts") or [] if isinstance(item, dict)]
        existing = next((item for item in rows if str(item.get("account_id") or "") == account_id), None)
        if existing is None and external_user_id:
            existing = next(
                (
                    item
                    for item in rows
                    if str(item.get("external_user_id") or item.get("external_id") or item.get("person_id") or "") == external_user_id
                    and str(item.get("workspace") or "") == workspace
                    and str(item.get("provider") or "") == provider
                    and str(item.get("app_id") or "") == app_id
                ),
                None,
            )
        if existing:
            row["account_id"] = str(existing.get("account_id") or account_id)
            existing.update({key: value for key, value in row.items() if value not in (None, "") or key in {"last_error"}})
            row = existing
        else:
            rows.append(row)
        data["accounts"] = rows
        await self._write_accounts_doc_async(data)
        return dict(row)

    async def delete_account_async(self, account_id: str) -> bool:
        wanted = str(account_id or "").strip()
        data = await self._read_accounts_doc_async()
        rows = [item for item in data.get("accounts") or [] if isinstance(item, dict)]
        kept = [item for item in rows if str(item.get("account_id") or "") != wanted]
        deleted = len(kept) != len(rows)
        data["accounts"] = kept
        await self._write_accounts_doc_async(data)
        if deleted:
            await self.delete_tokens_async(wanted)
        return deleted

    # ── tokens (user-scoped secrets) ────────────────────────────────────────

    @staticmethod
    def token_secret_key(account_id: str) -> str:
        return f"connections.accounts.{_safe_segment(account_id, fallback='account')}.tokens"

    async def set_tokens_async(self, account_id: str, tokens: Mapping[str, Any]) -> None:
        if set_user_secret is None:
            raise RuntimeError("async user-scoped secret storage is unavailable")
        await set_user_secret(
            self.token_secret_key(account_id),
            json.dumps(dict(tokens), sort_keys=True, ensure_ascii=True),
            user_id=self.user_id,
            bundle_id=self._token_bundle_id,
        )

    async def get_tokens_async(self, account_id: str) -> Dict[str, Any]:
        if get_secret is None:
            return {}
        raw = await get_secret(
            f"u:{self.token_secret_key(account_id)}",
            user_id=self.user_id,
            bundle_id=self._token_bundle_id,
        )
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    async def delete_tokens_async(self, account_id: str) -> None:
        if delete_user_secret is None:
            return
        try:
            await delete_user_secret(self.token_secret_key(account_id), user_id=self.user_id, bundle_id=self._token_bundle_id)
        except Exception:
            pass

    # ── signed OAuth state (single-use, anti-CSRF) ──────────────────────────

    def _state_path(self, state: str) -> Path:
        digest = hashlib.sha256(state.encode("utf-8")).hexdigest()
        return self.states_dir / f"{digest}.json"

    async def create_oauth_state_async(
        self,
        *,
        provider: str,
        secret: str,
        source: str,
        app_id: str = "",
        return_hint: str = "",
        ttl_seconds: int = 900,
    ) -> Dict[str, Any]:
        if not str(secret or "").strip():
            raise ValueError("OAuth state secret is not configured")
        provider_name = str(provider or "").strip()
        if not provider_name:
            raise ValueError("OAuth state requires a provider")
        now = int(time.time())
        payload = {
            "v": 1,
            "provider": provider_name,
            "app_id": str(app_id or "").strip(),
            "user_id": self.user_id,
            "account_id": f"{provider_name}_{uuid.uuid4().hex[:12]}",
            "nonce": uuid.uuid4().hex,
            "source": str(source or "settings").strip() or "settings",
            "return_hint": str(return_hint or "").strip(),
            "iat": now,
            "exp": now + int(ttl_seconds or 900),
        }
        encoded = _b64url_json(payload)
        sig = hmac.new(str(secret).encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        state = f"{encoded}.{sig}"
        async with aiofiles.open(self._state_path(state), "w", encoding="utf-8") as fh:
            await fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return {"state": state, "payload": payload}

    async def consume_oauth_state_async(self, *, state: str, secret: str) -> Dict[str, Any]:
        raw = str(state or "").strip()
        if "." not in raw:
            raise ValueError("OAuth state is invalid")
        encoded, received_sig = raw.rsplit(".", 1)
        expected = hmac.new(str(secret).encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received_sig, expected):
            raise ValueError("OAuth state signature is invalid")
        payload = _unb64url_json(encoded)
        if int(payload.get("exp") or 0) < int(time.time()):
            raise ValueError("OAuth state expired")
        path = self._state_path(raw)
        if not await aiofiles.os.path.exists(path):
            raise ValueError("OAuth state was not found or already used")
        await aiofiles.os.remove(path)
        return payload

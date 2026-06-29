"""Connection Hub edge storage and principal resolution helpers.

Connection Hub stores one graph primitive: an edge between two authority
identities. A same-principal link and an authorization delegation are not
separate storage models; they are different edge views:

- identity family resolution asks which identities are connected;
- boundary authorization asks whether the actor can be represented in the
  authority required by the boundary and which grants are delegated.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Any, Mapping, Optional


EDGE_SCHEMA = "connection_hub.edge.v1"
EDGE_CHALLENGE_SCHEMA = "connection_hub.edge_challenge.v1"
EDGE_RELATIONSHIP_DELEGATES_TO = "delegates_to"
PLATFORM_AUTHORITY_ID = "platform"


def _now() -> int:
    return int(time.time())


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(",", " ").split() if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _identity_ref(authority_id: str, subject: str) -> str:
    authority = _clean(authority_id)
    sub = _clean(subject)
    return f"{authority}:{sub}" if authority and sub else ""


def _actor_user_id(provider: str, subject: str, metadata: Mapping[str, Any] | None = None) -> str:
    explicit = _clean(_safe_mapping(metadata).get("actor_user_id"))
    if explicit:
        return explicit
    provider = _clean(provider).lower()
    subject = _clean(subject)
    if not provider or not subject:
        return ""
    return f"{provider}_{subject}"


def _edge_id(
    *,
    from_authority_id: str,
    from_subject: str,
    to_authority_id: str,
    to_subject: str,
    relationship: str,
) -> str:
    raw = "|".join(
        [
            _clean(relationship) or EDGE_RELATIONSHIP_DELEGATES_TO,
            _identity_ref(from_authority_id, from_subject),
            _identity_ref(to_authority_id, to_subject),
        ]
    )
    return "edge_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _endpoint(
    *,
    authority_id: str,
    provider: str,
    subject: str,
    user_id: str = "",
    label: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    authority = _clean(authority_id) or _clean(provider).lower()
    provider_value = _clean(provider).lower() or authority
    subject_value = _clean(subject)
    user = _clean(user_id) or (
        subject_value if authority == PLATFORM_AUTHORITY_ID else _actor_user_id(provider_value, subject_value, metadata)
    )
    return {
        "authority_id": authority,
        "provider": provider_value,
        "subject": subject_value,
        "identity_ref": _identity_ref(authority, subject_value),
        "user_id": user,
        "label": _clean(label) or subject_value,
    }


def edge_actor(edge: Mapping[str, Any]) -> dict[str, Any]:
    return _safe_mapping(edge.get("from"))


def edge_target(edge: Mapping[str, Any]) -> dict[str, Any]:
    return _safe_mapping(edge.get("to"))


class ConnectionEdgeStore:
    """Small JSON-backed Connection Hub edge store.

    The playground bundle uses JSON state, but callers should depend on this
    SDK contract rather than the filesystem shape. Production can later replace
    this with Postgres without changing API semantics.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.path = self.root / "connections" / "connection-edges.json"
        self.challenge_path = self.root / "connections" / "connection-edge-challenges.json"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "schema": EDGE_SCHEMA, "edges": {}}
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"version": 1, "schema": EDGE_SCHEMA, "edges": {}}
        if not isinstance(parsed, dict):
            return {"version": 1, "schema": EDGE_SCHEMA, "edges": {}}
        edges = parsed.get("edges")
        if not isinstance(edges, dict):
            parsed["edges"] = {}
        parsed.setdefault("version", 1)
        parsed.setdefault("schema", EDGE_SCHEMA)
        return parsed

    def _write(self, data: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def list_edges(
        self,
        *,
        target_user_id: str = "",
        source_provider: str = "",
        source_subject: str = "",
        relationship: str = EDGE_RELATIONSHIP_DELEGATES_TO,
    ) -> list[dict[str, Any]]:
        target_user = _clean(target_user_id)
        provider = _clean(source_provider).lower()
        subject = _clean(source_subject)
        relation = _clean(relationship)
        data = self._read()
        rows = data.get("edges") if isinstance(data, dict) else {}
        out: list[dict[str, Any]] = []
        if isinstance(rows, dict):
            for raw in rows.values():
                edge = _safe_mapping(raw)
                source = edge_actor(edge)
                target = edge_target(edge)
                if relation and _clean(edge.get("relationship")) != relation:
                    continue
                if target_user and _clean(target.get("user_id")) != target_user:
                    continue
                if provider and _clean(source.get("provider")).lower() != provider:
                    continue
                if subject and _clean(source.get("subject")) != subject:
                    continue
                if _clean(edge.get("status")) not in {"active", "linked"}:
                    continue
                out.append(edge)
        out.sort(
            key=lambda row: (
                _clean(edge_actor(row).get("provider")),
                _clean(edge_actor(row).get("subject")),
                _clean(edge_target(row).get("authority_id")),
            )
        )
        return out

    def upsert_edge(
        self,
        *,
        from_provider: str,
        from_subject: str,
        to_user_id: str,
        from_authority_id: str = "",
        to_authority_id: str = PLATFORM_AUTHORITY_ID,
        to_provider: str = PLATFORM_AUTHORITY_ID,
        relationship: str = EDGE_RELATIONSHIP_DELEGATES_TO,
        label: str = "",
        created_by: str = "",
        grants: Optional[list[str] | tuple[str, ...]] = None,
        constraints: Optional[Mapping[str, Any]] = None,
        proof: Optional[Mapping[str, Any]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        status: str = "active",
    ) -> dict[str, Any]:
        provider = _clean(from_provider).lower()
        subject = _clean(from_subject)
        target_user = _clean(to_user_id)
        source_authority = _clean(from_authority_id) or provider
        target_authority = _clean(to_authority_id) or PLATFORM_AUTHORITY_ID
        relation = _clean(relationship) or EDGE_RELATIONSHIP_DELEGATES_TO
        if not provider:
            raise ValueError("from_provider is required")
        if not subject:
            raise ValueError("from_subject is required")
        if not target_user or target_user == "anonymous":
            raise ValueError("to_user_id is required")

        data = self._read()
        rows = data.setdefault("edges", {})
        eid = _edge_id(
            from_authority_id=source_authority,
            from_subject=subject,
            to_authority_id=target_authority,
            to_subject=target_user,
            relationship=relation,
        )
        now = _now()
        previous = _safe_mapping(rows.get(eid)) if isinstance(rows, dict) else {}
        previous_target = edge_target(previous)
        previous_target_user = _clean(previous_target.get("user_id"))
        if previous_target_user and previous_target_user != target_user:
            raise ValueError("edge already targets another identity")

        metadata_map = _safe_mapping(metadata) if metadata is not None else _safe_mapping(previous.get("metadata"))
        source = _endpoint(
            authority_id=source_authority,
            provider=provider,
            subject=subject,
            label=label,
            metadata=metadata_map,
        )
        target = _endpoint(
            authority_id=target_authority,
            provider=to_provider,
            subject=target_user,
            user_id=target_user,
            label="KDCube platform user",
        )
        row = {
            "schema": EDGE_SCHEMA,
            "edge_id": eid,
            "relationship": relation,
            "from": source,
            "to": target,
            "grants": _safe_list(grants),
            "constraints": _safe_mapping(constraints),
            "proof": _safe_mapping(proof),
            "label": _clean(label) or previous.get("label") or subject,
            "status": _clean(status) or "active",
            "verified_at": previous.get("verified_at") or now,
            "created_at": previous.get("created_at") or now,
            "updated_at": now,
            "created_by": _clean(created_by) or previous.get("created_by") or target_user,
            "metadata": metadata_map,
        }
        rows[eid] = row
        self._write(data)
        return row

    def remove_edge(
        self,
        *,
        from_provider: str,
        from_subject: str,
        target_user_id: str = "",
    ) -> dict[str, Any]:
        provider = _clean(from_provider).lower()
        subject = _clean(from_subject)
        target_user = _clean(target_user_id)
        data = self._read()
        rows = data.get("edges") if isinstance(data, dict) else {}
        if not isinstance(rows, dict):
            return {"ok": True, "removed": False}
        removed: list[dict[str, Any]] = []
        for edge_id, edge in list(rows.items()):
            source = edge_actor(_safe_mapping(edge))
            target = edge_target(_safe_mapping(edge))
            if _clean(source.get("provider")).lower() != provider:
                continue
            if _clean(source.get("subject")) != subject:
                continue
            if target_user and _clean(target.get("user_id")) != target_user:
                return {"ok": False, "error": "connection_edge_belongs_to_another_principal"}
            removed.append(_safe_mapping(edge))
            del rows[edge_id]
        if removed:
            self._write(data)
        return {"ok": True, "removed": bool(removed), "edges": removed}

    def resolve_edge(
        self,
        *,
        from_provider: str,
        from_subject: str,
        target_authority_id: str = PLATFORM_AUTHORITY_ID,
    ) -> Optional[dict[str, Any]]:
        target_authority = _clean(target_authority_id) or PLATFORM_AUTHORITY_ID
        for edge in self.list_edges(source_provider=from_provider, source_subject=from_subject):
            if _clean(edge_target(edge).get("authority_id")) == target_authority:
                return edge
        return None

    def _read_challenges(self) -> dict[str, Any]:
        if not self.challenge_path.exists():
            return {"version": 1, "schema": EDGE_CHALLENGE_SCHEMA, "challenges": {}}
        try:
            parsed = json.loads(self.challenge_path.read_text(encoding="utf-8"))
        except Exception:
            return {"version": 1, "schema": EDGE_CHALLENGE_SCHEMA, "challenges": {}}
        if not isinstance(parsed, dict):
            return {"version": 1, "schema": EDGE_CHALLENGE_SCHEMA, "challenges": {}}
        challenges = parsed.get("challenges")
        if not isinstance(challenges, dict):
            parsed["challenges"] = {}
        parsed.setdefault("version", 1)
        parsed.setdefault("schema", EDGE_CHALLENGE_SCHEMA)
        return parsed

    def _write_challenges(self, data: Mapping[str, Any]) -> None:
        self.challenge_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.challenge_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.challenge_path)

    def create_edge_challenge(
        self,
        *,
        provider: str,
        target_user_id: str,
        created_by: str,
        ttl_seconds: int = 600,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        provider = _clean(provider).lower()
        user = _clean(target_user_id)
        if not provider:
            raise ValueError("provider is required")
        if not user or user == "anonymous":
            raise ValueError("target_user_id is required")
        now = _now()
        ttl = max(60, min(int(ttl_seconds or 600), 3600))
        challenge_id = secrets.token_urlsafe(24)
        row = {
            "schema": EDGE_CHALLENGE_SCHEMA,
            "challenge_id": challenge_id,
            "provider": provider,
            "target_authority_id": PLATFORM_AUTHORITY_ID,
            "target_user_id": user,
            "status": "pending",
            "created_at": now,
            "expires_at": now + ttl,
            "created_by": _clean(created_by) or user,
            "metadata": _safe_mapping(metadata),
        }
        data = self._read_challenges()
        challenges = data.setdefault("challenges", {})
        challenges[challenge_id] = row
        self._write_challenges(data)
        return row

    def create_provider_claim_challenge(
        self,
        *,
        provider: str,
        provider_subject: str,
        label: str = "",
        created_by: str = "",
        ttl_seconds: int = 600,
        metadata: Optional[Mapping[str, Any]] = None,
        grants: Optional[list[str] | tuple[str, ...]] = None,
    ) -> dict[str, Any]:
        provider = _clean(provider).lower()
        subject = _clean(provider_subject)
        if not provider:
            raise ValueError("provider is required")
        if not subject:
            raise ValueError("provider_subject is required")
        now = _now()
        ttl = max(60, min(int(ttl_seconds or 600), 3600))
        challenge_id = secrets.token_urlsafe(24)
        row = {
            "schema": EDGE_CHALLENGE_SCHEMA,
            "challenge_id": challenge_id,
            "provider": provider,
            "provider_subject": subject,
            "target_authority_id": PLATFORM_AUTHORITY_ID,
            "target_user_id": "",
            "label": _clean(label) or subject,
            "status": "pending_target_claim",
            "grants": _safe_list(grants),
            "created_at": now,
            "expires_at": now + ttl,
            "created_by": _clean(created_by) or provider,
            "metadata": _safe_mapping(metadata),
        }
        data = self._read_challenges()
        challenges = data.setdefault("challenges", {})
        challenges[challenge_id] = row
        self._write_challenges(data)
        return row

    def get_edge_challenge(self, *, challenge_id: str) -> Optional[dict[str, Any]]:
        cid = _clean(challenge_id)
        if not cid:
            return None
        data = self._read_challenges()
        challenges = data.get("challenges") if isinstance(data, dict) else {}
        if not isinstance(challenges, dict):
            return None
        row = challenges.get(cid)
        if not isinstance(row, Mapping):
            return None
        out = _safe_mapping(row)
        if out.get("status") in {"pending", "pending_target_claim"} and int(out.get("expires_at") or 0) < _now():
            out["status"] = "expired"
            challenges[cid] = out
            self._write_challenges(data)
        return out

    def claim_provider_challenge(
        self,
        *,
        challenge_id: str,
        target_user_id: str,
        claimed_by: str = "",
        grants: Optional[list[str] | tuple[str, ...]] = None,
    ) -> dict[str, Any]:
        cid = _clean(challenge_id)
        target_user = _clean(target_user_id)
        if not cid:
            raise ValueError("challenge_id is required")
        if not target_user or target_user == "anonymous":
            raise ValueError("target_user_id is required")

        data = self._read_challenges()
        challenges = data.get("challenges") if isinstance(data, dict) else {}
        if not isinstance(challenges, dict) or cid not in challenges:
            return {"ok": False, "error": "connection_edge_challenge_not_found"}
        challenge = _safe_mapping(challenges.get(cid))
        now = _now()
        status = _clean(challenge.get("status"))
        if status == "completed":
            if _clean(challenge.get("target_user_id")) != target_user:
                return {"ok": False, "error": "connection_edge_challenge_cross_user_access_denied", "challenge": challenge}
            edge = self.resolve_edge(
                from_provider=_clean(challenge.get("provider")),
                from_subject=_clean(challenge.get("provider_subject")),
            )
            return {"ok": True, "challenge": challenge, "edge": edge}
        if status != "pending_target_claim":
            return {"ok": False, "error": "connection_edge_challenge_not_claimable", "challenge": challenge}
        if int(challenge.get("expires_at") or 0) < now:
            challenge["status"] = "expired"
            challenge["updated_at"] = now
            challenges[cid] = challenge
            self._write_challenges(data)
            return {"ok": False, "error": "connection_edge_challenge_expired", "challenge": challenge}

        provider = _clean(challenge.get("provider"))
        subject = _clean(challenge.get("provider_subject"))
        if not provider or not subject:
            return {"ok": False, "error": "connection_edge_challenge_missing_source_identity", "challenge": challenge}
        try:
            edge = self.upsert_edge(
                from_provider=provider,
                from_subject=subject,
                from_authority_id=_clean(_safe_mapping(challenge.get("metadata")).get("authority_id")) or provider,
                to_user_id=target_user,
                label=_clean(challenge.get("label")) or subject,
                created_by=_clean(claimed_by) or target_user,
                grants=_safe_list(grants) or _safe_list(challenge.get("grants")),
                metadata=_safe_mapping(challenge.get("metadata")),
                proof={
                    "challenge_id": cid,
                    "provider": provider,
                    "claimed_at": now,
                },
            )
        except ValueError as exc:
            return {"ok": False, "error": "connection_edge_conflict", "message": str(exc), "challenge": challenge}
        challenge.update(
            {
                "status": "completed",
                "target_user_id": target_user,
                "claimed_at": now,
                "updated_at": now,
                "label": edge.get("label") or subject,
                "edge_id": edge.get("edge_id"),
                "grants": list(edge.get("grants") or []),
            }
        )
        challenges[cid] = challenge
        self._write_challenges(data)
        return {"ok": True, "challenge": challenge, "edge": edge}

    def complete_edge_challenge(
        self,
        *,
        challenge_id: str,
        provider: str,
        provider_subject: str,
        label: str = "",
        completed_by: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
        grants: Optional[list[str] | tuple[str, ...]] = None,
    ) -> dict[str, Any]:
        cid = _clean(challenge_id)
        expected_provider = _clean(provider).lower()
        subject = _clean(provider_subject)
        if not cid:
            raise ValueError("challenge_id is required")
        if not expected_provider:
            raise ValueError("provider is required")
        if not subject:
            raise ValueError("provider_subject is required")

        data = self._read_challenges()
        challenges = data.get("challenges") if isinstance(data, dict) else {}
        if not isinstance(challenges, dict) or cid not in challenges:
            return {"ok": False, "error": "connection_edge_challenge_not_found"}
        challenge = _safe_mapping(challenges.get(cid))
        now = _now()
        if _clean(challenge.get("provider")).lower() != expected_provider:
            return {"ok": False, "error": "connection_edge_challenge_provider_mismatch", "challenge": challenge}
        if _clean(challenge.get("status")) != "pending":
            return {"ok": False, "error": "connection_edge_challenge_not_pending", "challenge": challenge}
        if int(challenge.get("expires_at") or 0) < now:
            challenge["status"] = "expired"
            challenge["updated_at"] = now
            challenges[cid] = challenge
            self._write_challenges(data)
            return {"ok": False, "error": "connection_edge_challenge_expired", "challenge": challenge}

        target_user = _clean(challenge.get("target_user_id"))
        if not target_user or target_user == "anonymous":
            return {"ok": False, "error": "connection_edge_challenge_missing_target_identity", "challenge": challenge}
        merged_metadata = _safe_mapping(challenge.get("metadata"))
        if metadata is not None:
            merged_metadata.update(_safe_mapping(metadata))
        try:
            edge = self.upsert_edge(
                from_provider=expected_provider,
                from_subject=subject,
                from_authority_id=_clean(merged_metadata.get("authority_id")) or expected_provider,
                to_user_id=target_user,
                label=_clean(label) or subject,
                created_by=_clean(completed_by) or expected_provider,
                grants=_safe_list(grants) or _safe_list(challenge.get("grants")),
                metadata=merged_metadata,
                proof={
                    "challenge_id": cid,
                    "provider": expected_provider,
                    "completed_at": now,
                },
            )
        except ValueError as exc:
            return {"ok": False, "error": "connection_edge_conflict", "message": str(exc), "challenge": challenge}
        challenge.update(
            {
                "status": "completed",
                "completed_at": now,
                "updated_at": now,
                "provider_subject": subject,
                "label": edge.get("label") or subject,
                "edge_id": edge.get("edge_id"),
                "grants": list(edge.get("grants") or []),
            }
        )
        challenges[cid] = challenge
        self._write_challenges(data)
        return {"ok": True, "challenge": challenge, "edge": edge}


def resolve_principal_roles(
    *,
    platform_user_id: str,
    identity_config: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Resolve a platform principal through the current configured fixture.

    The returned shape is deliberately compatible with a future platform
    resolver response: callers should treat it as resolver output, not as roles
    authored by this app.
    """

    user = _clean(platform_user_id)
    cfg = _safe_mapping(identity_config)
    role_resolver = _safe_mapping(cfg.get("role_resolver"))
    mode = _clean(role_resolver.get("mode")) or "platform"
    bindings = _safe_mapping(cfg.get("role_bindings"))
    binding = _safe_mapping(bindings.get(user))
    roles = [str(v) for v in binding.get("roles") or [] if str(v).strip()]
    permissions = [str(v) for v in binding.get("permissions") or [] if str(v).strip()]

    if mode == "configured":
        status = "resolved" if roles or permissions else "no_binding"
        source = "connection_hub.configured_role_bindings"
    elif mode in {"none", "disabled"}:
        status = "disabled"
        source = "connection_hub.role_resolver_disabled"
        roles = []
        permissions = []
    else:
        status = "platform_resolver_not_wired"
        source = "platform.principal_role_resolver"
        roles = []
        permissions = []

    return {
        "platform_user_id": user,
        "roles": roles,
        "permissions": permissions,
        "role_resolution": {
            "status": status,
            "source": source,
            "mode": mode,
            "note": (
                "Connection Hub resolved the identity. A platform principal/role "
                "resolver should own entitlement resolution."
            ),
        },
    }


__all__ = [
    "ConnectionEdgeStore",
    "EDGE_CHALLENGE_SCHEMA",
    "EDGE_RELATIONSHIP_DELEGATES_TO",
    "EDGE_SCHEMA",
    "PLATFORM_AUTHORITY_ID",
    "edge_actor",
    "edge_target",
    "resolve_principal_roles",
]

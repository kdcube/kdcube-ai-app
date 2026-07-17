# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Claim-driven consent state — the ONE resolver the capabilities surface reads.

Every integration an agent can use (a delegated MCP tool, a connected-account
tool, a named-service realm) requires a set of CLAIMS — the raw grant vocabulary
(``memories:read``, ``slack:write``, …). This module answers, for one user and a
set of required claims, the per-claim consent state:

    given       — the user has consented / connected; the claim is usable now.
    pending     — the claim is delegable/connectable to this user but not yet
                  granted; the picker offers a grant/connect action.
    unavailable — the claim cannot be granted to this user (role not permitted,
                  provider not enabled); shown, not actionable.

It is CLAIM-FIRST and framework-neutral: it renders from the grant vocabulary's
own labels, so NO service must author a friendly Read/Actions taxonomy for its
consent to appear. A service that DID declare granular operation groups (Slack)
gets that richer view as ENRICHMENT layered on top by the caller — this resolver
is the base every integration shares.

The two consent stores are read through INJECTED readers (protocols) so this
module stays free of Redis/store wiring and is unit-testable; the store adapters
live beside it and are provided by the caller (the capabilities inventory).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, runtime_checkable

GIVEN = "given"
PENDING = "pending"
UNAVAILABLE = "unavailable"

# How a claim is consented — which store owns it.
SOURCE_DELEGATED = "delegated_by_kdcube"   # own KDCube resources (memories/tasks/…)
SOURCE_CONNECTED = "connected_account"     # an external provider account (Slack/Gmail)


@dataclass(frozen=True)
class ClaimRequirement:
    """A claim an integration needs, and which store consents it."""
    claim: str
    source: str = SOURCE_DELEGATED
    # connected-account routing (ignored for delegated):
    provider_id: str = ""
    connector_app_id: str = ""


@dataclass
class ClaimConsent:
    """The resolved consent for one claim, ready for the picker (claim-first)."""
    claim: str
    state: str                       # GIVEN | PENDING | UNAVAILABLE
    label: str = ""                  # from the grant vocabulary
    description: str = ""
    source: str = SOURCE_DELEGATED
    grant_action: Optional[Dict[str, Any]] = None  # how the user grants it (route/payload)

    def to_dict(self) -> Dict[str, Any]:
        out = {"claim": self.claim, "state": self.state, "source": self.source}
        if self.label:
            out["label"] = self.label
        if self.description:
            out["description"] = self.description
        if self.grant_action:
            out["grant_action"] = self.grant_action
        return out


@dataclass
class IntegrationConsent:
    """One integration's consent, claim-first. ``state`` is the rollup the picker
    shows on the header (pending if ANY required claim is pending)."""
    integration: str
    claims: List[ClaimConsent] = field(default_factory=list)

    @property
    def state(self) -> str:
        states = {c.state for c in self.claims}
        if PENDING in states:
            return PENDING
        if states == {GIVEN} or (states and states <= {GIVEN}):
            return GIVEN
        if states == {UNAVAILABLE}:
            return UNAVAILABLE
        # mix of given + unavailable, or empty
        return GIVEN if GIVEN in states else UNAVAILABLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integration": self.integration,
            "state": self.state,
            "claims": [c.to_dict() for c in self.claims],
        }


def claim_requirements_from_connection(conn: Mapping[str, Any]) -> List[ClaimRequirement]:
    """The claims a declared tool CONNECTION requires, as ClaimRequirements —
    one vocabulary across integration kinds:

    - a delegated `kind: mcp` connection (`delegated: true`) → its `scopes`/`claims`
      as delegated-by-KDCube claims;
    - a tool declaring `connected_accounts` → each account's `claims` as
      connected-account claims (carrying provider/connector for routing).

    A non-delegated / claim-less connection yields []."""
    out: List[ClaimRequirement] = []
    kind = str(conn.get("kind") or "").strip().lower()
    if kind == "mcp" and conn.get("delegated"):
        raw = conn.get("scopes") or conn.get("claims") or []
        if isinstance(raw, str):
            raw = [raw]
        for c in raw:
            c = str(c).strip()
            if c:
                out.append(ClaimRequirement(claim=c, source=SOURCE_DELEGATED))
    for acct in conn.get("connected_accounts") or []:
        if not isinstance(acct, Mapping):
            continue
        provider = str(acct.get("provider_id") or acct.get("provider") or "").strip()
        connector = str(acct.get("connector_app_id") or acct.get("connector") or "").strip()
        claims = acct.get("claims") or []
        if isinstance(claims, str):
            claims = [claims]
        for c in claims:
            c = str(c).strip()
            if c:
                out.append(ClaimRequirement(
                    claim=c, source=SOURCE_CONNECTED, provider_id=provider, connector_app_id=connector,
                ))
    return out


@runtime_checkable
class DelegatedGrantReader(Protocol):
    """Reads the delegated-by-KDCube store (own resources)."""
    async def granted_claims(self, user: Mapping[str, Any]) -> set: ...
    def vocabulary(self, claim: str) -> Dict[str, Any]: ...  # {label, description, delegable: bool, grant_action?}


@runtime_checkable
class ConnectedAccountReader(Protocol):
    """Reads the connected-account store (external providers)."""
    async def claim_state(
        self, *, claim: str, provider_id: str, connector_app_id: str, user: Mapping[str, Any]
    ) -> Dict[str, Any]: ...  # {state, label?, description?, grant_action?}


async def resolve_claim(
    req: ClaimRequirement,
    *,
    user: Mapping[str, Any],
    granted_delegated: set,
    delegated_reader: Optional[DelegatedGrantReader] = None,
    connected_reader: Optional[ConnectedAccountReader] = None,
) -> ClaimConsent:
    """Resolve one claim to a ``ClaimConsent`` via its owning store. Never raises;
    an unreadable store yields UNAVAILABLE (shown, not actionable)."""
    if req.source == SOURCE_CONNECTED:
        if connected_reader is None:
            return ClaimConsent(claim=req.claim, state=UNAVAILABLE, source=SOURCE_CONNECTED)
        try:
            info = await connected_reader.claim_state(
                claim=req.claim, provider_id=req.provider_id,
                connector_app_id=req.connector_app_id, user=user,
            )
        except Exception:
            info = {"state": UNAVAILABLE}
        return ClaimConsent(
            claim=req.claim,
            state=str(info.get("state") or UNAVAILABLE),
            label=str(info.get("label") or ""),
            description=str(info.get("description") or ""),
            source=SOURCE_CONNECTED,
            grant_action=info.get("grant_action"),
        )

    # delegated-by-KDCube (own resources)
    vocab: Dict[str, Any] = {}
    if delegated_reader is not None:
        try:
            vocab = delegated_reader.vocabulary(req.claim) or {}
        except Exception:
            vocab = {}
    if req.claim in (granted_delegated or set()):
        state = GIVEN
    elif vocab.get("delegable", True):
        state = PENDING
    else:
        state = UNAVAILABLE
    return ClaimConsent(
        claim=req.claim,
        state=state,
        label=str(vocab.get("label") or ""),
        description=str(vocab.get("description") or ""),
        source=SOURCE_DELEGATED,
        grant_action=vocab.get("grant_action") if state == PENDING else None,
    )


async def resolve_integration_consent(
    integration: str,
    requirements: Sequence[ClaimRequirement],
    *,
    user: Mapping[str, Any],
    delegated_reader: Optional[DelegatedGrantReader] = None,
    connected_reader: Optional[ConnectedAccountReader] = None,
) -> IntegrationConsent:
    """Resolve every required claim of one integration, claim-first. Reads the
    delegated store's granted set ONCE (it's per-user, not per-claim)."""
    granted_delegated: set = set()
    if delegated_reader is not None and any(r.source == SOURCE_DELEGATED for r in requirements):
        try:
            granted_delegated = set(await delegated_reader.granted_claims(user) or set())
        except Exception:
            granted_delegated = set()
    claims = [
        await resolve_claim(
            r, user=user, granted_delegated=granted_delegated,
            delegated_reader=delegated_reader, connected_reader=connected_reader,
        )
        for r in requirements
    ]
    return IntegrationConsent(integration=integration, claims=claims)

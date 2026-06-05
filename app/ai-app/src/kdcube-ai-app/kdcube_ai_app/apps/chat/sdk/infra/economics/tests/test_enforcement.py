# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Phase-1 unit tests for the reusable economics enforcement engine.

Redis-free: covers estimate sizing, nested-context detection, role carry,
funding-source selection, denial-at-start, the nested degrade path, and a
project-funded top-level happy path with fakes.
"""

from __future__ import annotations

import pytest

from kdcube_ai_app.infra import accounting as acct
from kdcube_ai_app.apps.chat.sdk.infra.economics.policy import QuotaPolicy, EconomicsLimitException
from kdcube_ai_app.apps.chat.sdk.infra.economics.limiter import AdmitResult
from kdcube_ai_app.apps.chat.sdk.infra.economics import enforcement as enf
from kdcube_ai_app.apps.chat.sdk.infra.economics.enforcement import (
    EconomicsGuard,
    EconomicsSubject,
    EconomicsEstimate,
    FlowPolicy,
    RoleResolver,
    economic_preflight,
)


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------
class _PlanBalance:
    def __init__(self, wallet: bool = False):
        self._wallet = wallet

    def has_lifetime_budget(self) -> bool:
        return self._wallet

    def has_plan_override(self) -> bool:
        return False

    def plan_override_is_active(self) -> bool:
        return False


class _Sub:
    def __init__(self, active: bool = True, plan_id: str = "beta-30"):
        self.status = "active" if active else "canceled"
        self.monthly_price_cents = 3000
        self.next_charge_at = None
        self.plan_id = plan_id
        self.provider = "internal"
        self.stripe_subscription_id = None
        self.last_charged_at = None


class _Credits:
    def __init__(self, balance: int = 0):
        self.balance = balance
        self.reserved = []
        self.committed = []
        self.consumed = []
        self.released = []

    async def get_lifetime_balance(self, **kw):
        return self.balance

    async def reserve_lifetime_tokens(self, **kw):
        self.reserved.append(kw)
        return True

    async def commit_reserved_lifetime_tokens(self, **kw):
        self.committed.append(kw)
        return 0

    async def consume_lifetime_tokens(self, **kw):
        self.consumed.append(kw)
        return 0

    async def release_lifetime_token_reservation(self, **kw):
        self.released.append(kw)


class _SubMgr:
    def __init__(self, sub=None):
        self.sub = sub

    async def get_subscription(self, **kw):
        return self.sub


class _CP:
    def __init__(self, *, plan_balance=None, sub=None, wallet=0, policy=None):
        self._plan_balance = plan_balance or _PlanBalance(wallet=bool(wallet))
        self.user_credits_mgr = _Credits(balance=wallet)
        self.subscription_mgr = _SubMgr(sub=sub)
        self._policy = policy or QuotaPolicy(max_concurrent=2, requests_per_day=100, tokens_per_month=10_000)

    async def get_user_plan_balance(self, **kw):
        return self._plan_balance

    async def get_plan_quota_policy(self, **kw):
        return self._policy


class _RL:
    def __init__(self, allowed: bool = True, reason=None):
        self.allowed = allowed
        self.reason = reason
        self.admit_calls = []
        self.commits = []
        self.releases = []

    async def admit(self, **kw):
        self.admit_calls.append(kw)
        reserve = int(kw.get("reserve_tokens") or 0)
        return AdmitResult(
            allowed=self.allowed,
            reason=None if self.allowed else (self.reason or "tokens_per_month"),
            lock_id=kw.get("lock_id") if self.allowed else None,
            snapshot={"tok_month": 0, "req_day": 0},
            reserved_tokens=reserve if self.allowed else 0,
            reservation_id=(kw.get("reservation_id") if (self.allowed and reserve > 0) else None),
        )

    async def commit_with_reservation(self, **kw):
        self.commits.append(kw)

    async def token_capacity_for_reservation(self, **kw):
        return {"available_tokens": 10**9, "own_reserved_tokens": int(kw.get("reserved_tokens") or 0)}

    async def release_token_reservation(self, **kw):
        self.releases.append(("tok", kw))
        return 1

    async def release(self, **kw):
        self.releases.append(("lock", kw))
        return 0


class _Budget:
    def __init__(self):
        self.reserved = []
        self.committed = []
        self.released = []
        self.forced = []

    async def get_app_budget_balance(self):
        return {"available_usd": 1000.0, "overdraft_limit_usd": None}

    async def reserve(self, **kw):
        self.reserved.append(kw)
        return type("RR", (), {"reservation_id": kw.get("reservation_id")})()

    async def commit_reserved_spend(self, **kw):
        self.committed.append(kw)

    async def release_reservation(self, **kw):
        self.released.append(kw)

    async def force_project_spend(self, **kw):
        self.forced.append(kw)


class _Spec:
    id = "test-bundle@1"


class _Config:
    ai_bundle_spec = _Spec()


class _EP:
    def __init__(self, *, cp, rl, budget, accounting_result=(1000, {"cost_total_usd": 0.03})):
        self.cp_manager = cp
        self.rl = rl
        self.budget_limiter = budget
        self.logger = None
        self.comm = None
        self.config = _Config()
        self.pg_pool = None
        self._acct = accounting_result
        self.run_accounting_calls = []

    def wallet_users_use_project_budget_first(self) -> bool:
        return True

    def project_budget_allowed_for_plan(self, *, user_type, plan_id, plan_source, has_wallet, has_active_subscription):
        # Mirrors BaseEntrypointWithEconomics.project_budget_allowed_for_plan
        if has_active_subscription:
            return False
        if has_wallet and not self.wallet_users_use_project_budget_first():
            return False
        return str(user_type or "").lower() != "anonymous"

    async def run_accounting(self, **kw):
        self.run_accounting_calls.append(kw)
        return self._acct


def _subject(role="registered"):
    return EconomicsSubject(tenant="t", project="p", user_id="u1", user_type=role, timezone="UTC")


def _ep(*, sub=None, wallet=0, allowed=True, reason=None, accounting=(1000, {"cost_total_usd": 0.03})):
    cp = _CP(sub=sub, wallet=wallet, plan_balance=_PlanBalance(wallet=bool(wallet)))
    rl = _RL(allowed=allowed, reason=reason)
    budget = _Budget()
    return _EP(cp=cp, rl=rl, budget=budget, accounting_result=accounting)


# --------------------------------------------------------------------------
# Estimate sizing
# --------------------------------------------------------------------------
def test_estimate_reservation_usd_drives_tokens():
    upt = enf._usd_per_token()
    est = EconomicsEstimate(reservation_usd=0.05, min_tokens=10)
    tokens = enf._estimate_tokens(est, upt)
    # tokens ~= reservation_usd / (upt * SAFETY_MARGIN)
    assert tokens > 10
    assert tokens == max(10, __import__("math").ceil(0.05 / (upt * enf.SAFETY_MARGIN)))


def test_estimate_text_path_uses_floor():
    est = EconomicsEstimate(input_text="hello world", output_budget_tokens=0, min_tokens=500)
    tokens = enf._estimate_tokens(est, enf._usd_per_token())
    assert tokens >= 500


# --------------------------------------------------------------------------
# Economics-scope detection (NOT raw accounting context)
# --------------------------------------------------------------------------
def test_active_econ_scope_none_by_default():
    assert enf.active_econ_scope() is None


def test_accounting_context_alone_is_not_an_econ_scope():
    # A bare accounting context (as a background-job worker binds) must NOT be
    # treated as a settling economics parent — otherwise top-level background
    # flows wrongly degrade to preflight and never reserve/settle.
    with acct.with_accounting("chat", turn_id="turn-123", conversation_id="conv-1"):
        assert enf.active_econ_scope() is None


# --------------------------------------------------------------------------
# Role carry
# --------------------------------------------------------------------------
def test_role_resolver_is_privileged():
    assert RoleResolver._is_privileged("privileged")
    assert RoleResolver._is_privileged("admin")
    assert not RoleResolver._is_privileged("registered")
    assert not RoleResolver._is_privileged(None)


async def test_role_resolver_preserves_privileged_without_db():
    rr = RoleResolver(pg_pool=None, tenant="t", project="p")
    # privileged is carried, resolver (DB) is never touched
    assert await rr.resolve(user_id="u1", carried_role="privileged") == "privileged"
    assert await rr.resolve(user_id="u1", carried_role="admin") == "admin"


# --------------------------------------------------------------------------
# Funding-source selection
# --------------------------------------------------------------------------
async def test_funding_summary_subscription():
    ep = _ep(sub=_Sub(active=True))
    g = EconomicsGuard(ep, subject=_subject("registered"), scope_id="s1", flow="f",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    r = await g._resolve_plan_and_funding()
    assert r["has_active_subscription"] is True
    assert g._funding_summary(r)[0] == "subscription"


async def test_funding_summary_project_for_registered():
    ep = _ep()  # no sub, no wallet
    g = EconomicsGuard(ep, subject=_subject("registered"), scope_id="s1", flow="f",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    r = await g._resolve_plan_and_funding()
    assert g._funding_summary(r)[0] == "project"


async def test_funding_summary_wallet_when_no_project():
    ep = _ep(wallet=1_000_000)
    g = EconomicsGuard(ep, subject=_subject("anonymous"), scope_id="s1", flow="f",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    r = await g._resolve_plan_and_funding()
    # anonymous: project not allowed, wallet present -> wallet
    assert g._funding_summary(r)[0] == "wallet"


async def test_funding_summary_paid_wallet_user_uses_project():
    # Alignment with run()'s project_budget_allowed_for_plan: a wallet-first paid
    # user's plan lane is backed by PROJECT (wallet is overflow only), NOT wallet.
    ep = _ep(wallet=1_000_000)
    g = EconomicsGuard(ep, subject=_subject("paid"), scope_id="s1", flow="f",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    r = await g._resolve_plan_and_funding()
    assert r["project_budget_allowed"] is True
    assert g._funding_summary(r)[0] == "project"


async def test_funding_summary_none():
    ep = _ep()
    g = EconomicsGuard(ep, subject=_subject("anonymous"), scope_id="s1", flow="f",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    r = await g._resolve_plan_and_funding()
    assert g._funding_summary(r)[0] == "none"


async def test_concurrency_dropped_for_non_chat():
    ep = _ep()
    g = EconomicsGuard(ep, subject=_subject("registered"), scope_id="s1", flow="f",
                       estimate=EconomicsEstimate(reservation_usd=0.05),
                       policy=FlowPolicy(enforce_concurrency=False))
    r = await g._resolve_plan_and_funding()
    assert r["base_policy"].max_concurrent is None


# --------------------------------------------------------------------------
# Denial at start
# --------------------------------------------------------------------------
async def test_preflight_denies_when_rate_limited():
    ep = _ep(allowed=False, reason="tokens_per_month")
    with pytest.raises(EconomicsLimitException) as ei:
        await economic_preflight(
            ep, subject=_subject("registered"),
            estimate=EconomicsEstimate(reservation_usd=0.05), flow="memory.search",
        )
    assert ei.value.code == "rate_limited"


async def test_preflight_denies_when_no_funding():
    ep = _ep()  # anonymous -> none
    with pytest.raises(EconomicsLimitException) as ei:
        await economic_preflight(
            ep, subject=_subject("anonymous"),
            estimate=EconomicsEstimate(reservation_usd=0.05), flow="memory.search",
        )
    assert ei.value.code == "no_funding_source"


async def test_guard_enter_denies_before_body_and_no_reservation():
    ep = _ep(allowed=False, reason="tokens_per_month")
    g = EconomicsGuard(ep, subject=_subject("registered"), scope_id="s1", flow="f",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    with pytest.raises(EconomicsLimitException):
        await g.__aenter__()
    assert ep.budget_limiter.reserved == []  # never reserved on denial


# --------------------------------------------------------------------------
# Nested degrade (anti double-charge)
# --------------------------------------------------------------------------
async def test_guard_degrades_to_preflight_when_inside_active_guard():
    ep = _ep()
    # Simulate an outer settling economics scope (guard-in-guard).
    token = enf._ECON_SCOPE_ACTIVE.set("outer-scope")
    try:
        g = EconomicsGuard(ep, subject=_subject("registered"), scope_id="s1", flow="f",
                           estimate=EconomicsEstimate(reservation_usd=0.05))
        decision = await g.__aenter__()
        assert decision.nested is True
        # no reservation, no accounting bind of our own
        assert ep.budget_limiter.reserved == []
        assert g._acct_cm is None
        # __aexit__ on a nested decision is a no-op
        await g.__aexit__(None, None, None)
        assert ep.budget_limiter.committed == []
    finally:
        enf._ECON_SCOPE_ACTIVE.reset(token)


async def test_guard_runs_top_level_inside_bare_accounting_context():
    # Regression: a background-job-style accounting context must NOT make the
    # guard nested — it must reserve and settle (own scope).
    ep = _ep()
    g = EconomicsGuard(ep, subject=_subject("registered"), scope_id="bg-scope", flow="memory.reconciler",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    with acct.with_accounting("job.worker", turn_id="turn_bg", conversation_id="turn_bg"):
        decision = await g.__aenter__()
        assert decision.nested is False
        assert len(ep.budget_limiter.reserved) == 1
        # while inside, the marker is our scope
        assert enf.active_econ_scope() == "bg-scope"
        await g.__aexit__(None, None, None)
    assert enf.active_econ_scope() is None
    assert len(ep.budget_limiter.committed) == 1


# --------------------------------------------------------------------------
# Top-level happy path (project funded)
# --------------------------------------------------------------------------
async def test_top_level_project_lifecycle_reserves_and_settles():
    ep = _ep(accounting=(1000, {"cost_total_usd": 0.03}))
    g = EconomicsGuard(ep, subject=_subject("registered"), scope_id="scope-xyz", flow="memory.reconciler",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    decision = await g.__aenter__()
    assert decision.nested is False
    assert decision.funding_source == "project"
    assert decision.app_reservation_source == "project"
    assert len(ep.budget_limiter.reserved) == 1
    # accounting bound under scope_id
    assert enf.active_econ_scope() == "scope-xyz"

    await g.__aexit__(None, None, None)
    # settled: project reservation committed, rl usage committed, accounting unbound
    assert len(ep.budget_limiter.committed) == 1
    assert len(ep.rl.commits) == 1
    assert ep.run_accounting_calls and ep.run_accounting_calls[0]["turn_id"] == "scope-xyz"
    assert enf.active_econ_scope() is None


async def test_top_level_releases_reservation_on_accounting_failure():
    class _BadEP(_EP):
        async def run_accounting(self, **kw):
            raise RuntimeError("boom")

    cp = _CP(plan_balance=_PlanBalance(False))
    ep = _BadEP(cp=cp, rl=_RL(), budget=_Budget())
    g = EconomicsGuard(ep, subject=_subject("registered"), scope_id="s9", flow="f",
                       estimate=EconomicsEstimate(reservation_usd=0.05))
    await g.__aenter__()
    await g.__aexit__(None, None, None)
    # settlement failed -> reservation released, accounting unbound
    assert len(ep.budget_limiter.released) == 1
    assert enf.active_econ_scope() is None

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Phase-3 wiring tests: memory reconciler -> EconomicsGuard.

Exercises the economics helpers added to the memory entrypoint without standing
up the full reconciliation pipeline (snapshot/candidates/LLM). Methods are called
unbound against a light stub `self`.
"""

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint_with_memory import (
    MemoryEntrypointMixin as M,
)
from kdcube_ai_app.apps.chat.sdk.infra.economics.enforcement import EconomicsGuard


class _Spec:
    id = "task-and-memo-app@1-0"


class _Config:
    ai_bundle_spec = _Spec()


class _StubMemEP:
    """Minimal stand-in for the memory entrypoint for economics wiring tests."""

    def __init__(self, *, economics: bool = True, reservation=0.25, pg_pool=None):
        self.cp_manager = object() if economics else None
        self.rl = object() if economics else None
        self.budget_limiter = object() if economics else None
        self.pg_pool = pg_pool
        self.logger = None
        self.comm = None
        self.config = _Config()
        self._reservation = reservation
        self.stored = []

    def _memory_reconciliation_config(self):
        return {"reservation_amount_dollars": self._reservation}

    async def _memory_reconciliation_store_job(self, job):
        self.stored.append(dict(job))
        return job

    # delegate to the real mixin implementations (these call each other via self.*)
    def _memory_economics_enabled(self):
        return M._memory_economics_enabled(self)

    def _memory_reconciliation_reservation_usd(self):
        return M._memory_reconciliation_reservation_usd(self)

    async def _memory_reconciliation_econ_subject(self, job):
        return await M._memory_reconciliation_econ_subject(self, job)


def _authority_for_role(role, user_id="u1"):
    """Projected Connection Hub authority for a carried role. The reconciliation
    subject resolves is_anonymous/roles/budget_bypass from this envelope (not the
    legacy user_type field), so the job must carry it."""
    if str(role or "").lower() == "anonymous":
        return {}
    return {
        "economics_projection": "platform_user",
        "platform_user_id": user_id,
        "platform_roles": [role],
        "economics_budget_bypass": str(role or "").lower() in ("privileged", "admin"),
    }


def _job(role="registered"):
    return {
        "job_id": "memrec_20260604_abc",
        "user_type": role,
        "identity_authority": _authority_for_role(role),
        "timezone": "Europe/Kyiv",
        "scope": {"tenant": "t", "project": "p", "user_id": "u1", "bundle_id": "b@1"},
    }


def test_economics_enabled_flag():
    assert M._memory_economics_enabled(_StubMemEP(economics=True)) is True
    assert M._memory_economics_enabled(_StubMemEP(economics=False)) is False


def test_reservation_usd_from_config():
    assert M._memory_reconciliation_reservation_usd(_StubMemEP(reservation=0.25)) == 0.25
    # bad value -> default
    ep = _StubMemEP(reservation="nope")
    assert M._memory_reconciliation_reservation_usd(ep) == 0.10


async def test_subject_preserves_privileged_carried_role():
    ep = _StubMemEP(pg_pool=None)  # no DB -> carried role kept
    subj = await M._memory_reconciliation_econ_subject(ep, _job(role="privileged"))
    assert subj.budget_bypass is True
    assert subj.is_anonymous is False
    assert (subj.tenant, subj.project, subj.user_id) == ("t", "p", "u1")
    assert subj.timezone == "Europe/Kyiv"


async def test_subject_uses_carried_role_when_no_pg():
    ep = _StubMemEP(pg_pool=None)
    subj = await M._memory_reconciliation_econ_subject(ep, _job(role="registered"))
    assert subj.budget_bypass is False
    assert subj.is_anonymous is False


async def test_make_guard_none_when_economics_disabled():
    ep = _StubMemEP(economics=False)
    guard = await M._memory_reconciliation_make_guard(ep, _job(), "memrec_20260604_abc")
    assert guard is None


async def test_make_guard_none_when_scope_incomplete():
    ep = _StubMemEP(economics=True)
    bad = _job()
    bad["scope"] = {"tenant": "", "project": "", "user_id": ""}
    guard = await M._memory_reconciliation_make_guard(ep, bad, "memrec_x")
    assert guard is None


async def test_make_guard_built_when_enabled():
    ep = _StubMemEP(economics=True)
    guard = await M._memory_reconciliation_make_guard(ep, _job(), "memrec_20260604_abc")
    assert isinstance(guard, EconomicsGuard)
    assert guard.scope_id == "mem_reconcile_memrec_20260604_abc"
    assert guard.flow == "memory.reconciler"
    assert guard.estimate.reservation_usd == 0.25
    assert guard.policy.enforce_concurrency is False
    assert guard.policy.emit_user_events is False


async def test_mark_economics_denied_sets_job_fields():
    ep = _StubMemEP()
    job = _job()

    class _Exc(RuntimeError):
        code = "rate_limited"
        data = {"reason": "tokens_per_month"}

    await M._memory_reconciliation_mark_economics_denied(ep, job, _Exc("limit hit"))
    assert job["status"] == "failed"
    assert job["economics"]["denied"] is True
    assert job["economics"]["code"] == "rate_limited"
    assert ep.stored and ep.stored[-1]["status"] == "failed"

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

# sdk/infra/economics/defaults.py

"""
Platform-owned default economics.

These are the mandatory baked-in quota policies for the four plan ids that are
intrinsic to the runtime plan-resolution logic in the economics entrypoint
(`anonymous`, `free`, `payasyougo`, `admin`). They are owned by the platform,
not by any bundle.

Two consumers share this single source of truth:
  - the deploy-time seeder always seeds these four (descriptor entries override
    them per field);
  - the runtime keeps a defensive fallback when a DB policy row is absent.

Subscription plans have a small baked-in baseline too: `free` and `admin` are
always seeded (descriptor entries override them per field), mirroring the quota
baseline. Any other subscription plan is descriptor opt-in.

`budget_policies` has NO baked-in baseline: it is descriptor opt-in and
admin-driven only, so there are no default constants here.
"""

from __future__ import annotations

from typing import Any, Dict

from kdcube_ai_app.apps.chat.sdk.infra.economics.policy import QuotaPolicy

# The four plan ids that the runtime resolves users into. Order is informational.
MANDATORY_QUOTA_PLAN_IDS = ("anonymous", "free", "payasyougo", "admin")

# Built-in baseline for the mandatory quota plans. A None dimension means
# "unlimited" for that window.
DEFAULT_QUOTA_POLICIES: Dict[str, QuotaPolicy] = {
    "anonymous": QuotaPolicy(
        max_concurrent=1,
        requests_per_day=2,
        requests_per_month=60,
        total_requests=None,
        tokens_per_hour=150_000,
        tokens_per_day=1_500_000,
        tokens_per_month=20_000_000,
    ),
    "free": QuotaPolicy(
        max_concurrent=2,
        requests_per_day=100,
        requests_per_month=30000,
        total_requests=None,
        tokens_per_hour=133_333,
        tokens_per_day=333_333,
        tokens_per_month=666_666,
    ),
    "payasyougo": QuotaPolicy(
        max_concurrent=4,
        requests_per_day=200,
        requests_per_month=6000,
        total_requests=None,
    ),
    "admin": QuotaPolicy(
        max_concurrent=10,
    ),
}


def default_quota_policy(plan_id: str) -> QuotaPolicy:
    """Defensive fallback used by the runtime when a DB policy row is missing."""
    return (
        DEFAULT_QUOTA_POLICIES.get(plan_id)
        or DEFAULT_QUOTA_POLICIES.get("free")
        or DEFAULT_QUOTA_POLICIES["anonymous"]
    )


# Subscription plan ids that the platform always seeds (descriptor overrides per
# field). Both are internal, free-of-charge catalog entries by default.
MANDATORY_SUBSCRIPTION_PLAN_IDS = ("free", "admin")

DEFAULT_SUBSCRIPTION_PLANS: Dict[str, Dict[str, Any]] = {
    "free": {"provider": "internal", "monthly_price_cents": 0, "active": True},
    "admin": {"provider": "internal", "monthly_price_cents": 0, "active": True},
}

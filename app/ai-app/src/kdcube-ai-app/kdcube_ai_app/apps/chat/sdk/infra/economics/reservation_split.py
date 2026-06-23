# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Reserve-side split for the unified funding model (single split).

This one runs at admit/reserve time against the *estimated* turn size.

Divisible (tokens/money):
plan_part = min(Reserve, Quota, Plan);
wallet_part = Reserve - plan_part;
admit_divisible iff wallet_part <= W.
Indivisible (requests/concurrency): a wallet holder always passes the gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Sentinel-free "unlimited": None means no bound (admin / unlimited overdraft /
# unlimited monthly quota). Internally treated as +inf.
def _as_bound(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    return max(int(value), 0)


@dataclass(frozen=True)
class ReservationSplitInput:
    # R — estimated turn cost (tokens).
    est_turn_tokens: int
    # Q — remaining plan token quota for the window (override-adjusted). None = unlimited.
    quota_remaining_tokens: Optional[int]
    # P — primary funding available, in token-equivalent (available_usd / usd_per_token).
    #     None = unlimited (admin bypass / unlimited overdraft).
    primary_available_tokens: Optional[int]
    # W — wallet tokens available.
    wallet_available_tokens: int
    has_wallet: bool
    # The request is over an indivisible quota (requests_per_*, max_concurrent) — the
    # caller computes this from the admit snapshot. total_requests is counted but NOT
    # enforced, so it must not feed this flag (decision D).
    over_indivisible_quota: bool = False


@dataclass(frozen=True)
class ReservationSplit:
    plan_part_tokens: int       # min(R, Q, P) — the primary/quota-funded share
    wallet_part_tokens: int     # R - plan_part — routed to the wallet
    admit: bool                 # admit_divisible AND indivisible_ok
    deny_reason: str            # "" when admit; else one of the reasons below

    # deny_reason vocabulary (caller maps to its SSE codes):
    #   "wallet_insufficient"  — over quota/funds and the wallet cannot cover the remainder
    #   "indivisible_no_wallet"— over a requests/concurrency quota and no wallet to pass the gate


def _min_with_unlimited(r: int, *bounds: Optional[int]) -> int:
    out = int(r)
    for b in bounds:
        if b is None:
            continue
        out = min(out, int(b))
    return max(out, 0)


def split_reservation(inp: ReservationSplitInput) -> ReservationSplit:
    """Compute the plan/wallet split + admit decision for one turn estimate."""
    r = max(int(inp.est_turn_tokens), 0)
    q = _as_bound(inp.quota_remaining_tokens)
    p = _as_bound(inp.primary_available_tokens)
    w = max(int(inp.wallet_available_tokens), 0)

    plan_part = _min_with_unlimited(r, q, p)
    wallet_part = max(r - plan_part, 0)

    admit_divisible = wallet_part <= w
    indivisible_ok = (not inp.over_indivisible_quota) or inp.has_wallet

    if admit_divisible and indivisible_ok:
        return ReservationSplit(
            plan_part_tokens=plan_part,
            wallet_part_tokens=wallet_part,
            admit=True,
            deny_reason="",
        )

    # Denied: report the binding reason. Indivisible gate is reported only when the
    # divisible split would otherwise have passed, so the caller can distinguish a
    # "need wallet to pass the request gate" denial from a "wallet too small" one.
    if not admit_divisible:
        reason = "wallet_insufficient"
    else:
        reason = "indivisible_no_wallet"

    return ReservationSplit(
        plan_part_tokens=plan_part,
        wallet_part_tokens=wallet_part,
        admit=False,
        deny_reason=reason,
    )

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Goldens for the reserve-side split — the R1-R9 + indivisible-gate rows from
docs/economics/unified-funding-split-model-README.md."""

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.infra.economics.reservation_split import (
    ReservationSplitInput,
    split_reservation,
)


def _split(*, R=100, Q=None, P=None, W=0, has_wallet=None, over_indivisible=False):
    # has_wallet defaults to "W > 0" unless explicitly overridden.
    hw = (W > 0) if has_wallet is None else has_wallet
    return split_reservation(
        ReservationSplitInput(
            est_turn_tokens=R,
            quota_remaining_tokens=Q,
            primary_available_tokens=P,
            wallet_available_tokens=W,
            has_wallet=hw,
            over_indivisible_quota=over_indivisible,
        )
    )


# --- divisible split (R-table) --------------------------------------------
def test_R1_plan_covers_all_wallet_untouched():
    s = _split(R=100, Q=500, P=500, W=50)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (100, 0)
    assert s.admit is True


def test_R2_over_quota_wallet_covers_remainder():
    s = _split(R=100, Q=60, P=500, W=50)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (60, 40)
    assert s.admit is True


def test_R3_over_quota_wallet_too_small_rejects():
    s = _split(R=100, Q=60, P=500, W=20)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (60, 40)
    assert s.admit is False
    assert s.deny_reason == "wallet_insufficient"


def test_R4_funds_short_wallet_covers():
    s = _split(R=100, Q=500, P=30, W=100)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (30, 70)
    assert s.admit is True


def test_R5_free_project_covers_within_quota():
    s = _split(R=100, Q=500, P=500, W=0)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (100, 0)
    assert s.admit is True


def test_R6_free_over_quota_wallet_covers():
    s = _split(R=100, Q=60, P=500, W=50)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (60, 40)
    assert s.admit is True


def test_R7_free_over_quota_no_wallet_rejects():
    # quota enforced for the wallet-less user
    s = _split(R=100, Q=60, P=500, W=0)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (60, 40)
    assert s.admit is False
    assert s.deny_reason == "wallet_insufficient"


def test_R8_admin_unlimited_never_rejects():
    s = _split(R=100, Q=None, P=None, W=0)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (100, 0)
    assert s.admit is True


def test_R9_wallet_meta_only_wallet_source_rejects_when_short():
    # primary funds = 0 (wallet is the only source); need 100 but W=80
    s = _split(R=100, Q=None, P=0, W=80, has_wallet=True)
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (0, 100)
    assert s.admit is False
    assert s.deny_reason == "wallet_insufficient"


# --- indivisible gate -----------------------------------------------------
def test_G1_over_request_quota_no_wallet_rejects():
    s = _split(R=100, Q=500, P=500, W=0, over_indivisible=True)
    assert s.admit is False
    assert s.deny_reason == "indivisible_no_wallet"


def test_G2_over_request_quota_with_wallet_passes():
    s = _split(R=100, Q=500, P=500, W=50, has_wallet=True, over_indivisible=True)
    assert s.admit is True


def test_G3_over_concurrency_with_wallet_passes():
    # divisible split is fully covered by the plan; the gate is lifted by the wallet
    s = _split(R=100, Q=500, P=500, W=10, has_wallet=True, over_indivisible=True)
    assert s.admit is True
    assert (s.plan_part_tokens, s.wallet_part_tokens) == (100, 0)


# --- precedence: a divisible shortfall outranks the indivisible gate ------
def test_wallet_insufficient_reported_over_indivisible_when_both_fail():
    # over quota AND over an indivisible dim, wallet too small for the divisible part:
    # the binding denial is the wallet shortfall.
    s = _split(R=100, Q=60, P=500, W=20, has_wallet=True, over_indivisible=True)
    assert s.admit is False
    assert s.deny_reason == "wallet_insufficient"

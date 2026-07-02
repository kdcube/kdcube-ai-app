# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Signed conversation file download tokens: mint/verify round-trip + tamper checks."""

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.conversation.download_links import (
    mint_file_download_token,
    verify_file_download_token,
)


def test_round_trip_returns_bound_payload():
    token, expires_at = mint_file_download_token(
        "secret", fi_ref="fi:conv_c1.turn_t1.outputs/chart.png",
        user_id="u1", conversation_id="c1", tenant="t", project="p",
        ttl_seconds=900, now=1000,
    )
    assert expires_at == 1900
    payload = verify_file_download_token("secret", token, fi_ref="fi:conv_c1.turn_t1.outputs/chart.png", now=1001)
    assert payload["user_id"] == "u1"
    assert payload["conversation_id"] == "c1"
    assert payload["tenant"] == "t"
    assert payload["project"] == "p"


def test_verify_rejects_wrong_fi_ref():
    token, _ = mint_file_download_token("secret", fi_ref="fi:a", user_id="u1", now=1000)
    with pytest.raises(ValueError):
        verify_file_download_token("secret", token, fi_ref="fi:b", now=1001)


def test_verify_rejects_wrong_secret_and_tamper():
    token, _ = mint_file_download_token("secret", fi_ref="fi:a", user_id="u1", now=1000)
    with pytest.raises(ValueError):
        verify_file_download_token("other-secret", token, fi_ref="fi:a", now=1001)
    body, sig = token.split(".", 1)
    tampered = body[:-1] + ("A" if body[-1] != "A" else "B") + "." + sig
    with pytest.raises(ValueError):
        verify_file_download_token("secret", tampered, fi_ref="fi:a", now=1001)


def test_verify_rejects_expired():
    token, expires_at = mint_file_download_token("secret", fi_ref="fi:a", user_id="u1", ttl_seconds=60, now=1000)
    assert expires_at == 1060
    with pytest.raises(ValueError):
        verify_file_download_token("secret", token, fi_ref="fi:a", now=1061)


def test_mint_requires_secret():
    with pytest.raises(ValueError):
        mint_file_download_token("", fi_ref="fi:a", user_id="u1", now=1000)


def test_ttl_is_clamped():
    # Below the floor and above the ceiling both clamp into range.
    _, low = mint_file_download_token("s", fi_ref="fi:a", user_id="u", ttl_seconds=1, now=0)
    _, high = mint_file_download_token("s", fi_ref="fi:a", user_id="u", ttl_seconds=10**9, now=0)
    assert low == 60
    assert high == 86400

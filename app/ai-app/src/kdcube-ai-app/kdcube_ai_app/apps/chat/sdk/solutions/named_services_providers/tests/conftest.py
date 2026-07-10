# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

import pytest

from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.contract_gate import (
    reset_contract_gate_process_state,
)


@pytest.fixture(autouse=True)
def _reset_contract_gate_state():
    """The contract-first gate keeps in-process state (conversation-keyed);
    tests in this directory dispatch through the same process, so each test
    starts and ends with a clean gate."""

    reset_contract_gate_process_state()
    yield
    reset_contract_gate_process_state()

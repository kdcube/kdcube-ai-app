# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Authority-provider runtimes owned by Connection Hub SDK.

Provider modules are intentionally not imported here. Some providers depend on
host/runtime integrations, and importing them eagerly during gateway startup can
create application-level cycles. Import the concrete provider module directly.
"""

from __future__ import annotations

__all__: list[str] = []

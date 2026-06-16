# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

# ops/deployment/economics/__init__.py

from kdcube_ai_app.ops.deployment.economics.economics_seed import (
    seed_economics,
    load_economics_descriptor,
)

__all__ = ["seed_economics", "load_economics_descriptor"]

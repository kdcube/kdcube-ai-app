# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Email/app-password adapter registration for user-connected integrations."""

from __future__ import annotations

from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.adapters import (
    UserIntegrationAdapter,
    adapter,
)


@adapter("email.imap_smtp_app_password")
class EmailAppPasswordAdapter(UserIntegrationAdapter):
    label = "Email"
    kind = "app_password"

    async def normalize_profile(self, credential: dict) -> dict:
        email = str(credential.get("email") or credential.get("username") or "").strip()
        return {
            "external_subject": email,
            "email": email,
            "display_name": email,
        }


__all__ = ["EmailAppPasswordAdapter"]

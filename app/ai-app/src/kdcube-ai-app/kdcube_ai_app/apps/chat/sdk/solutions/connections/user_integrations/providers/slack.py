# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Slack user-token adapter registration for user-connected integrations."""

from __future__ import annotations

import httpx

from kdcube_ai_app.apps.chat.sdk.solutions.connections.user_integrations.adapters import (
    UserIntegrationAdapter,
    adapter,
)

SLACK_AUTH_TEST_URL = "https://slack.com/api/auth.test"


@adapter("slack.oauth_user_token")
class SlackUserTokenAdapter(UserIntegrationAdapter):
    label = "Slack"
    kind = "oauth2"
    authorize_url = "https://slack.com/oauth/v2/authorize"
    token_url = "https://slack.com/api/oauth.v2.access"

    def authorize_scope_param(self) -> str:
        return "user_scope"

    def extract_token(self, raw: dict) -> dict:
        data = dict(raw or {})
        if "ok" in data and not data.get("ok"):
            raise RuntimeError(f"Slack OAuth error: {data.get('error') or 'unknown'}")
        authed = data.get("authed_user")
        if isinstance(authed, dict) and str(authed.get("access_token") or "").strip():
            out = {
                "access_token": authed.get("access_token"),
                "token_type": authed.get("token_type") or "user",
                "scope": authed.get("scope") or "",
            }
            if authed.get("refresh_token"):
                out["refresh_token"] = authed["refresh_token"]
            if authed.get("expires_in"):
                out["expires_in"] = authed["expires_in"]
            team = data.get("team")
            if isinstance(team, dict):
                out["team_id"] = team.get("id")
                out["team_name"] = team.get("name")
            return out
        return data

    async def fetch_profile(self, *, access_token: str, token: dict | None = None) -> dict:
        del token
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    SLACK_AUTH_TEST_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Slack auth.test request failed: {exc}") from exc
        try:
            data = response.json()
        except Exception:
            data = {}
        if not isinstance(data, dict) or not data.get("ok"):
            err = ""
            if isinstance(data, dict):
                err = str(data.get("error") or "")
            raise RuntimeError(f"Slack auth.test failed: {err or 'unknown error'}")
        team_id = str(data.get("team_id") or "").strip()
        user_id = str(data.get("user_id") or "").strip()
        team = str(data.get("team") or "").strip()
        user = str(data.get("user") or "").strip()
        display = f"{user} @ {team}" if user and team else user or team or user_id or "Slack account"
        return {
            "external_subject": user_id,
            "workspace": team_id,
            "workspace_label": team,
            "display_name": display,
        }

    async def normalize_profile(self, credential: dict) -> dict:
        team = str(credential.get("team_name") or credential.get("workspace_label") or "").strip()
        user = str(credential.get("user") or credential.get("user_id") or "").strip()
        display = f"{user} @ {team}" if user and team else user or team
        return {
            "external_subject": str(credential.get("user_id") or "").strip(),
            "workspace": str(credential.get("team_id") or credential.get("workspace") or "").strip(),
            "display_name": display,
        }


__all__ = ["SlackUserTokenAdapter"]

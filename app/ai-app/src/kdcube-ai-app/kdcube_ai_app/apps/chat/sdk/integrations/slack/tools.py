# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Slack tools backed by Connection Hub connected accounts."""

from __future__ import annotations

from typing import Annotated, Any

import httpx
import semantic_kernel as sk

try:
    from semantic_kernel.functions import kernel_function
except Exception:
    from semantic_kernel.utils.function_decorator import kernel_function

from kdcube_ai_app.apps.chat.sdk.integrations.connected_accounts import (
    ConnectedAccountCredential,
    resolve_connected_account_claim,
)


SLACK_PROVIDER_ID = "slack"
SLACK_CONNECTOR_APP_ID = "demo"
SLACK_SEARCH_CLAIM = "slack:search"
SLACK_POST_CLAIM = "slack:post"
SLACK_API = "https://slack.com/api"

_SERVICE = None
_INTEGRATIONS: dict[str, Any] = {}


def bind_service(svc: Any) -> None:
    global _SERVICE
    _SERVICE = svc


def bind_integrations(integrations: dict[str, Any] | None) -> None:
    global _INTEGRATIONS
    _INTEGRATIONS = dict(integrations or {})


def _ok_ret_result(ret: Any) -> dict[str, Any]:
    return {"ok": True, "error": None, "ret": ret}


def _error_result(*, code: str, message: str, where: str, ret: Any = None) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "where": where,
            "managed": True,
        },
        "ret": ret,
    }


def _slack_error(data: Any, *, fallback: str) -> str:
    if isinstance(data, dict):
        return str(data.get("error") or data.get("warning") or fallback)
    return fallback


class SlackTools:
    async def _credential(
        self,
        *,
        claim: str,
        tool_name: str,
        account_id: str = "",
    ) -> ConnectedAccountCredential:
        return await resolve_connected_account_claim(
            globals(),
            provider_id=SLACK_PROVIDER_ID,
            connector_app_id=SLACK_CONNECTOR_APP_ID,
            claim=claim,
            account_id=account_id,
            tool_name=tool_name,
        )

    @kernel_function(
        name="search_slack",
        description=(
            "Search Slack messages visible to the current user's connected Slack account. "
            "Requires the user to connect Slack with the slack:search claim in Connection Hub. "
            "Returns {ok, error, ret}; ret contains matching messages."
        ),
    )
    async def search_slack(
        self,
        query: Annotated[str, "Slack search query."] = "",
        count: Annotated[int, "Maximum results to return, 1-20.", {"min": 1, "max": 20}] = 10,
        account_id: Annotated[str, "Optional connected account id when the user has several Slack workspaces/accounts."] = "",
    ) -> Annotated[dict, "Envelope: {ok, error, ret}."]:
        if not str(query or "").strip():
            return _error_result(
                code="query_required",
                message="Slack search query is required.",
                where="slack.search_slack",
            )
        credential = await self._credential(claim=SLACK_SEARCH_CLAIM, account_id=account_id, tool_name="slack.search_slack")
        if not credential.ok:
            return credential.error_envelope(where="slack.search_slack")
        if not credential.access_token:
            return _error_result(
                code="credential_missing_access_token",
                message="Connected Slack credential has no access token.",
                where="slack.search_slack",
            )
        limit = max(1, min(int(count or 10), 20))
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{SLACK_API}/search.messages",
                headers={"Authorization": f"Bearer {credential.access_token}"},
                params={"query": query, "count": limit},
            )
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code >= 400 or not (isinstance(data, dict) and data.get("ok")):
            return _error_result(
                code="slack_api_error",
                message=_slack_error(data, fallback="Slack search failed."),
                where="slack.search_slack",
                ret=data if isinstance(data, dict) else None,
            )
        messages = data.get("messages") if isinstance(data, dict) else {}
        matches = messages.get("matches") if isinstance(messages, dict) else []
        rows: list[dict[str, Any]] = []
        for item in matches or []:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "channel_id": str(item.get("channel", {}).get("id") if isinstance(item.get("channel"), dict) else item.get("channel") or ""),
                    "channel_name": str(item.get("channel", {}).get("name") if isinstance(item.get("channel"), dict) else ""),
                    "user": str(item.get("user") or item.get("username") or ""),
                    "text": str(item.get("text") or ""),
                    "permalink": str(item.get("permalink") or ""),
                    "timestamp": str(item.get("ts") or ""),
                }
            )
        return _ok_ret_result({"messages": rows, "count": len(rows), "account_id": credential.account_id})

    @kernel_function(
        name="post_slack_message",
        description=(
            "Post a message to a Slack channel using the current user's connected Slack account. "
            "Requires the user to connect Slack with the slack:post claim in Connection Hub. "
            "The channel can be a Slack channel id or an allowed channel name accepted by Slack."
        ),
    )
    async def post_slack_message(
        self,
        channel: Annotated[str, "Slack channel id or name accepted by Slack."] = "",
        text: Annotated[str, "Message text to post."] = "",
        thread_ts: Annotated[str, "Optional Slack thread timestamp to reply in a thread."] = "",
        account_id: Annotated[str, "Optional connected account id when the user has several Slack workspaces/accounts."] = "",
    ) -> Annotated[dict, "Envelope: {ok, error, ret}."]:
        if not str(channel or "").strip():
            return _error_result(
                code="channel_required",
                message="Slack channel is required.",
                where="slack.post_slack_message",
            )
        if not str(text or "").strip():
            return _error_result(
                code="text_required",
                message="Slack message text is required.",
                where="slack.post_slack_message",
            )
        credential = await self._credential(claim=SLACK_POST_CLAIM, account_id=account_id, tool_name="slack.post_slack_message")
        if not credential.ok:
            return credential.error_envelope(where="slack.post_slack_message")
        if not credential.access_token:
            return _error_result(
                code="credential_missing_access_token",
                message="Connected Slack credential has no access token.",
                where="slack.post_slack_message",
            )
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if str(thread_ts or "").strip():
            payload["thread_ts"] = str(thread_ts).strip()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{SLACK_API}/chat.postMessage",
                headers={"Authorization": f"Bearer {credential.access_token}"},
                json=payload,
            )
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code >= 400 or not (isinstance(data, dict) and data.get("ok")):
            return _error_result(
                code="slack_api_error",
                message=_slack_error(data, fallback="Slack post failed."),
                where="slack.post_slack_message",
                ret=data if isinstance(data, dict) else None,
            )
        return _ok_ret_result(
            {
                "channel": str(data.get("channel") or channel),
                "timestamp": str(data.get("ts") or ""),
                "message": data.get("message") if isinstance(data.get("message"), dict) else {},
                "account_id": credential.account_id,
            }
        )


kernel = sk.Kernel()
tools = SlackTools()
kernel.add_plugin(tools, "slack")


__all__ = [
    "SLACK_API",
    "SLACK_CONNECTOR_APP_ID",
    "SLACK_POST_CLAIM",
    "SLACK_PROVIDER_ID",
    "SLACK_SEARCH_CLAIM",
    "SlackTools",
    "kernel",
    "tools",
]

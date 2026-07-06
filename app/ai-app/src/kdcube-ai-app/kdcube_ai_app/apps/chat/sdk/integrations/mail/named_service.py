# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Provider-neutral mail named service.

The ``mail`` namespace models mail as a user realm, not as a specific OAuth
provider. A platform user can connect several mail accounts (Gmail, iCloud,
Yahoo, ...). This provider exposes those accounts and messages through the
standard named-service operations; provider-specific transport remains in the
provider packages such as ``integrations.google.gmail_tools``.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from kdcube_ai_app.apps.chat.sdk.integrations.google.gmail_tools import (
    GMAIL_CONNECTOR_APP_ID,
    GMAIL_PROVIDER_ID,
    GMAIL_READ_CLAIM,
    GMAIL_SEND_CLAIM,
    GmailTools,
    bind_integrations as bind_gmail_integrations,
    bind_service as bind_gmail_service,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.connection_edges import (
    DEFAULT_CONNECTION_HUB_BUNDLE_ID,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube import (
    DelegatedToKdcubeClient,
    connected_account_consent_payload,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube.models import (
    ConnectedAccount,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers import (
    NamedServiceContext,
    NamedServiceProvider,
    NamedServiceProviderSpec,
    NamedServiceRequest,
    NamedServiceResponse,
    NamedServiceSearchScope,
    TRANSPORT_API,
    TRANSPORT_LOCAL,
    named_service_provider,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.types import (
    OBJECT_ACTION,
    OBJECT_GET,
    OBJECT_LIST,
    OBJECT_SCHEMA,
    OBJECT_SEARCH,
    PROVIDER_ABOUT,
    PROVIDER_CAPABILITIES,
)


LOGGER = logging.getLogger("kdcube.sdk.integrations.mail.named_service")

MAIL_NAMESPACE = "mail"
PROVIDER_ID = "sdk.integrations.mail"
MAIL_ACCOUNT_KIND = "mail.account"
MAIL_MESSAGE_KIND = "mail.message"
MAIL_ATTACHMENT_KIND = "mail.attachment"
MAIL_TRANSPORTS = (TRANSPORT_LOCAL, TRANSPORT_API)

ACTION_DOWNLOAD_ATTACHMENTS = "download_attachments"
ACTION_SEND = "send"
ACTION_FORWARD = "forward"

MAIL_GRANT_HINTS = {
    "object.list": ["mail:read"],
    "object.search": ["mail:read"],
    "object.get": ["mail:read"],
    "object.action.download_attachments": ["mail:read"],
    "object.action.send": ["mail:send"],
    "object.action.forward": ["mail:read", "mail:send"],
}

MAIL_PROVIDER_CATALOG = {
    "gmail": {
        "provider_id": GMAIL_PROVIDER_ID,
        "connector_app_id": GMAIL_CONNECTOR_APP_ID,
        "label": "Gmail",
        "claims": {
            "read": GMAIL_READ_CLAIM,
            "send": GMAIL_SEND_CLAIM,
        },
    },
    # Shape reserved for providers implemented next. They share the ``mail``
    # namespace and object model, but resolve through their own connector app.
    "icloud": {
        "provider_id": "email",
        "connector_app_id": "icloud-mail",
        "label": "iCloud Mail",
        "claims": {"read": "mail:read", "send": "mail:send"},
        "implemented": False,
    },
    "yahoo": {
        "provider_id": "email",
        "connector_app_id": "yahoo-mail",
        "label": "Yahoo Mail",
        "claims": {"read": "mail:read", "send": "mail:send"},
        "implemented": False,
    },
}

MAIL_SEARCH_FILTERS = {
    "account_id": {
        "type": "string",
        "description": "Optional connected mail account id. Omit to search every connected Gmail account with mail read access.",
    },
    "provider": {
        "type": "string",
        "description": "Optional mail provider key. Currently implemented: gmail.",
        "default": "gmail",
    },
    "gmail_query": {
        "type": "string",
        "description": "Gmail-native query. Defaults to the named-service query.",
    },
}

MAIL_SEARCH_SCOPES = (
    NamedServiceSearchScope(
        namespace=MAIL_NAMESPACE,
        label="mail messages",
        object_kind=MAIL_MESSAGE_KIND,
        description=(
            "Search messages across connected mail accounts. Omit account_id to "
            "search every connected account that already approved the read claim."
        ),
        filters_schema=MAIL_SEARCH_FILTERS,
    ),
)

MAIL_INTRO = (
    "Use namespace `mail` for user-connected email accounts. Start with "
    "object.list to see connected accounts, object.search to find messages, "
    "object.get to read a message, and object.action with download_attachments, "
    "send, or forward for bounded mail actions."
)

MAIL_SCHEMA = {
    "namespace": MAIL_NAMESPACE,
    "refs": {
        "account": "mail:<provider>:<account_id>",
        "message": "mail:<provider>:<account_id>:message:<message_id>",
        "attachment": "mail:<provider>:<account_id>:attachment:<message_id>:<attachment_id>",
    },
    "object_kinds": {
        MAIL_ACCOUNT_KIND: {
            "description": "One connected mail account belonging to the current KDCube user.",
            "fields": ["ref", "provider", "provider_id", "connector_app_id", "account_id", "label", "email", "claims"],
        },
        MAIL_MESSAGE_KIND: {
            "description": "One mail message found or read from a connected account.",
            "fields": ["ref", "provider", "account_id", "message_id", "thread_id", "subject", "from", "date", "snippet"],
        },
        MAIL_ATTACHMENT_KIND: {
            "description": "One attachment on a mail message.",
            "fields": ["attachment_id", "filename", "mime_type", "size_bytes", "logical_path"],
        },
    },
    "search": {"filters": MAIL_SEARCH_FILTERS},
    "actions": {
        ACTION_DOWNLOAD_ATTACHMENTS: {
            "description": "Download message attachments into KDCube files.",
            "object_ref": "mail:<provider>:<account_id>:message:<message_id>",
            "payload": ["attachment_ids", "include_inline", "max_attachments", "visibility"],
        },
        ACTION_SEND: {
            "description": "Send a new email from a connected mail account.",
            "object_ref": "mail:<provider>:<account_id> or omit account_id in payload when only one account can send",
            "payload": ["to", "subject", "body_markdown", "cc", "bcc", "body_html", "attachment_paths", "account_id"],
        },
        ACTION_FORWARD: {
            "description": "Forward an existing message.",
            "object_ref": "mail:<provider>:<account_id>:message:<message_id>",
            "payload": ["to", "note_markdown", "cc", "bcc", "include_original_attachments", "attachment_paths"],
        },
    },
    "grant_hints": MAIL_GRANT_HINTS,
    "connected_account_claims": {
        "gmail": {
            "read": GMAIL_READ_CLAIM,
            "send": GMAIL_SEND_CLAIM,
        }
    },
}


def _operations() -> dict[str, Any]:
    return {
        PROVIDER_ABOUT: {"transports": MAIL_TRANSPORTS},
        PROVIDER_CAPABILITIES: {"transports": MAIL_TRANSPORTS},
        OBJECT_LIST: {"transports": MAIL_TRANSPORTS},
        OBJECT_SEARCH: {"transports": MAIL_TRANSPORTS},
        OBJECT_GET: {"transports": MAIL_TRANSPORTS},
        OBJECT_SCHEMA: {"transports": MAIL_TRANSPORTS},
        OBJECT_ACTION: {"transports": MAIL_TRANSPORTS},
    }


def mail_named_service_spec(*, bundle_id: str | None = None) -> NamedServiceProviderSpec:
    return NamedServiceProviderSpec(
        provider_id=PROVIDER_ID,
        bundle_id=bundle_id,
        namespace=MAIL_NAMESPACE,
        refs=("mail:*",),
        object_kinds=(MAIL_ACCOUNT_KIND, MAIL_MESSAGE_KIND, MAIL_ATTACHMENT_KIND),
        search_scopes=MAIL_SEARCH_SCOPES,
        operations=_operations(),
        label="Mail",
        description="Provider-neutral mail namespace over user-connected Gmail, iCloud, Yahoo, and related accounts.",
        intro=MAIL_INTRO,
        metadata={
            "provider_catalog": MAIL_PROVIDER_CATALOG,
            "grant_hints": MAIL_GRANT_HINTS,
            "canonical_ref": "mail:<provider>:<account_id>:message:<message_id>",
        },
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, *, default: int, minimum: int = 1, maximum: int = 50) -> int:
    try:
        parsed = int(value if value is not None else default)
    except Exception:
        parsed = default
    return max(minimum, min(parsed, maximum))


def _as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def account_ref(provider: str, account_id: str) -> str:
    return f"{MAIL_NAMESPACE}:{_text(provider) or 'gmail'}:{_text(account_id)}"


def message_ref(provider: str, account_id: str, message_id: str) -> str:
    return f"{account_ref(provider, account_id)}:message:{_text(message_id)}"


def attachment_ref(provider: str, account_id: str, message_id: str, attachment_id: str) -> str:
    return f"{account_ref(provider, account_id)}:attachment:{_text(message_id)}:{_text(attachment_id)}"


def parse_mail_ref(ref: str) -> dict[str, str]:
    parts = _text(ref).split(":")
    if len(parts) < 3 or parts[0] != MAIL_NAMESPACE:
        return {}
    parsed = {"provider": parts[1], "account_id": parts[2], "kind": "account"}
    if len(parts) >= 5 and parts[3] == "message":
        parsed.update({"kind": "message", "message_id": ":".join(parts[4:])})
    elif len(parts) >= 6 and parts[3] == "attachment":
        parsed.update({"kind": "attachment", "message_id": parts[4], "attachment_id": ":".join(parts[5:])})
    return parsed


def _account_object(account: ConnectedAccount, *, provider_key: str = "gmail") -> dict[str, Any]:
    label = account.display_name or account.email or account.external_subject or account.account_id
    return {
        "ref": account_ref(provider_key, account.account_id),
        "object_ref": account_ref(provider_key, account.account_id),
        "object_kind": MAIL_ACCOUNT_KIND,
        "id": account.account_id,
        "account_id": account.account_id,
        "provider": provider_key,
        "provider_id": account.provider_id,
        "connector_app_id": account.connector_app_id,
        "label": label,
        "display_name": account.display_name,
        "email": account.email,
        "external_subject": account.external_subject,
        "workspace": account.workspace,
        "claims": list(account.claims or ()),
        "connected": account.connected,
        "status": account.status,
        "connected_at": account.connected_at,
        "updated_at": account.updated_at,
        "metadata": dict(account.metadata or {}),
    }


def _message_object(row: Mapping[str, Any], *, provider_key: str = "gmail", account_id: str = "") -> dict[str, Any]:
    message_id = _text(row.get("id") or row.get("message_id"))
    headers = row.get("headers") if isinstance(row.get("headers"), Mapping) else {}
    subject = _text(row.get("subject") or headers.get("subject"))
    sender = _text(row.get("from") or headers.get("from"))
    date = _text(row.get("date") or headers.get("date"))
    ref = message_ref(provider_key, account_id, message_id) if message_id and account_id else ""
    return {
        "ref": ref,
        "object_ref": ref,
        "object_kind": MAIL_MESSAGE_KIND,
        "id": message_id,
        "message_id": message_id,
        "thread_id": _text(row.get("thread_id")),
        "provider": provider_key,
        "account_id": account_id,
        "subject": subject,
        "from": sender,
        "date": date,
        "snippet": _text(row.get("snippet")),
        "headers": dict(headers or {}),
        "attachment_count": row.get("attachment_count", 0),
        "inline_attachment_count": row.get("inline_attachment_count", 0),
        "attachments": list(row.get("attachments") or []),
        "inline_attachments": list(row.get("inline_attachments") or []),
    }


def _error_from_tool(result: Mapping[str, Any], *, request: NamedServiceRequest, default_code: str = "mail_operation_failed") -> NamedServiceResponse:
    error = result.get("error")
    error = error if isinstance(error, Mapping) else {}
    ret = result.get("ret")
    return NamedServiceResponse.error_response(
        code=_text(error.get("code")) or _text(result.get("error")) or default_code,
        message=_text(error.get("message")) or _text(result.get("message")) or "Mail operation failed.",
        status=400,
        details={"ret": ret} if ret is not None else {},
        provider={"provider_id": PROVIDER_ID},
        namespace=request.namespace or MAIL_NAMESPACE,
        object_ref=request.object_ref,
    )


@named_service_provider(
    provider_id=PROVIDER_ID,
    namespace=MAIL_NAMESPACE,
    refs=("mail:*",),
    object_kinds=(MAIL_ACCOUNT_KIND, MAIL_MESSAGE_KIND, MAIL_ATTACHMENT_KIND),
    search_scopes=MAIL_SEARCH_SCOPES,
    operations=_operations(),
    label="Mail",
    description="Provider-neutral mail namespace over user-connected accounts.",
    intro=MAIL_INTRO,
    metadata={"provider_catalog": MAIL_PROVIDER_CATALOG, "grant_hints": MAIL_GRANT_HINTS},
)
class MailNamedServiceProvider(NamedServiceProvider):
    def __init__(
        self,
        *,
        entrypoint: Any = None,
        bundle_id: str | None = None,
        connection_hub_bundle_id: str = DEFAULT_CONNECTION_HUB_BUNDLE_ID,
    ) -> None:
        super().__init__(mail_named_service_spec(bundle_id=bundle_id))
        self._entrypoint = entrypoint
        self._connection_hub_bundle_id = connection_hub_bundle_id
        self._gmail = GmailTools()
        if entrypoint is not None:
            bind_gmail_service(entrypoint)
            bind_gmail_integrations({"comm_context": getattr(entrypoint, "comm_context", None)})

    def _provider_identity(self) -> dict[str, Any]:
        return {"provider_id": PROVIDER_ID, "bundle_id": self.spec.bundle_id}

    async def _client(self, ctx: NamedServiceContext) -> DelegatedToKdcubeClient | None:
        user_id = _text(ctx.user_id)
        if not user_id or self._entrypoint is None:
            return None
        return await DelegatedToKdcubeClient.from_connection_hub(
            self._entrypoint,
            user_id=user_id,
            tenant=ctx.tenant,
            project=ctx.project,
            connection_hub_bundle_id=self._connection_hub_bundle_id,
        )

    async def _gmail_accounts(self, ctx: NamedServiceContext, *, claim: str = "") -> list[ConnectedAccount]:
        client = await self._client(ctx)
        if client is None:
            return []
        accounts = await client.list_accounts(provider_id=GMAIL_PROVIDER_ID)
        out = [
            account for account in accounts
            if account.connector_app_id == GMAIL_CONNECTOR_APP_ID
            and account.connected
            and (not claim or account.allows(claim))
        ]
        return out

    def _consent_required(
        self,
        *,
        ctx: NamedServiceContext,
        request: NamedServiceRequest,
        provider_id: str,
        connector_app_id: str,
        claim: str,
        message: str,
        account_id: str = "",
    ) -> NamedServiceResponse:
        payload = connected_account_consent_payload(
            tenant=ctx.tenant,
            project=ctx.project,
            connection_hub_bundle_id=self._connection_hub_bundle_id,
            missing=[
                {
                    "ok": False,
                    "tool_name": f"named_services.{MAIL_NAMESPACE}.{request.operation}",
                    "failures": [
                        {
                            "ok": False,
                            "provider_id": provider_id,
                            "connector_app_id": connector_app_id,
                            "claim": claim,
                            "account_id": account_id,
                            "error": "consent_required",
                            "message": message,
                        }
                    ],
                }
            ],
        )
        return NamedServiceResponse.error_response(
            code="connected_account_consent_required",
            message=message,
            status=403,
            details={"consent": payload.get("consent"), "payload": payload},
            provider=self._provider_identity(),
            namespace=request.namespace or MAIL_NAMESPACE,
            object_ref=request.object_ref,
        )

    async def provider_about(self, ctx: NamedServiceContext, request: NamedServiceRequest) -> NamedServiceResponse:
        del ctx
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=request.namespace or MAIL_NAMESPACE,
            extra={
                "title": "KDCube Mail",
                "description": (
                    "Provider-neutral mail namespace. Connected accounts can be Gmail, "
                    "iCloud, Yahoo, or another mail provider; Gmail is implemented now."
                ),
                "workflow": [
                    "Call object.list to see connected accounts.",
                    "Call object.search with namespace='mail' to search messages.",
                    "Call object.get with a mail:<provider>:<account_id>:message:<id> ref to read a message.",
                    "Call object.action download_attachments/send/forward for bounded mail actions.",
                ],
                "providers": MAIL_PROVIDER_CATALOG,
                "schema": MAIL_SCHEMA,
            },
        )

    async def provider_capabilities(self, ctx: NamedServiceContext, request: NamedServiceRequest) -> NamedServiceResponse:
        del ctx
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=request.namespace or MAIL_NAMESPACE,
            capabilities={
                "list": True,
                "search": True,
                "get": True,
                "upsert": False,
                "delete": False,
                "actions": [ACTION_DOWNLOAD_ATTACHMENTS, ACTION_SEND, ACTION_FORWARD],
                "providers": MAIL_PROVIDER_CATALOG,
                "grant_hints": MAIL_GRANT_HINTS,
                "connected_account_claims": MAIL_SCHEMA["connected_account_claims"],
            },
        )

    async def object_schema(self, ctx: NamedServiceContext, request: NamedServiceRequest) -> NamedServiceResponse:
        del ctx
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=request.namespace or MAIL_NAMESPACE,
            extra={"schema": MAIL_SCHEMA},
        )

    async def object_list(self, ctx: NamedServiceContext, request: NamedServiceRequest) -> NamedServiceResponse:
        filters = dict(request.filters or {})
        provider_filter = _text(filters.get("provider")).lower()
        items: list[dict[str, Any]] = []
        if not provider_filter or provider_filter == "gmail":
            for account in await self._gmail_accounts(ctx):
                items.append(_account_object(account, provider_key="gmail"))
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=request.namespace or MAIL_NAMESPACE,
            items=items,
            extra={"count": len(items), "providers": ["gmail"]},
        )

    async def object_search(self, ctx: NamedServiceContext, request: NamedServiceRequest) -> NamedServiceResponse:
        filters = dict(request.filters or {})
        provider_key = _text(filters.get("provider") or "gmail").lower()
        if provider_key != "gmail":
            return NamedServiceResponse.error_response(
                code="mail_provider_not_implemented",
                message=f"Mail provider is not implemented yet: {provider_key}",
                status=501,
                provider=self._provider_identity(),
                namespace=request.namespace or MAIL_NAMESPACE,
            )
        query = _text(filters.get("gmail_query") or request.query)
        account_id = _text(filters.get("account_id") or request.payload.get("account_id"))
        limit = _int(request.limit, default=5, maximum=10)
        accounts = [ConnectedAccount(account_id=account_id, provider_id=GMAIL_PROVIDER_ID, connector_app_id=GMAIL_CONNECTOR_APP_ID)] if account_id else await self._gmail_accounts(ctx, claim=GMAIL_READ_CLAIM)
        if not accounts:
            return self._consent_required(
                ctx=ctx,
                request=request,
                provider_id=GMAIL_PROVIDER_ID,
                connector_app_id=GMAIL_CONNECTOR_APP_ID,
                claim=GMAIL_READ_CLAIM,
                account_id=account_id,
                message="Connect a Gmail account and approve Gmail read access.",
            )

        items: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        per_account_limit = max(1, min(limit, 10))
        for account in accounts:
            result = await self._gmail.search_gmail(
                query=query,
                max_results=per_account_limit,
                account_id=account.account_id,
            )
            if not isinstance(result, Mapping) or not result.get("ok"):
                errors.append({
                    "account_id": account.account_id,
                    "error": result.get("error") if isinstance(result, Mapping) else "gmail_search_failed",
                    "ret": result.get("ret") if isinstance(result, Mapping) else None,
                })
                continue
            ret = result.get("ret") if isinstance(result.get("ret"), Mapping) else {}
            resolved_account_id = _text(ret.get("account_id") or account.account_id)
            for row in ret.get("messages") or []:
                if isinstance(row, Mapping):
                    items.append(_message_object(row, provider_key="gmail", account_id=resolved_account_id))

        if not items and errors:
            first = errors[0]
            err = first.get("error") if isinstance(first.get("error"), Mapping) else {}
            return NamedServiceResponse.error_response(
                code=_text(err.get("code")) or "gmail_search_failed",
                message=_text(err.get("message")) or "Gmail search failed.",
                status=400,
                details={"errors": errors},
                provider=self._provider_identity(),
                namespace=request.namespace or MAIL_NAMESPACE,
            )
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=request.namespace or MAIL_NAMESPACE,
            items=items[:limit],
            warnings=[{"code": "mail_account_error", "message": str(err)} for err in errors] or None,
            extra={"query": query, "provider": "gmail", "count": len(items[:limit]), "searched_accounts": len(accounts)},
        )

    async def object_get(self, ctx: NamedServiceContext, request: NamedServiceRequest) -> NamedServiceResponse:
        parsed = parse_mail_ref(request.object_ref or "")
        if parsed.get("kind") == "account":
            accounts = await self._gmail_accounts(ctx)
            account = next((item for item in accounts if item.account_id == parsed.get("account_id")), None)
            if account is None:
                return NamedServiceResponse.error_response(
                    code="mail_account_not_found",
                    message="Connected mail account was not found.",
                    status=404,
                    provider=self._provider_identity(),
                    namespace=request.namespace or MAIL_NAMESPACE,
                    object_ref=request.object_ref,
                )
            return NamedServiceResponse.ok_response(
                provider=self._provider_identity(),
                namespace=request.namespace or MAIL_NAMESPACE,
                object_ref=request.object_ref,
                object=_account_object(account, provider_key=parsed.get("provider") or "gmail"),
            )
        if parsed.get("kind") != "message" or parsed.get("provider") != "gmail":
            return NamedServiceResponse.error_response(
                code="mail_message_ref_required",
                message="object_ref must be mail:gmail:<account_id>:message:<message_id>.",
                status=400,
                provider=self._provider_identity(),
                namespace=request.namespace or MAIL_NAMESPACE,
                object_ref=request.object_ref,
            )
        include_html = bool(request.filters.get("include_html") or request.payload.get("include_html"))
        max_body_chars = _int(request.filters.get("max_body_chars") or request.payload.get("max_body_chars"), default=12000, maximum=24000)
        result = await self._gmail.read_gmail_message(
            message_id=parsed["message_id"],
            include_html=include_html,
            max_body_chars=max_body_chars,
            account_id=parsed["account_id"],
        )
        if not isinstance(result, Mapping) or not result.get("ok"):
            return _error_from_tool(result if isinstance(result, Mapping) else {}, request=request, default_code="gmail_read_failed")
        ret = result.get("ret") if isinstance(result.get("ret"), Mapping) else {}
        obj = _message_object(ret, provider_key="gmail", account_id=_text(ret.get("account_id") or parsed["account_id"]))
        obj.update(
            {
                "body_text": ret.get("body_text", ""),
                "body_text_truncated": bool(ret.get("body_text_truncated")),
                "usage": ret.get("usage") or {},
            }
        )
        if include_html:
            obj["body_html"] = ret.get("body_html", "")
            obj["body_html_truncated"] = bool(ret.get("body_html_truncated"))
        for row in obj.get("attachments") or []:
            if isinstance(row, dict):
                row.setdefault("ref", attachment_ref("gmail", obj["account_id"], obj["message_id"], _text(row.get("attachment_id"))))
        return NamedServiceResponse.ok_response(
            provider=self._provider_identity(),
            namespace=request.namespace or MAIL_NAMESPACE,
            object_ref=obj.get("ref") or request.object_ref,
            object=obj,
        )

    async def object_action(self, ctx: NamedServiceContext, request: NamedServiceRequest) -> NamedServiceResponse:
        del ctx
        action = _text(request.action or request.payload.get("action")).lower()
        payload = dict(request.payload or {})
        parsed = parse_mail_ref(request.object_ref or "")
        if action == ACTION_DOWNLOAD_ATTACHMENTS:
            if parsed.get("kind") != "message" or parsed.get("provider") != "gmail":
                return NamedServiceResponse.error_response(
                    code="mail_message_ref_required",
                    message="download_attachments requires object_ref mail:gmail:<account_id>:message:<message_id>.",
                    status=400,
                    provider=self._provider_identity(),
                    namespace=request.namespace or MAIL_NAMESPACE,
                    object_ref=request.object_ref,
                )
            result = await self._gmail.download_gmail_attachments(
                message_id=parsed["message_id"],
                attachment_ids=payload.get("attachment_ids") or "",
                include_inline=bool(payload.get("include_inline")),
                max_attachments=_int(payload.get("max_attachments"), default=10, maximum=20),
                max_bytes_per_attachment=_int(payload.get("max_bytes_per_attachment"), default=25 * 1024 * 1024, maximum=25 * 1024 * 1024),
                visibility=_text(payload.get("visibility") or "external"),
                account_id=parsed["account_id"],
            )
            if not isinstance(result, Mapping) or not result.get("ok"):
                return _error_from_tool(result if isinstance(result, Mapping) else {}, request=request, default_code="gmail_download_failed")
            return NamedServiceResponse.ok_response(
                provider=self._provider_identity(),
                namespace=request.namespace or MAIL_NAMESPACE,
                object_ref=request.object_ref,
                extra={"action": action, "result": result},
                ret={"attrs": {"action": action}, "extra": result.get("ret") or result},
            )

        if action == ACTION_SEND:
            account_id = _text(payload.get("account_id") or parsed.get("account_id"))
            result = await self._gmail.send_gmail(
                to=_text(payload.get("to")),
                subject=_text(payload.get("subject") or "KDCube message"),
                body_markdown=_text(payload.get("body_markdown") or payload.get("body")),
                cc=_text(payload.get("cc")),
                bcc=_text(payload.get("bcc")),
                body_html=_text(payload.get("body_html")),
                attachment_paths=payload.get("attachment_paths") or "",
                account_id=account_id,
            )
            if not isinstance(result, Mapping) or not result.get("ok"):
                return _error_from_tool(result if isinstance(result, Mapping) else {}, request=request, default_code="gmail_send_failed")
            ret = result.get("ret") if isinstance(result.get("ret"), Mapping) else {}
            obj = _message_object(ret, provider_key="gmail", account_id=_text(ret.get("account_id") or account_id))
            return NamedServiceResponse.ok_response(
                provider=self._provider_identity(),
                namespace=request.namespace or MAIL_NAMESPACE,
                object_ref=obj.get("ref") or request.object_ref,
                object=obj,
                extra={"action": action, "result": ret},
            )

        if action == ACTION_FORWARD:
            if parsed.get("kind") != "message" or parsed.get("provider") != "gmail":
                return NamedServiceResponse.error_response(
                    code="mail_message_ref_required",
                    message="forward requires object_ref mail:gmail:<account_id>:message:<message_id>.",
                    status=400,
                    provider=self._provider_identity(),
                    namespace=request.namespace or MAIL_NAMESPACE,
                    object_ref=request.object_ref,
                )
            result = await self._gmail.forward_gmail_message(
                message_id=parsed["message_id"],
                to=_text(payload.get("to")),
                note_markdown=_text(payload.get("note_markdown") or payload.get("note")),
                cc=_text(payload.get("cc")),
                bcc=_text(payload.get("bcc")),
                include_original_attachments=bool(payload.get("include_original_attachments")),
                attachment_paths=payload.get("attachment_paths") or "",
                account_id=parsed["account_id"],
            )
            if not isinstance(result, Mapping) or not result.get("ok"):
                return _error_from_tool(result if isinstance(result, Mapping) else {}, request=request, default_code="gmail_forward_failed")
            ret = result.get("ret") if isinstance(result.get("ret"), Mapping) else {}
            obj = _message_object(ret, provider_key="gmail", account_id=_text(ret.get("account_id") or parsed["account_id"]))
            return NamedServiceResponse.ok_response(
                provider=self._provider_identity(),
                namespace=request.namespace or MAIL_NAMESPACE,
                object_ref=obj.get("ref") or request.object_ref,
                object=obj,
                extra={"action": action, "result": ret},
            )

        return NamedServiceResponse.error_response(
            code="mail_action_not_supported",
            message=f"Unsupported mail action: {action or '<missing>'}.",
            status=400,
            provider=self._provider_identity(),
            namespace=request.namespace or MAIL_NAMESPACE,
            object_ref=request.object_ref,
        )


def make_mail_named_service_provider(
    *,
    entrypoint: Any = None,
    bundle_id: str | None = None,
    connection_hub_bundle_id: str = DEFAULT_CONNECTION_HUB_BUNDLE_ID,
) -> MailNamedServiceProvider:
    return MailNamedServiceProvider(
        entrypoint=entrypoint,
        bundle_id=bundle_id,
        connection_hub_bundle_id=connection_hub_bundle_id,
    )


__all__ = [
    "ACTION_DOWNLOAD_ATTACHMENTS",
    "ACTION_FORWARD",
    "ACTION_SEND",
    "MAIL_ACCOUNT_KIND",
    "MAIL_ATTACHMENT_KIND",
    "MAIL_GRANT_HINTS",
    "MAIL_MESSAGE_KIND",
    "MAIL_NAMESPACE",
    "MAIL_PROVIDER_CATALOG",
    "MAIL_SCHEMA",
    "MailNamedServiceProvider",
    "account_ref",
    "attachment_ref",
    "mail_named_service_spec",
    "make_mail_named_service_provider",
    "message_ref",
    "parse_mail_ref",
]

from __future__ import annotations

from typing import Any

import pytest

from kdcube_ai_app.apps.chat.sdk.integrations.mail.named_service import (
    ACTION_DOWNLOAD_ATTACHMENTS,
    ACTION_FORWARD,
    ACTION_SEND,
    MAIL_NAMESPACE,
    MailNamedServiceProvider,
    account_ref,
    attachment_ref,
    message_ref,
    parse_mail_ref,
)
from kdcube_ai_app.apps.chat.sdk.solutions.connections.delegated_to_kdcube.models import (
    ConnectedAccount,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers import (
    NamedServiceContext,
    NamedServiceRequest,
)
from kdcube_ai_app.apps.chat.sdk.solutions.named_services_providers.types import (
    OBJECT_ACTION,
    OBJECT_GET,
    OBJECT_LIST,
    OBJECT_SEARCH,
    OBJECT_SCHEMA,
    PROVIDER_ABOUT,
    PROVIDER_CAPABILITIES,
)


def _ctx() -> NamedServiceContext:
    return NamedServiceContext(tenant="demo", project="project", user_id="user-1")


def _account(account_id: str, *claims: str) -> ConnectedAccount:
    return ConnectedAccount(
        account_id=account_id,
        provider_id="google",
        connector_app_id="gmail",
        external_subject=f"google:{account_id}",
        email=f"{account_id}@example.test",
        display_name=f"Account {account_id}",
        claims=claims,
        credential_id=f"cred-{account_id}",
    )


class _FakeGmail:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def search_gmail(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("search_gmail", kwargs))
        account_id = kwargs["account_id"]
        return {
            "ok": True,
            "ret": {
                "account_id": account_id,
                "messages": [
                    {
                        "id": f"msg-{account_id}",
                        "thread_id": f"thread-{account_id}",
                        "subject": f"Receipt {account_id}",
                        "from": "billing@example.test",
                        "date": "Mon, 6 Jul 2026 10:00:00 +0000",
                        "snippet": "receipt",
                    }
                ],
            },
        }

    async def read_gmail_message(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("read_gmail_message", kwargs))
        return {
            "ok": True,
            "ret": {
                "id": kwargs["message_id"],
                "thread_id": "thread-1",
                "account_id": kwargs["account_id"],
                "subject": "Receipt",
                "from": "billing@example.test",
                "date": "Mon, 6 Jul 2026 10:00:00 +0000",
                "snippet": "receipt",
                "body_text": "body",
                "attachments": [{"attachment_id": "att-1", "filename": "invoice.pdf"}],
            },
        }

    async def download_gmail_attachments(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("download_gmail_attachments", kwargs))
        return {"ok": True, "ret": {"files": [{"logical_path": "conv:fi:turn/files/invoice.pdf"}]}}

    async def send_gmail(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("send_gmail", kwargs))
        return {
            "ok": True,
            "ret": {
                "id": "sent-1",
                "thread_id": "sent-thread",
                "account_id": kwargs["account_id"],
                "subject": kwargs["subject"],
                "snippet": "",
            },
        }

    async def forward_gmail_message(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("forward_gmail_message", kwargs))
        return {
            "ok": True,
            "ret": {
                "id": "fwd-1",
                "thread_id": "fwd-thread",
                "account_id": kwargs["account_id"],
                "subject": "Fwd",
                "snippet": "",
            },
        }


class _Provider(MailNamedServiceProvider):
    def __init__(self, accounts: list[ConnectedAccount] | None = None) -> None:
        super().__init__(entrypoint=None, bundle_id="kdcube-services@1-0")
        self.accounts = list(accounts or [])
        self._gmail = _FakeGmail()

    async def _gmail_accounts(self, ctx: NamedServiceContext, *, claim: str = "") -> list[ConnectedAccount]:
        del ctx
        return [account for account in self.accounts if not claim or account.allows(claim)]


def test_mail_refs_are_provider_neutral():
    assert account_ref("gmail", "acc-1") == "mail:gmail:acc-1"
    assert message_ref("gmail", "acc-1", "msg-1") == "mail:gmail:acc-1:message:msg-1"
    assert (
        attachment_ref("gmail", "acc-1", "msg-1", "att:1")
        == "mail:gmail:acc-1:attachment:msg-1:att:1"
    )
    assert parse_mail_ref("mail:gmail:acc-1") == {
        "provider": "gmail",
        "account_id": "acc-1",
        "kind": "account",
    }
    assert parse_mail_ref("mail:gmail:acc-1:message:msg:1") == {
        "provider": "gmail",
        "account_id": "acc-1",
        "kind": "message",
        "message_id": "msg:1",
    }


@pytest.mark.asyncio
async def test_about_capabilities_and_schema_expose_mail_contract():
    provider = _Provider()

    about = await provider.provider_about(_ctx(), NamedServiceRequest(operation=PROVIDER_ABOUT, namespace=MAIL_NAMESPACE))
    capabilities = await provider.provider_capabilities(
        _ctx(),
        NamedServiceRequest(operation=PROVIDER_CAPABILITIES, namespace=MAIL_NAMESPACE),
    )
    schema = await provider.object_schema(_ctx(), NamedServiceRequest(operation=OBJECT_SCHEMA, namespace=MAIL_NAMESPACE))

    assert about.ok is True
    assert "object.list" in about.ret["extra"]["workflow"][0]
    assert capabilities.ret["attrs"]["capabilities"]["actions"] == [
        ACTION_DOWNLOAD_ATTACHMENTS,
        ACTION_SEND,
        ACTION_FORWARD,
    ]
    assert schema.ret["extra"]["schema"]["namespace"] == MAIL_NAMESPACE
    assert schema.ret["extra"]["schema"]["refs"]["message"] == "mail:<provider>:<account_id>:message:<message_id>"


@pytest.mark.asyncio
async def test_object_list_returns_connected_mail_accounts():
    provider = _Provider([_account("acc-1", "gmail:read"), _account("acc-2", "gmail:send")])

    response = await provider.object_list(_ctx(), NamedServiceRequest(operation=OBJECT_LIST, namespace=MAIL_NAMESPACE))

    assert response.ok is True
    assert [item["ref"] for item in response.ret["items"]] == ["mail:gmail:acc-1", "mail:gmail:acc-2"]
    assert response.ret["items"][0]["email"] == "acc-1@example.test"


@pytest.mark.asyncio
async def test_search_fans_out_to_readable_gmail_accounts():
    provider = _Provider([_account("acc-1", "gmail:read"), _account("acc-2", "gmail:read"), _account("send-only", "gmail:send")])

    response = await provider.object_search(
        _ctx(),
        NamedServiceRequest(operation=OBJECT_SEARCH, namespace=MAIL_NAMESPACE, query="receipt", limit=5),
    )

    assert response.ok is True
    assert [item["ref"] for item in response.ret["items"]] == [
        "mail:gmail:acc-1:message:msg-acc-1",
        "mail:gmail:acc-2:message:msg-acc-2",
    ]
    assert [call[1]["account_id"] for call in provider._gmail.calls] == ["acc-1", "acc-2"]


@pytest.mark.asyncio
async def test_search_without_readable_account_returns_consent_payload():
    provider = _Provider([])

    response = await provider.object_search(
        _ctx(),
        NamedServiceRequest(operation=OBJECT_SEARCH, namespace=MAIL_NAMESPACE, query="receipt", limit=5),
    )

    assert response.ok is False
    assert response.status == 403
    assert response.error is not None
    assert response.error.code == "connected_account_consent_required"
    assert response.error.details["consent"]["provider_id"] == "google"
    assert response.error.details["consent"]["connector_app_id"] == "gmail"
    assert response.error.details["consent"]["claims"] == ["gmail:read"]


@pytest.mark.asyncio
async def test_get_reads_gmail_message_and_decorates_attachment_refs():
    provider = _Provider([_account("acc-1", "gmail:read")])

    response = await provider.object_get(
        _ctx(),
        NamedServiceRequest(
            operation=OBJECT_GET,
            namespace=MAIL_NAMESPACE,
            object_ref="mail:gmail:acc-1:message:msg-1",
        ),
    )

    assert response.ok is True
    obj = response.ret["object"]
    assert obj["ref"] == "mail:gmail:acc-1:message:msg-1"
    assert obj["attachments"][0]["ref"] == "mail:gmail:acc-1:attachment:msg-1:att-1"


@pytest.mark.asyncio
async def test_actions_dispatch_to_gmail_transport():
    provider = _Provider([_account("acc-1", "gmail:read", "gmail:send")])
    message = "mail:gmail:acc-1:message:msg-1"

    downloaded = await provider.object_action(
        _ctx(),
        NamedServiceRequest(
            operation=OBJECT_ACTION,
            namespace=MAIL_NAMESPACE,
            object_ref=message,
            action=ACTION_DOWNLOAD_ATTACHMENTS,
            payload={"attachment_ids": ["att-1"]},
        ),
    )
    sent = await provider.object_action(
        _ctx(),
        NamedServiceRequest(
            operation=OBJECT_ACTION,
            namespace=MAIL_NAMESPACE,
            object_ref="mail:gmail:acc-1",
            action=ACTION_SEND,
            payload={"to": "user@example.test", "subject": "Hello", "body_markdown": "Body"},
        ),
    )
    forwarded = await provider.object_action(
        _ctx(),
        NamedServiceRequest(
            operation=OBJECT_ACTION,
            namespace=MAIL_NAMESPACE,
            object_ref=message,
            action=ACTION_FORWARD,
            payload={"to": "user@example.test", "note_markdown": "FYI"},
        ),
    )

    assert downloaded.ok is True
    assert sent.ret["object"]["ref"] == "mail:gmail:acc-1:message:sent-1"
    assert forwarded.ret["object"]["ref"] == "mail:gmail:acc-1:message:fwd-1"
    assert [name for name, _ in provider._gmail.calls] == [
        "download_gmail_attachments",
        "send_gmail",
        "forward_gmail_message",
    ]

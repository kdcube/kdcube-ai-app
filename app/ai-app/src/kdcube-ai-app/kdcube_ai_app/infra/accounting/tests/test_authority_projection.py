from __future__ import annotations

from kdcube_ai_app.infra.accounting import _get_context, with_accounting


def test_with_accounting_projects_authority_without_client_economics_user_id():
    identity_authority = {
        "actor_user_id": "telegram_42",
        "economics_user_id": "platform-user-1",
        "platform_roles": ["kdcube:role:super-admin"],
    }

    with with_accounting(
        "test.component",
        user_id="telegram_42",
        tenant_id="tenant-a",
        project_id="project-a",
        identity_authority=identity_authority,
        metadata={"actor_user_id": "telegram_42"},
    ):
        context = _get_context().to_dict()
        enrichment = _get_context().event_enrichment

        assert context["user_id"] == "platform-user-1"
        assert "user_type" not in context
        assert context["identity_authority"] == identity_authority
        assert enrichment["metadata"]["actor_user_id"] == "telegram_42"
        assert enrichment["metadata"]["economics_user_id"] == "platform-user-1"
        assert enrichment["metadata"]["identity_authority"] == identity_authority

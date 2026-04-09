from kdcube_cli.cli import _descriptor_fast_path_reasons


def test_descriptor_fast_path_accepts_complete_release_descriptor():
    assembly = {
        "context": {"tenant": "cisoteria", "project": "chatbot"},
        "platform": {"repo": "kdcube/kdcube-ai-app", "ref": "2026.4.04.318"},
        "secrets": {"provider": "secrets-file"},
        "auth": {"type": "simple"},
        "proxy": {"ssl": False},
        "storage": {
            "workspace": {"type": "git", "repo": "https://github.com/kdcube/agentic-workspace.git"},
            "claude_code_session": {"type": "git", "repo": "https://github.com/kdcube/agentic-workspace.git"},
        },
    }

    reasons = _descriptor_fast_path_reasons(
        assembly,
        have_secrets=True,
        have_gateway=True,
        latest=False,
    )

    assert reasons == []


def test_descriptor_fast_path_requires_platform_ref_without_latest():
    assembly = {
        "context": {"tenant": "cisoteria", "project": "chatbot"},
        "secrets": {"provider": "secrets-file"},
        "auth": {"type": "simple"},
        "proxy": {"ssl": False},
    }

    reasons = _descriptor_fast_path_reasons(
        assembly,
        have_secrets=True,
        have_gateway=True,
        latest=False,
    )

    assert "assembly platform.ref is required unless --latest is used" in reasons


def test_descriptor_fast_path_requires_cognito_fields():
    assembly = {
        "context": {"tenant": "cisoteria", "project": "chatbot"},
        "platform": {"ref": "2026.4.04.318"},
        "secrets": {"provider": "secrets-file"},
        "auth": {
            "type": "cognito",
            "cognito": {
                "region": "eu-west-1",
                "user_pool_id": "pool",
            },
        },
        "proxy": {"ssl": False},
    }

    reasons = _descriptor_fast_path_reasons(
        assembly,
        have_secrets=True,
        have_gateway=True,
        latest=False,
    )

    assert "assembly auth.cognito.app_client_id is required" in reasons


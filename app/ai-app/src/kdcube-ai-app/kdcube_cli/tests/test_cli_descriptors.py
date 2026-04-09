from pathlib import Path

from kdcube_cli.cli import _descriptor_fast_path_reasons, _load_bundle_ids_from_descriptor


def test_descriptor_fast_path_accepts_complete_release_descriptor():
    assembly = {
        "context": {"tenant": "example-product", "project": "chatbot"},
        "platform": {"repo": "kdcube/kdcube-ai-app", "ref": "2026.4.04.318"},
        "secrets": {"provider": "secrets-file"},
        "paths": {"host_bundles_path": "/Users/demo/bundles"},
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
        release=None,
    )

    assert reasons == []


def test_descriptor_fast_path_requires_platform_ref_without_latest():
    assembly = {
        "context": {"tenant": "example-product", "project": "chatbot"},
        "secrets": {"provider": "secrets-file"},
        "paths": {"host_bundles_path": "/Users/demo/bundles"},
        "auth": {"type": "simple"},
        "proxy": {"ssl": False},
    }

    reasons = _descriptor_fast_path_reasons(
        assembly,
        have_secrets=True,
        have_gateway=True,
        latest=False,
        release=None,
    )

    assert "assembly platform.ref is required unless --latest or --release is used" in reasons


def test_descriptor_fast_path_requires_cognito_fields():
    assembly = {
        "context": {"tenant": "example-product", "project": "chatbot"},
        "platform": {"ref": "2026.4.04.318"},
        "secrets": {"provider": "secrets-file"},
        "paths": {"host_bundles_path": "/Users/demo/bundles"},
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
        release=None,
    )

    assert "assembly auth.cognito.app_client_id is required" in reasons


def test_descriptor_fast_path_accepts_explicit_release_without_platform_ref():
    assembly = {
        "context": {"tenant": "example-product", "project": "chatbot"},
        "secrets": {"provider": "secrets-file"},
        "paths": {"host_bundles_path": "/Users/demo/bundles"},
        "auth": {"type": "simple"},
        "proxy": {"ssl": False},
    }

    reasons = _descriptor_fast_path_reasons(
        assembly,
        have_secrets=True,
        have_gateway=True,
        latest=False,
        release="2026.4.04.318",
    )

    assert reasons == []


def test_descriptor_fast_path_requires_host_bundles_path_for_noninteractive_local_bundle_installs():
    assembly = {
        "context": {"tenant": "example-product", "project": "chatbot"},
        "platform": {"ref": "2026.4.04.318"},
        "secrets": {"provider": "secrets-file"},
        "auth": {"type": "simple"},
        "proxy": {"ssl": False},
    }

    reasons = _descriptor_fast_path_reasons(
        assembly,
        have_secrets=True,
        have_gateway=True,
        latest=False,
        release=None,
    )

    assert "assembly paths.host_bundles_path is required for non-interactive local bundle installs" in reasons


def test_load_bundle_ids_from_bundles_yaml(tmp_path: Path):
    path = tmp_path / "bundles.yaml"
    path.write_text(
        """
bundles:
  demo.bundle@1.0.0:
    path: /bundles/demo
    module: demo.entrypoint
  another.bundle@2.0.0:
    path: /bundles/another
    module: another.entrypoint
""".strip()
    )

    assert _load_bundle_ids_from_descriptor(path) == {
        "demo.bundle@1.0.0",
        "another.bundle@2.0.0",
    }


def test_load_bundle_ids_from_assembly_yaml(tmp_path: Path):
    path = tmp_path / "assembly.yaml"
    path.write_text(
        """
context:
  tenant: demo
  project: chatbot
bundles:
  demo.bundle@1.0.0:
    path: /bundles/demo
    module: demo.entrypoint
""".strip()
    )

    assert _load_bundle_ids_from_descriptor(path) == {"demo.bundle@1.0.0"}

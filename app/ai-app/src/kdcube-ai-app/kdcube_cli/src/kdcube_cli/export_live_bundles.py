# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import yaml
from rich.console import Console


def aws_cli_env(*, region: str | None, profile: str | None) -> dict[str, str]:
    env = os.environ.copy()
    if region:
        env["AWS_REGION"] = region
        env["AWS_DEFAULT_REGION"] = region
    if profile:
        env["AWS_PROFILE"] = profile
    return env


def aws_secret_json(
    *,
    secret_id: str,
    region: str | None,
    profile: str | None,
    required: bool,
) -> dict[str, object] | None:
    cmd = [
        "aws",
        "secretsmanager",
        "get-secret-value",
        "--secret-id",
        secret_id,
        "--query",
        "SecretString",
        "--output",
        "text",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=aws_cli_env(region=region, profile=profile),
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        if not required and "ResourceNotFoundException" in stderr:
            return None
        raise SystemExit(f"Failed to read AWS secret {secret_id}: {stderr or proc.stdout.strip()}")
    raw = (proc.stdout or "").strip()
    if not raw or raw == "None":
        return {} if required else None
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise SystemExit(f"AWS secret {secret_id} does not contain valid JSON.") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"AWS secret {secret_id} must contain a JSON object.")
    return payload


def resolve_aws_sm_prefix(*, tenant: str, project: str, explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip().strip("/")
    tenant_text = str(tenant or "").strip()
    project_text = str(project or "").strip()
    if not tenant_text or not project_text:
        raise SystemExit("--tenant and --project are required unless --aws-sm-prefix is provided.")
    return f"kdcube/{tenant_text}/{project_text}"


def _empty_bundles_secrets_payload() -> dict[str, object]:
    return {
        "bundles": {
            "version": "1",
            "items": [],
        }
    }


def _export_live_bundle_descriptors_from_files(
    console: Console,
    *,
    bundles_path: Path,
    bundles_secrets_path: Path | None,
    out_dir: Path,
) -> None:
    if not bundles_path.exists():
        raise SystemExit(f"Local bundles descriptor not found: {bundles_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_bundles_path = out_dir / "bundles.yaml"
    out_bundles_path.write_text(bundles_path.read_text())

    out_bundles_secrets_path = out_dir / "bundles.secrets.yaml"
    if bundles_secrets_path is not None and bundles_secrets_path.exists():
        out_bundles_secrets_path.write_text(bundles_secrets_path.read_text())
    else:
        out_bundles_secrets_path.write_text(
            yaml.safe_dump(_empty_bundles_secrets_payload(), sort_keys=False, allow_unicode=True)
        )

    console.print("[green]Exported effective live bundle descriptors.[/green]")
    console.print(f"[dim]Authority:[/dim] mounted local descriptors")
    console.print(f"[dim]source bundles.yaml:[/dim] {bundles_path}")
    if bundles_secrets_path is not None and bundles_secrets_path.exists():
        console.print(f"[dim]source bundles.secrets.yaml:[/dim] {bundles_secrets_path}")
    else:
        console.print("[dim]source bundles.secrets.yaml:[/dim] <not configured>")
    console.print(f"[dim]bundles.yaml:[/dim] {out_bundles_path}")
    console.print(f"[dim]bundles.secrets.yaml:[/dim] {out_bundles_secrets_path}")


def export_live_bundle_descriptors(
    console: Console,
    *,
    tenant: str,
    project: str,
    out_dir: Path,
    aws_region: str | None,
    aws_profile: str | None,
    aws_sm_prefix: str | None,
    bundles_path: Path | None = None,
    bundles_secrets_path: Path | None = None,
) -> None:
    if bundles_path is not None:
        _export_live_bundle_descriptors_from_files(
            console,
            bundles_path=bundles_path,
            bundles_secrets_path=bundles_secrets_path,
            out_dir=out_dir,
        )
        return

    prefix = resolve_aws_sm_prefix(tenant=tenant, project=project, explicit=aws_sm_prefix)
    meta_secret_id = f"{prefix}/bundles-meta"
    meta = aws_secret_json(
        secret_id=meta_secret_id,
        region=aws_region,
        profile=aws_profile,
        required=True,
    )
    bundle_ids = [
        str(item).strip()
        for item in (meta.get("bundle_ids") or [])
        if str(item).strip()
    ]
    if not bundle_ids:
        raise SystemExit(
            f"{meta_secret_id} does not contain bundle_ids. "
            "Bootstrap the authoritative bundle descriptor store first by applying a live bundle update or reload-authority."
        )

    default_bundle_id = str(meta.get("default_bundle_id") or "").strip() or None
    bundles_items: list[dict[str, object]] = []
    bundles_secrets_items: list[dict[str, object]] = []

    for bundle_id in bundle_ids:
        descriptor = aws_secret_json(
            secret_id=f"{prefix}/bundles/{bundle_id}/descriptor",
            region=aws_region,
            profile=aws_profile,
            required=True,
        ) or {}
        secrets = aws_secret_json(
            secret_id=f"{prefix}/bundles/{bundle_id}/secrets",
            region=aws_region,
            profile=aws_profile,
            required=False,
        ) or {}
        descriptor_payload = {"id": bundle_id, **descriptor}
        props = descriptor_payload.pop("props", None)
        if isinstance(props, dict) and props:
            descriptor_payload["config"] = props
        bundles_items.append(descriptor_payload)
        bundles_secrets_items.append({"id": bundle_id, "secrets": secrets})

    bundles_payload: dict[str, object] = {"bundles": {"version": "1", "items": bundles_items}}
    if default_bundle_id:
        bundles_payload["bundles"]["default_bundle_id"] = default_bundle_id

    bundles_secrets_payload: dict[str, object] = {
        "bundles": {"version": "1", "items": bundles_secrets_items}
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    bundles_path = out_dir / "bundles.yaml"
    bundles_secrets_path = out_dir / "bundles.secrets.yaml"
    bundles_path.write_text(yaml.safe_dump(bundles_payload, sort_keys=False, allow_unicode=True))
    bundles_secrets_path.write_text(
        yaml.safe_dump(bundles_secrets_payload, sort_keys=False, allow_unicode=True)
    )

    console.print("[green]Exported effective live bundle descriptors.[/green]")
    console.print(f"[dim]AWS SM prefix:[/dim] {prefix}")
    console.print(f"[dim]bundles.yaml:[/dim] {bundles_path}")
    console.print(f"[dim]bundles.secrets.yaml:[/dim] {bundles_secrets_path}")

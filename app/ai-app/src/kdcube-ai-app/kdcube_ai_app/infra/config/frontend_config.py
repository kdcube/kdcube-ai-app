# SPDX-License-Identifier: MIT
from __future__ import annotations

import sys
from pathlib import Path


def _ensure_cli_src_importable() -> None:
    monorepo_root = Path(__file__).resolve().parents[3]
    cli_src = monorepo_root / "kdcube_cli" / "src"
    if cli_src.exists():
        cli_src_text = str(cli_src)
        if cli_src_text not in sys.path:
            sys.path.insert(0, cli_src_text)


_ensure_cli_src_importable()

try:
    from kdcube_cli.frontend_config import (
        as_text,
        build_frontend_config,
        build_frontend_config_from_assembly,
        deep_merge,
        get_nested,
        is_placeholder,
        load_json_file,
        load_yaml_descriptor,
        normalize_routes_prefix,
        write_frontend_config_file,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"kdcube_cli", "kdcube_cli.frontend_config"}:
        raise
    sys.modules.pop("kdcube_cli", None)
    _ensure_cli_src_importable()
    from kdcube_cli.frontend_config import (
        as_text,
        build_frontend_config,
        build_frontend_config_from_assembly,
        deep_merge,
        get_nested,
        is_placeholder,
        load_json_file,
        load_yaml_descriptor,
        normalize_routes_prefix,
        write_frontend_config_file,
    )


__all__ = [
    "as_text",
    "is_placeholder",
    "normalize_routes_prefix",
    "get_nested",
    "deep_merge",
    "load_yaml_descriptor",
    "load_json_file",
    "build_frontend_config",
    "build_frontend_config_from_assembly",
    "write_frontend_config_file",
]

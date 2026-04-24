from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import httpx


@dataclass(frozen=True)
class NodeBridgeResponse:
    ok: bool
    status: int
    data: Any
    error: Any = None


class BundleNodeBackendBridge:
    """
    Start and call a bundle-local Node sidecar.

    The Python bundle remains the KDCube-facing surface. Node stays behind an
    explicit local sidecar boundary.
    """

    def __init__(
        self,
        *,
        bundle: Any,
        name: str = "node-backend",
        source_dir: str = "backend_src",
        entry_module: str = "src/bridge_app.ts",
        allowed_prefixes: Sequence[str] = (),
        host: str = "127.0.0.1",
        port: Optional[int] = 0,
        ready_timeout_sec: float = 30.0,
        extra_env: Optional[Mapping[str, Any]] = None,
        live_config: Any = None,
        reconfigure_path: Optional[str] = None,
    ) -> None:
        self.bundle = bundle
        self.name = str(name or "node-backend").strip() or "node-backend"
        self.source_dir = str(source_dir or "backend_src").strip() or "backend_src"
        self.entry_module = str(entry_module or "src/bridge_app.ts").strip() or "src/bridge_app.ts"
        self.allowed_prefixes = tuple(
            str(item).strip()
            for item in (allowed_prefixes or ())
            if str(item).strip()
        )
        self.host = str(host or "127.0.0.1").strip() or "127.0.0.1"
        self.port = port
        self.ready_timeout_sec = float(ready_timeout_sec or 30.0)
        self.extra_env = {
            str(key): str(value)
            for key, value in (extra_env or {}).items()
            if value is not None
        }
        self.live_config = live_config
        self.reconfigure_path = str(reconfigure_path or "").strip() or None

    def _bundle_root(self) -> Path:
        resolver = getattr(self.bundle, "_bundle_root", None)
        if resolver is None:
            raise RuntimeError("Bundle entrypoint does not expose _bundle_root()")
        root = resolver()
        if not root:
            raise RuntimeError("Bundle root is unavailable for Node bridge startup")
        return Path(str(root)).resolve()

    def source_root(self) -> Path:
        root = (self._bundle_root() / self.source_dir).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Node backend source dir not found: {root}")
        return root

    def entry_file(self) -> Path:
        source_root = self.source_root()
        entry = (source_root / self.entry_module).resolve()
        if entry.exists():
            return entry
        if entry.suffix == ".js":
            ts_entry = entry.with_suffix(".ts")
            if ts_entry.exists():
                return ts_entry
        raise FileNotFoundError(f"Node bridge entry module not found: {entry}")

    @staticmethod
    def _stable_json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _startup_payload(self) -> dict[str, Any]:
        return {
            "bundle_root": str(self._bundle_root()),
            "source_root": str(self.source_root()),
            "entry_file": str(self.entry_file()),
            "allowed_prefixes": list(self.allowed_prefixes),
            "host": self.host,
            "extra_env": dict(sorted(self.extra_env.items())),
        }

    def startup_fingerprint(self) -> str:
        payload = self._stable_json(self._startup_payload()).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def live_config_fingerprint(self) -> Optional[str]:
        if self.live_config is None or not self.reconfigure_path:
            return None
        payload = self._stable_json(self.live_config).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def ensure_started(self):
        startup_fingerprint = self.startup_fingerprint()
        existing = self.bundle.get_local_sidecar(self.name)
        if existing is not None:
            existing_fp = existing.runtime_metadata.get("startup_fingerprint")
            if existing_fp and existing_fp != startup_fingerprint:
                self.bundle.stop_local_sidecar(self.name)

        sidecar_dir = Path(__file__).resolve().parent / "sidecar"
        cli_path = sidecar_dir / "cli.mjs"
        loader_path = sidecar_dir / "ts_loader.mjs"
        env = {
            "KDCUBE_NODE_BRIDGE_ENTRY": str(self.entry_file()),
            "KDCUBE_NODE_BRIDGE_SOURCE_ROOT": str(self.source_root()),
            "KDCUBE_NODE_BRIDGE_ALLOWED_PREFIXES": json.dumps(list(self.allowed_prefixes)),
            **self.extra_env,
        }
        return self.bundle.ensure_local_sidecar(
            name=self.name,
            command=[
                self.resolve_node_binary(),
                "--loader",
                str(loader_path),
                str(cli_path),
            ],
            cwd=str(self.source_root()),
            env=env,
            host=self.host,
            port=self.port,
            ready_path="/healthz",
            ready_timeout_sec=self.ready_timeout_sec,
            startup_fingerprint=startup_fingerprint,
        )

    async def _ensure_live_config(self, handle, *, timeout_sec: float) -> Any:
        live_fingerprint = self.live_config_fingerprint()
        if live_fingerprint is None or not self.reconfigure_path:
            return handle
        if handle.runtime_metadata.get("live_config_fingerprint") == live_fingerprint:
            return handle
        if not handle.base_url:
            raise RuntimeError("Node bridge sidecar did not expose a base URL for reconfigure")

        async with httpx.AsyncClient(timeout=float(timeout_sec or 15.0)) as client:
            response = await client.post(
                f"{handle.base_url}{self.reconfigure_path}",
                json={
                    "config": self.live_config,
                    "fingerprint": live_fingerprint,
                },
            )

        try:
            payload = response.json() if response.content else None
        except Exception:
            payload = {"raw": response.text}

        if not response.is_success:
            raise RuntimeError(
                f"Node bridge reconfigure failed: status={response.status_code} payload={payload!r}"
            )

        updated = self.bundle.update_local_sidecar_runtime_metadata(
            self.name,
            runtime_metadata={"live_config_fingerprint": live_fingerprint},
        )
        return updated or handle

    async def request_json(
        self,
        *,
        method: str,
        path: str,
        body: Any = None,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, Any]] = None,
        timeout_sec: float = 15.0,
    ) -> NodeBridgeResponse:
        request_path = str(path or "").strip()
        if not request_path.startswith("/"):
            raise ValueError(f"Bridge path must start with '/': {request_path!r}")

        handle = self.ensure_started()
        handle = await self._ensure_live_config(handle, timeout_sec=timeout_sec)
        if not handle.base_url:
            raise RuntimeError("Node bridge sidecar did not expose a base URL")

        request_kwargs = {
            "params": dict(query or {}),
            "headers": {str(k): str(v) for k, v in (headers or {}).items()},
        }
        if body is not None:
            request_kwargs["json"] = body

        async with httpx.AsyncClient(timeout=float(timeout_sec or 15.0)) as client:
            response = await client.request(
                str(method or "GET").upper(),
                f"{handle.base_url}{request_path}",
                **request_kwargs,
            )

        if response.content:
            try:
                payload: Any = response.json()
            except Exception:
                payload = {"raw": response.text}
        else:
            payload = None

        if isinstance(payload, dict) and "status" in payload and ("data" in payload or "error" in payload):
            return NodeBridgeResponse(
                ok=bool(payload.get("ok", response.is_success)),
                status=int(payload.get("status") or response.status_code),
                data=payload.get("data"),
                error=payload.get("error"),
            )

        return NodeBridgeResponse(
            ok=response.is_success,
            status=response.status_code,
            data=payload,
            error=None if response.is_success else payload,
        )

    async def get_json(
        self,
        path: str,
        *,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, Any]] = None,
        timeout_sec: float = 15.0,
    ) -> NodeBridgeResponse:
        return await self.request_json(
            method="GET",
            path=path,
            query=query,
            headers=headers,
            timeout_sec=timeout_sec,
        )

    async def post_json(
        self,
        path: str,
        *,
        body: Any = None,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, Any]] = None,
        timeout_sec: float = 15.0,
    ) -> NodeBridgeResponse:
        return await self.request_json(
            method="POST",
            path=path,
            body=body,
            query=query,
            headers=headers,
            timeout_sec=timeout_sec,
        )

    @staticmethod
    def resolve_node_binary() -> str:
        direct = shutil.which("node")
        if direct:
            return direct

        nvm_root = Path.home() / ".nvm" / "versions" / "node"
        if nvm_root.exists():
            for version_dir in sorted(nvm_root.iterdir(), reverse=True):
                candidate = version_dir / "bin" / "node"
                if candidate.exists():
                    return str(candidate)

        raise FileNotFoundError(
            "Node runtime is not available. Install node or use a chat-proc image that includes it."
        )

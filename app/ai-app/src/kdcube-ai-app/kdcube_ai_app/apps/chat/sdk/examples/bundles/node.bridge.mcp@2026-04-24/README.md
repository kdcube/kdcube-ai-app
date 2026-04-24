# Node Bridge + MCP Example

This bundle demonstrates a bundle-local Node/TypeScript backend started as a
process-local sidecar and called from Python-owned bundle APIs and MCP tools.

Surfaces:
- `node_status` API
- `node_search` API
- `node_tools` MCP endpoint

What it demonstrates:
- startup props:
  - `node_bridge.source_dir`
  - `node_bridge.entry_module`
  - `node_bridge.allowed_prefixes`
- live props:
  - `node_bridge.runtime_config`
- startup-prop change:
  - sidecar restarts lazily on next use
- live-prop change:
  - sidecar receives `POST /__kdcube/reconfigure` on next use

Source layout:

```text
node.bridge.mcp@2026-04-24/
  entrypoint.py
  node_mcp_tools.py
  backend_src/
    package.json
    src/
      bridge_app.ts
```

The example uses only built-in Node modules, so there is no `npm install`
step required to run it.

let runtimeConfig = {
  statusLabel: 'node-sidecar',
  searchPrefix: 'Node match for',
}

function normalizeRuntimeConfig(input) {
  const patch = input && typeof input === 'object' ? input : {}
  const next = {
    statusLabel: String(patch.statusLabel || runtimeConfig.statusLabel || 'node-sidecar').trim() || 'node-sidecar',
    searchPrefix: String(patch.searchPrefix || runtimeConfig.searchPrefix || 'Node match for').trim() || 'Node match for',
  }
  runtimeConfig = next
  return next
}

export async function registerBridgeRoutes(registry, context = {}) {
  registry.get('/api/projects/status', async () => {
    return {
      status: 200,
      data: {
        ok: true,
        runtime: runtimeConfig.statusLabel,
        bundle_root: context.bundleRoot || null,
        source_root: context.sourceRoot || null,
        storage_root: context.storageRoot || null,
        live_config: context.liveConfig || runtimeConfig,
      },
    }
  })

  registry.post('/api/projects/search', async ({ body }) => {
    const query = String(body?.query || '').trim()
    const items = query
      ? [
          {
            id: 'node-bridge-sample-1',
            title: `${runtimeConfig.searchPrefix} ${query}`,
            source: 'node.bridge.mcp',
          },
        ]
      : []

    return {
      status: 200,
      data: {
        ok: true,
        items,
        total: items.length,
      },
    }
  })
}

export async function reconfigureBridge({ config, fingerprint, context } = {}) {
  const applied = normalizeRuntimeConfig(config)
  if (context && typeof context === 'object') {
    context.liveConfig = applied
    context.liveConfigFingerprint = fingerprint ? String(fingerprint) : null
  }
  return {
    status: 200,
    data: {
      ok: true,
      applied: true,
      fingerprint: fingerprint ? String(fingerprint) : null,
      runtime_config: applied,
    },
  }
}

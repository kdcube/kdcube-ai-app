import http from 'node:http'
import { pathToFileURL } from 'node:url'

const HOST = process.env.HOST || '127.0.0.1'
const PORT = Number.parseInt(process.env.PORT || '0', 10) || 0
const ENTRY_FILE = String(process.env.KDCUBE_NODE_BRIDGE_ENTRY || '').trim()
const SOURCE_ROOT = String(process.env.KDCUBE_NODE_BRIDGE_SOURCE_ROOT || '').trim()

function readAllowedPrefixes() {
  try {
    const raw = JSON.parse(process.env.KDCUBE_NODE_BRIDGE_ALLOWED_PREFIXES || '[]')
    if (!Array.isArray(raw)) {
      return []
    }
    return raw
      .map((item) => String(item || '').trim())
      .filter(Boolean)
  } catch {
    return []
  }
}

const ALLOWED_PREFIXES = readAllowedPrefixes()
const SUPPORTED_METHODS = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])

function ensureEntryFile() {
  if (!ENTRY_FILE) {
    throw new Error('KDCUBE_NODE_BRIDGE_ENTRY is required')
  }
}

function buildQueryObject(searchParams) {
  const out = {}
  for (const [key, value] of searchParams.entries()) {
    if (Object.prototype.hasOwnProperty.call(out, key)) {
      const current = out[key]
      out[key] = Array.isArray(current) ? [...current, value] : [current, value]
      continue
    }
    out[key] = value
  }
  return out
}

async function readJsonBody(req) {
  const chunks = []
  for await (const chunk of req) {
    chunks.push(chunk)
  }
  if (chunks.length === 0) {
    return null
  }
  const raw = Buffer.concat(chunks).toString('utf-8').trim()
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw)
  } catch (error) {
    const invalid = new Error(error?.message || 'Invalid JSON request body')
    invalid.status = 400
    throw invalid
  }
}

function sendJson(res, status, payload, extraHeaders = {}) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    ...extraHeaders,
  })
  res.end(`${JSON.stringify(payload)}\n`)
}

function normalizeHandlerResult(result) {
  if (!result || typeof result !== 'object' || Array.isArray(result)) {
    return { status: 200, data: result, headers: {} }
  }
  const status = Number.parseInt(String(result.status || '200'), 10) || 200
  if (Object.prototype.hasOwnProperty.call(result, 'data')) {
    return { status, data: result.data, headers: result.headers || {} }
  }
  if (Object.prototype.hasOwnProperty.call(result, 'body')) {
    return { status, data: result.body, headers: result.headers || {} }
  }
  return { status, data: result, headers: {} }
}

function createRegistry() {
  const routes = new Map()

  function register(method, routePath, handler) {
    const normalizedMethod = String(method || '').toUpperCase()
    const normalizedPath = String(routePath || '').trim()
    if (!SUPPORTED_METHODS.has(normalizedMethod)) {
      throw new Error(`Unsupported bridge method: ${normalizedMethod}`)
    }
    if (!normalizedPath.startsWith('/')) {
      throw new Error(`Bridge route must start with '/': ${normalizedPath}`)
    }
    if (ALLOWED_PREFIXES.length && !ALLOWED_PREFIXES.some((prefix) => normalizedPath.startsWith(prefix))) {
      throw new Error(`Bridge route outside allowed prefixes: ${normalizedPath}`)
    }
    if (typeof handler !== 'function') {
      throw new Error(`Bridge handler must be a function for ${normalizedMethod} ${normalizedPath}`)
    }
    routes.set(`${normalizedMethod} ${normalizedPath}`, handler)
  }

  return {
    routes,
    get(path, handler) {
      register('GET', path, handler)
    },
    post(path, handler) {
      register('POST', path, handler)
    },
    put(path, handler) {
      register('PUT', path, handler)
    },
    patch(path, handler) {
      register('PATCH', path, handler)
    },
    delete(path, handler) {
      register('DELETE', path, handler)
    },
  }
}

async function loadBridgeModule() {
  ensureEntryFile()
  const moduleUrl = pathToFileURL(ENTRY_FILE).href
  const loaded = await import(moduleUrl)
  if (typeof loaded.registerBridgeRoutes !== 'function') {
    throw new Error(
      `Node bridge entry must export registerBridgeRoutes(registry, context): ${ENTRY_FILE}`,
    )
  }
  return loaded
}

async function main() {
  const registry = createRegistry()
  const bridgeModule = await loadBridgeModule()
  const runtimeContext = {
    bundleRoot: String(process.env.KDCUBE_BUNDLE_ROOT || '').trim() || null,
    storageRoot: String(process.env.KDCUBE_BUNDLE_STORAGE_ROOT || '').trim() || null,
    sourceRoot: SOURCE_ROOT || null,
    liveConfig: null,
    liveConfigFingerprint: null,
  }

  await bridgeModule.registerBridgeRoutes(registry, runtimeContext)

  const server = http.createServer(async (req, res) => {
    const requestUrl = new URL(req.url || '/', `http://${HOST}:${PORT || 0}`)
    const pathname = requestUrl.pathname || '/'
    const method = String(req.method || 'GET').toUpperCase()

    if (pathname === '/healthz') {
      sendJson(res, 200, {
        ok: true,
        status: 200,
        data: {
          runtime: 'node-sidecar',
          entry: ENTRY_FILE,
          allowed_prefixes: ALLOWED_PREFIXES,
          live_config_fingerprint: runtimeContext.liveConfigFingerprint,
        },
      })
      return
    }

    if (pathname === '/__kdcube/reconfigure') {
      if (method !== 'POST') {
        sendJson(res, 405, {
          ok: false,
          status: 405,
          error: { code: 'method_not_allowed', message: 'Use POST for /__kdcube/reconfigure' },
        })
        return
      }
      try {
        const body = await readJsonBody(req)
        const config = body && typeof body === 'object' ? (body.config ?? null) : null
        const fingerprint = body && typeof body === 'object' ? (body.fingerprint ?? null) : null
        runtimeContext.liveConfig = config
        runtimeContext.liveConfigFingerprint = fingerprint ? String(fingerprint) : null
        if (typeof bridgeModule.reconfigureBridge === 'function') {
          const outcome = await bridgeModule.reconfigureBridge({
            config: runtimeContext.liveConfig,
            fingerprint: runtimeContext.liveConfigFingerprint,
            context: runtimeContext,
          })
          const normalized = normalizeHandlerResult(outcome)
          sendJson(
            res,
            normalized.status,
            {
              ok: normalized.status < 400,
              status: normalized.status,
              data: normalized.data,
            },
            normalized.headers,
          )
          return
        }
        sendJson(res, 200, {
          ok: true,
          status: 200,
          data: {
            applied: true,
            fingerprint: runtimeContext.liveConfigFingerprint,
          },
        })
        return
      } catch (error) {
        const status = Number.parseInt(String(error?.status || '500'), 10) || 500
        sendJson(res, status, {
          ok: false,
          status,
          error: {
            code: error?.code || 'node_bridge_reconfigure_error',
            message: error?.message || 'Node bridge reconfigure failed',
          },
        })
        return
      }
    }

    if (!SUPPORTED_METHODS.has(method)) {
      sendJson(res, 405, {
        ok: false,
        status: 405,
        error: { code: 'method_not_allowed', message: `Unsupported method: ${method}` },
      })
      return
    }

    if (ALLOWED_PREFIXES.length && !ALLOWED_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
      sendJson(res, 404, {
        ok: false,
        status: 404,
        error: { code: 'path_not_allowed', message: `Unsupported bridge path: ${pathname}` },
      })
      return
    }

    const handler = registry.routes.get(`${method} ${pathname}`)
    if (!handler) {
      sendJson(res, 404, {
        ok: false,
        status: 404,
        error: { code: 'route_not_found', message: `Route not found: ${method} ${pathname}` },
      })
      return
    }

    try {
      const body = ['GET', 'HEAD'].includes(method) ? null : await readJsonBody(req)
      const outcome = await handler({
        method,
        path: pathname,
        headers: req.headers,
        query: buildQueryObject(requestUrl.searchParams),
        body,
        context: runtimeContext,
      })
      const normalized = normalizeHandlerResult(outcome)
      sendJson(
        res,
        normalized.status,
        {
          ok: normalized.status < 400,
          status: normalized.status,
          data: normalized.data,
        },
        normalized.headers,
      )
    } catch (error) {
      const status = Number.parseInt(String(error?.status || '500'), 10) || 500
      sendJson(res, status, {
        ok: false,
        status,
        error: {
          code: error?.code || 'node_bridge_error',
          message: error?.message || 'Node bridge request failed',
        },
      })
    }
  })

  server.listen(PORT, HOST)
}

await main()

/**
 * Standalone <Chat/> harness — the "external React, no iframe" story.
 *
 * Mounts the package's drop-in chat directly against a backend, with NO scene /
 * iframe / parent handshake. Connection is read from the URL query (so you can
 * point it at any runtime) with sensible local defaults. Login lives outside the
 * component: `auth.mode: 'cookie'` lets the browser session cookie authenticate
 * (use `mode: 'token'` + getAccessToken/getIdToken for a bearer flow instead).
 */
import { createRoot } from 'react-dom/client'
import { ChatStoreProvider, Chat } from '@kdcube/components-react/chat'
import type { EngineConfig } from '@kdcube/components-core'
import { installCapabilitiesMock } from './mockCapabilities.ts'
import './chat-ui.css'

const params = new URLSearchParams(window.location.search)
// `?mock=1` — exercise the composer "+" menu against canned agent_capabilities /
// agent_selection_update responses, no backend needed.
if (params.get('mock')) installCapabilitiesMock()
const config: EngineConfig = {
  connection: {
    baseUrl: params.get('baseUrl') || 'http://localhost:8000',
    tenant: params.get('tenant') || 'demo-tenant',
    project: params.get('project') || 'demo-project',
    bundleId: params.get('bundle') || 'versatile@2026-03-31-13-36',
  },
  agentId: params.get('agent') || undefined,
  auth: { mode: 'cookie' },
}

createRoot(document.getElementById('root')!).render(
  <ChatStoreProvider config={config}>
    <Chat brandLabel="Chat" />
  </ChatStoreProvider>,
)

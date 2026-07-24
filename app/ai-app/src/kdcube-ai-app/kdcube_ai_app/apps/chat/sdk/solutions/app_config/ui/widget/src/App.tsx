/**
 * The app-configuration admin surface, ONE place: the structured App Config
 * panel (as_provider/as_consumer/config with the YAML-or-JSON merge editor)
 * plus the agentic views — the instruction constructor, the per-app Agents
 * editor, and App settings (config patches + secrets) — hosted as tabs over
 * the shared packages. Runtime config + auth resolve via the standard
 * handshake (`settings`); on a host `kdcube-auth-changed` broadcast it
 * re-probes config and remounts so every view reloads with fresh auth.
 */
import { useEffect, useState } from 'react'
import { AppsConfigProvider, AppConfigPanel } from '@kdcube/components-react/apps-config'
import type { AppScope, AppsConfigTransport } from '@kdcube/components-core/apps-config'
import {
  AgenticConfigProvider,
  AgenticConfigTabs,
  type AgenticConfigTransport,
} from '@kdcube/components-react/agentic-config'
import { settings } from './settings.ts'

const transport: AppsConfigTransport = {
  baseUrl: () => settings.getBaseUrl(),
  authHeaders: (extra) => settings.authHeaders(extra),
}

const agenticTransport: AgenticConfigTransport = {
  baseUrl: () => settings.getBaseUrl(),
  authHeaders: (extra) => settings.authHeaders(extra),
  tenant: () => settings.getTenant(),
  project: () => settings.getProject(),
  opsBundle: () => 'kdcube-services@1-0',
}

type Tab = 'apps' | 'agentic'

export default function App() {
  const [ready, setReady] = useState(false)
  const [authNonce, setAuthNonce] = useState(0)
  const [tab, setTab] = useState<Tab>('apps')

  useEffect(() => {
    let alive = true
    void settings.setupParentListener().then(() => {
      if (alive) setReady(true)
    })

    const onAuthChanged = () => {
      void settings.requestConfig().then(() => {
        if (alive) setAuthNonce((n) => n + 1)
      })
    }
    window.addEventListener('kdcube-auth-changed', onAuthChanged as EventListener)
    return () => {
      alive = false
      window.removeEventListener('kdcube-auth-changed', onAuthChanged as EventListener)
    }
  }, [])

  if (!ready) {
    return <div className="ac-boot">Loading…</div>
  }

  const scope: AppScope = { tenant: settings.getTenant(), project: settings.getProject() }

  return (
    <div className="acw-shell" key={authNonce}>
      <nav className="acw-tabs">
        <button className={tab === 'apps' ? 'is-active' : ''} onClick={() => setTab('apps')}>
          App Config
        </button>
        <button className={tab === 'agentic' ? 'is-active' : ''} onClick={() => setTab('agentic')}>
          Agents & Instructions
        </button>
      </nav>
      {tab === 'apps' ? (
        <AppsConfigProvider scope={scope} transport={transport}>
          <AppConfigPanel title="App Config" />
        </AppsConfigProvider>
      ) : (
        <AgenticConfigProvider transport={agenticTransport}>
          <AgenticConfigTabs />
        </AgenticConfigProvider>
      )}
    </div>
  )
}

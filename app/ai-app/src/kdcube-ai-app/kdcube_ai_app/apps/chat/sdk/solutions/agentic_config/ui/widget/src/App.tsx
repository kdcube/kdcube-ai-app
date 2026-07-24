/**
 * The agentic-config admin widget — a thin shell over
 * `@kdcube/components-react/agentic-config` (the instruction constructor,
 * the per-app Agents editor, App settings). Runtime config + auth resolve
 * via the standard handshake (`settings`); a host `kdcube-auth-changed`
 * broadcast re-probes config and remounts the views with fresh auth.
 */
import { useEffect, useState } from 'react'
import {
  AgenticConfigProvider,
  AgenticConfigTabs,
  type AgenticConfigTransport,
} from '@kdcube/components-react/agentic-config'
import { settings } from './settings.ts'

const transport: AgenticConfigTransport = {
  baseUrl: () => settings.getBaseUrl(),
  authHeaders: (extra) => settings.authHeaders(extra),
  tenant: () => settings.getTenant(),
  project: () => settings.getProject(),
  opsBundle: () => settings.getOpsBundle(),
}

export default function App() {
  const [ready, setReady] = useState(false)
  const [authNonce, setAuthNonce] = useState(0)

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

  if (!ready) return <div className="agc-boot">Loading…</div>
  return (
    <AgenticConfigProvider key={authNonce} transport={transport}>
      <AgenticConfigTabs />
    </AgenticConfigProvider>
  )
}

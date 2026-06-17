/**
 * Package-UI engine root (opt-in via `VITE_CHAT_UI=package`). Drives chat through
 * the framework-agnostic `@kdcube/components-react/chat` engine AND renders that
 * package's default `<Chat/>` UI — instead of the in-tree `App.tsx`.
 *
 * It reuses `PackageChatRoot` (from `packageEngine.tsx`) verbatim: that already
 * resolves the parent-handshake config, creates the package engine, and installs
 * the iframe host-bridge (engine events ⇄ scene postMessage). We simply pass the
 * package `<Chat/>` as its children, so the host-bridge keeps working while the
 * UI comes from the package. Host-specific chrome (brand, account, embed, preview)
 * is read from the widget's settings/host and forwarded as `<Chat>` props, so the
 * package UI matches the in-tree widget's appearance.
 *
 * Selected by `vite.config.ts`'s `@chat/engine-root` alias; `EngineRoot({children})`
 * shape matches `localEngineRoot.tsx` / `packageEngine.tsx`. The in-tree `App.tsx`
 * passed as children is ignored in this mode.
 */
import type { ReactNode } from 'react'
import { Chat } from '@kdcube/components-react/chat'
import type { NamespaceStyleMap } from '@kdcube/components-core/chat'
import { PackageChatRoot } from './packageEngine.tsx'
import { CHAT_BRAND_LABEL, settings } from '../settings.ts'
import { isHostEmbedMode, isKdcubePreviewContext } from '../host.ts'

/** Renders inside PackageChatRoot (after config resolves), so `settings` is
 *  populated when we read tenant/project + namespace styles. `setupParentListener`
 *  awaits `loadNamespaceStyles` before resolving, so the styles are present here on
 *  first render — the in-tree path reads the same singleton, just live per render. */
function PackageChatUI() {
  return (
    <Chat
      brandLabel={CHAT_BRAND_LABEL}
      accountLabel={`${settings.getTenant() || 'tenant'} / ${settings.getProject() || 'project'}`}
      embedded={isHostEmbedMode()}
      kdcubePreview={isKdcubePreviewContext()}
      // Namespace-owned colors for context chips — without this the package chat
      // renders chips uncolored (the in-tree components read this singleton directly).
      namespaceStyles={settings.getNamespaceStyles() as NamespaceStyleMap}
    />
  )
}

export function EngineRoot(_props: { children?: ReactNode }) {
  return (
    <PackageChatRoot>
      <PackageChatUI />
    </PackageChatRoot>
  )
}

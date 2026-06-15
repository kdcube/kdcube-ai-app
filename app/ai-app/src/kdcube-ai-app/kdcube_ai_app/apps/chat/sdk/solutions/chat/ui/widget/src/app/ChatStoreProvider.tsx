/**
 * ChatStoreProvider — the public entry point for embedding the reusable chat
 * engine with your own UI:
 *
 *   <ChatStoreProvider config={...}>
 *     <MyOwnChatUI />        // calls useChatEngine() inside
 *   </ChatStoreProvider>
 *
 * Responsibilities:
 *  - provide the Redux store (the chat state machine + transport already live
 *    in the slice/reducers/api — see app/store.ts), and
 *  - apply any caller-supplied connection config to `settings` BEFORE the
 *    engine boots, so a custom/external host can pass baseUrl/tenant/project/
 *    bundle/tokens directly instead of relying on the iframe parent handshake.
 *
 * When `config` is omitted the engine keeps today's behavior: it resolves
 * baseUrl/tenant/project/bundle/auth from query params, the served route, and
 * the parent-frame CONFIG handshake (settings.setupParentListener()).
 *
 * Note: the store is a module singleton today (app/store.ts), so two providers
 * on one page share one chat state — correct for the single-widget embed. Making
 * it multi-instance safe (a store per provider) is a deliberate follow-up.
 */
import type { ReactNode } from 'react'
import { useState } from 'react'
import { Provider } from 'react-redux'
import { store } from './store.ts'
import { ChatEngineHost } from './useChatEngine.tsx'
import type { AppSettings } from '../settings.ts'
import { settings } from '../settings.ts'

export type ChatEngineConfig = Partial<AppSettings>

export function ChatStoreProvider({
  config,
  children,
}: {
  config?: ChatEngineConfig
  children: ReactNode
}) {
  /* Apply caller config exactly once, synchronously, before children (and the
   * engine boot inside useChatEngine) first render. A useState initializer runs
   * during render, ahead of child effects. */
  useState(() => {
    if (config && Object.keys(config).length > 0) settings.update(config)
    return true
  })

  return (
    <Provider store={store}>
      <ChatEngineHost>{children}</ChatEngineHost>
    </Provider>
  )
}

/**
 * `<Chat/>` — the default, drop-in chat UI. Mount inside `<ChatStoreProvider>`:
 *
 *   <ChatStoreProvider config={...}><Chat /></ChatStoreProvider>
 *
 * U1 scaffold: provides the `ChatViewModel` and renders a minimal shell (status +
 * composer) that exercises the engine seam end-to-end. The full presentational
 * layer (turns, conversations, context chips, banners, …) is ported in U2; until
 * then this is a functional placeholder, not feature-parity with the SDK widget.
 */
import { useState } from 'react'
import { ChatViewModelProvider, useChatViewModel, type ChatViewModelProviderProps } from './context.tsx'

export interface ChatProps {
  /** Marks a same-origin dev-preview frame; forwarded to the view-model. */
  kdcubePreview?: ChatViewModelProviderProps['kdcubePreview']
}

export function Chat({ kdcubePreview }: ChatProps = {}) {
  return (
    <ChatViewModelProvider kdcubePreview={kdcubePreview}>
      <ChatShell />
    </ChatViewModelProvider>
  )
}

function ChatShell() {
  const vm = useChatViewModel()
  const [draft, setDraft] = useState('')

  const submit = () => {
    const text = draft.trim()
    if (!text) return
    vm.send(text)
    setDraft('')
  }

  return (
    <div className="kdc-chat" data-bundle={vm.bundleId} data-view={vm.hostView}>
      <header className="kdc-chat__status">
        <span>{vm.ready ? 'ready' : 'connecting…'}</span>
        {vm.bootError ? <span className="kdc-chat__error">{vm.bootError}</span> : null}
      </header>
      <div className="kdc-chat__composer">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder="Message…"
          rows={2}
        />
        <button type="button" onClick={submit} disabled={!draft.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}

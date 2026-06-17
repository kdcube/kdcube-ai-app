/**
 * `<Chat/>` — the default, drop-in chat UI. Mount inside `<ChatStoreProvider>`:
 *
 *   <ChatStoreProvider config={...}><Chat /></ChatStoreProvider>
 *
 * It provides the `ChatViewModel` (derived from the engine) and renders the full
 * reference chat shell (transcript, conversations, composer, banners, …). Host
 * specifics are optional props: `brandLabel`, `accountLabel`, `embedded`, and an
 * optional left-pane `webapp` widget — all off/auto by default so a bare `<Chat/>`
 * works standalone.
 */
import { ChatViewModelProvider, type ChatViewModelProviderProps } from './context.tsx'
import { ChatShell, type ChatShellProps } from './ChatShell.tsx'

export interface ChatProps extends ChatShellProps {
  /** Marks a same-origin dev-preview frame; forwarded to the view-model. */
  kdcubePreview?: ChatViewModelProviderProps['kdcubePreview']
}

export function Chat({ kdcubePreview, ...shellProps }: ChatProps = {}) {
  return (
    <ChatViewModelProvider kdcubePreview={kdcubePreview}>
      <ChatShell {...shellProps} />
    </ChatViewModelProvider>
  )
}

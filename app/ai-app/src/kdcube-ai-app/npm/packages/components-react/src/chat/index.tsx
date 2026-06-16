/**
 * @kdcube/components-react/chat — public surface.
 *
 * Two layers:
 *   - **binding** (`./binding.tsx`) — `<ChatStoreProvider>` + `useChatEngine` /
 *     `useChatState` / `useChatStatus`: the engine made consumable by React. Use
 *     these to build your own UI.
 *   - **ui** (`./ui`) — a default `<Chat/>` component (the reference chat UI) that
 *     renders against a `ChatViewModel` derived from the engine. Use this for a
 *     drop-in chat:
 *
 *       <ChatStoreProvider config={{ connection: { baseUrl, tenant, project, bundleId } }}>
 *         <Chat />
 *       </ChatStoreProvider>
 *
 * `<Chat/>` is being built out as a side solution (see U1–U4); it is not yet at
 * feature parity with the in-tree SDK widget UI.
 */
export * from './binding.tsx'
export { Chat } from './ui/index.ts'
export { useChatViewModel } from './ui/context.tsx'
export type { ChatViewModel } from './ui/viewModel.ts'

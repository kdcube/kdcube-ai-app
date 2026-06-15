/**
 * Public surface for embedding the reusable chat engine with a custom UI:
 *
 *   import { ChatStoreProvider, useChatEngine } from '.../ui/widget/src/app'
 *
 *   <ChatStoreProvider config={...}>
 *     <MyOwnChatUI />        // calls useChatEngine()
 *   </ChatStoreProvider>
 */
export { ChatStoreProvider } from './ChatStoreProvider.tsx'
export type { ChatEngineConfig } from './ChatStoreProvider.tsx'
export { useChatEngine } from './useChatEngine.tsx'
export type { ChatEngine, HostView } from './useChatEngine.tsx'

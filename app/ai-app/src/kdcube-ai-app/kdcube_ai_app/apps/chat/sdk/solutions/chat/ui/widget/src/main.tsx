import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ChatStoreProvider } from './app/ChatStoreProvider.tsx'

// Build-time stamp (set in vite.config). Tells you, in the running widget, exactly
// which chat implementation was built: in-tree / package-engine / package-ui.
declare const __KDCUBE_CHAT_IMPL__: string
const chatImpl = typeof __KDCUBE_CHAT_IMPL__ !== 'undefined' ? __KDCUBE_CHAT_IMPL__ : 'in-tree'
document.documentElement.setAttribute('data-kdcube-chat-impl', chatImpl)
console.info(`[kdcube.chat] UI implementation = ${chatImpl}`)

createRoot(document.getElementById('root')!).render(
  <ChatStoreProvider>
    <App />
  </ChatStoreProvider>,
)

import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ChatStoreProvider } from './app/ChatStoreProvider.tsx'

createRoot(document.getElementById('root')!).render(
  <ChatStoreProvider>
    <App />
  </ChatStoreProvider>,
)

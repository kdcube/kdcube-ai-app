import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import '@kdcube/components-react/agentic-config/styles/agentic-config.css'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'

// Resolve the workspace packages from SOURCE so the harness runs live without a
// build or publish step. (External consumers instead `npm install` the packages
// and import them normally; no alias needed.)
const PKGS = resolve(__dirname, '../../..') // -> npm/packages

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: [
      { find: '@kdcube/components-react/chat', replacement: resolve(PKGS, 'components-react/src/chat/index.tsx') },
      { find: '@kdcube/components-react', replacement: resolve(PKGS, 'components-react/src/index.ts') },
      { find: '@kdcube/components-core/chat', replacement: resolve(PKGS, 'components-core/src/chat/index.ts') },
      { find: '@kdcube/components-core/canvas', replacement: resolve(PKGS, 'components-core/src/canvas/index.ts') },
      { find: '@kdcube/components-core', replacement: resolve(PKGS, 'components-core/src/index.ts') },
    ],
    dedupe: ['react', 'react-dom', 'react-redux', '@reduxjs/toolkit'],
  },
})

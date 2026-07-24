import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/** The agent-instructions authoring widget, built as a served widget. */
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: process.env.OUTDIR || 'dist',
    emptyOutDir: true,
  },
})

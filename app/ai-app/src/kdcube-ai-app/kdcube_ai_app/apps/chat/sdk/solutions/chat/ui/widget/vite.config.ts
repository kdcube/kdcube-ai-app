import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Chat engine selection is a single build-time knob: `VITE_CHAT_ENGINE`.
 *
 *   - unset / anything else  → in-tree engine (`src/app/localEngineRoot.tsx`)
 *   - `package`              → framework-agnostic `@kdcube/components-*` engine
 *                             (`src/app/packageEngine.tsx`)
 *
 * `ChatStoreProvider` imports `@chat/engine-root`; we resolve that alias to one of
 * the two roots here. Crucially, the package root (and therefore the `@kdcube/*`
 * imports) only enters the module graph in package mode — so the default build can
 * never fail on an unresolved package, even for a bundle that declares no
 * `shared_sources`. Switching engines requires no code changes, only the env var.
 *
 * In package mode the `@kdcube/*` packages resolve to the package `src` trees that
 * the bundle build materializes next to this config under `_shared/` (via the
 * widget's `shared_sources` + the `npm://` resolver). A plain-checkout fallback
 * walks up to the workspace `npm/packages` so `npm run build` works without the
 * bundle pipeline.
 */
const USE_PACKAGE_ENGINE =
  (process.env.VITE_CHAT_ENGINE || '').toLowerCase() === 'package'
// `VITE_CHAT_UI=package` goes one step further than the engine flag: it renders the
// package's own `<Chat/>` UI (via `src/app/packageUIRoot.tsx`) instead of the in-tree
// `App.tsx`. It implies the package engine. Either flag pulls the `@kdcube/*` packages
// into the graph (and needs the materialized `_shared/` sources).
const USE_PACKAGE_UI =
  (process.env.VITE_CHAT_UI || '').toLowerCase() === 'package'
const USE_PACKAGE = USE_PACKAGE_ENGINE || USE_PACKAGE_UI

function findWorkspacePackages(start: string): string | null {
  let dir = start
  for (let i = 0; i < 12; i++) {
    const candidate = resolve(dir, 'npm', 'packages')
    if (existsSync(candidate)) return candidate
    const parent = resolve(dir, '..')
    if (parent === dir) break
    dir = parent
  }
  return null
}

function pkgSrc(materializedName: string, packageName: string): string {
  const shared = resolve(__dirname, '_shared', materializedName)
  if (existsSync(shared)) return shared
  const workspace = findWorkspacePackages(__dirname)
  if (workspace) return resolve(workspace, packageName, 'src')
  // Last resort: the materialized path (vite reports a clear missing-alias error).
  return shared
}

const engineRoot = resolve(
  __dirname,
  'src/app',
  USE_PACKAGE_UI ? 'packageUIRoot.tsx' : USE_PACKAGE_ENGINE ? 'packageEngine.tsx' : 'localEngineRoot.tsx',
)

const kdcubeAliases = USE_PACKAGE
  ? (() => {
      const CORE = pkgSrc('components_core', 'components-core')
      const REACT = pkgSrc('components_react', 'components-react')
      return [
        { find: '@kdcube/components-react/chat', replacement: resolve(REACT, 'chat') },
        { find: '@kdcube/components-react', replacement: REACT },
        { find: '@kdcube/components-core/chat', replacement: resolve(CORE, 'chat') },
        { find: '@kdcube/components-core', replacement: CORE },
      ]
    })()
  : []

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',
  resolve: {
    alias: [
      { find: '@chat/engine-root', replacement: engineRoot },
      ...kdcubeAliases,
    ],
    // The materialized package source imports react / redux as bare specifiers;
    // dedupe so they bind to the widget's single copy, not a nested one.
    dedupe: ['react', 'react-dom', 'react-redux', '@reduxjs/toolkit'],
  },
  build: {
    outDir: process.env.OUTDIR || 'dist',
    emptyOutDir: true,
  },
  // Build-time stamp so you can SEE which chat implementation actually built:
  // `in-tree` (App.tsx + local engine), `package-engine` (npm engine, in-tree UI),
  // or `package-ui` (npm engine + npm <Chat/>). Surfaced on <html data-kdcube-chat-impl>
  // and in the console by main.tsx.
  define: {
    __KDCUBE_CHAT_IMPL__: JSON.stringify(
      USE_PACKAGE_UI ? 'package-ui' : USE_PACKAGE_ENGINE ? 'package-engine' : 'in-tree',
    ),
  },
})

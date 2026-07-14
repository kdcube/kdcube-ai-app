import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)

function findInWorkspace(start, rel) {
  let dir = start
  for (let i = 0; i < 16; i++) {
    const candidate = path.resolve(dir, rel)
    if (fs.existsSync(candidate)) return candidate
    const parent = path.resolve(dir, '..')
    if (parent === dir) break
    dir = parent
  }
  return ''
}

// Scene-host shell (@kdcube/components-react/scene — rail, window manager,
// component registry, host plumbing, sceneHost.css). The bundle build materializes
// it next to this config under _shared/; a plain-checkout fallback walks up to the
// workspace npm/packages. (Files sit at the package root — no src/ subdir.) The
// stylesheet resolves next to the entry.
const materializedComponentsReactScene = path.resolve(__dirname, '_shared/components-react/scene/index.ts')
const sceneShellEntry = fs.existsSync(materializedComponentsReactScene)
  ? materializedComponentsReactScene
  : findInWorkspace(__dirname, 'npm/packages/components-react/src/scene/index.ts')
const sceneShellCss = path.resolve(path.dirname(sceneShellEntry), 'sceneHost.css')

// Scene runtime (@kdcube/components-core/scene) — the registry/host types the
// shell re-exports; it in turn imports @kdcube/components-core/events. Same
// materialized-_shared + workspace-fallback resolution.
const materializedComponentsCoreScene = path.resolve(__dirname, '_shared/components-core/scene/index.ts')
const sceneRuntimeEntry = fs.existsSync(materializedComponentsCoreScene)
  ? materializedComponentsCoreScene
  : findInWorkspace(__dirname, 'npm/packages/components-core/src/scene/index.ts')
const materializedComponentsCoreEvents = path.resolve(__dirname, '_shared/components-core/events/index.ts')
const eventsRuntimeEntry = fs.existsSync(materializedComponentsCoreEvents)
  ? materializedComponentsCoreEvents
  : findInWorkspace(__dirname, 'npm/packages/components-core/src/events/index.ts')

export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: {
    alias: [
      { find: '@kdcube/components-react/scene/sceneHost.css', replacement: sceneShellCss },
      { find: '@kdcube/components-react/scene', replacement: sceneShellEntry },
      { find: '@kdcube/components-core/scene', replacement: sceneRuntimeEntry },
      { find: '@kdcube/components-core/events', replacement: eventsRuntimeEntry },
      { find: /^react$/, replacement: require.resolve('react') },
      { find: /^react-dom$/, replacement: require.resolve('react-dom') },
      { find: /^react-dom\/client$/, replacement: require.resolve('react-dom/client') },
      { find: /^react\/jsx-runtime$/, replacement: require.resolve('react/jsx-runtime') },
    ],
  },
  build: {
    outDir: process.env.OUTDIR || 'dist',
    emptyOutDir: true,
  },
})

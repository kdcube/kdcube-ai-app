import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

function findWorkspacePackages(start: string): string | null {
  let dir = start;
  for (let i = 0; i < 12; i += 1) {
    const candidate = resolve(dir, 'npm', 'packages');
    if (existsSync(candidate)) return candidate;
    const parent = resolve(dir, '..');
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

function componentsCoreSrc(): string {
  const shared = resolve(__dirname, '_shared', 'components-core');
  if (existsSync(shared)) return shared;
  const workspace = findWorkspacePackages(__dirname);
  if (workspace) return resolve(workspace, 'components-core', 'src');
  return shared;
}

const CORE = componentsCoreSrc();

export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: {
    alias: [
      { find: '@kdcube/components-core/events', replacement: resolve(CORE, 'events') },
      { find: '@kdcube/components-core/scene', replacement: resolve(CORE, 'scene') },
      { find: '@kdcube/components-core', replacement: CORE },
    ],
  },
  build: {
    outDir: process.env.OUTDIR || process.env.VITE_BUILD_DEST_ABSOLUTE_PATH || 'dist',
    emptyOutDir: true,
  },
});

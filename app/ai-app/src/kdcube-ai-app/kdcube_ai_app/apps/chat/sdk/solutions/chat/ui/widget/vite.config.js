"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var vite_1 = require("vite");
var plugin_react_1 = require("@vitejs/plugin-react");
var vite_2 = require("@tailwindcss/vite");
var node_fs_1 = require("node:fs");
var node_path_1 = require("node:path");
/**
 * The chat widget builds the npm `@kdcube/components-*` chat (package `<Chat/>` +
 * the framework-agnostic engine + iframe host-bridge). There is no in-tree engine
 * or UI anymore.
 *
 * The `@kdcube/*` packages resolve to the package `src` trees that the bundle build
 * materializes next to this config under `_shared/` (via the widget's `npm://`
 * `shared_sources`). A plain-checkout fallback walks up to the workspace
 * `npm/packages` so `npm run build` works without the bundle pipeline.
 */
function findWorkspacePackages(start) {
    var dir = start;
    for (var i = 0; i < 12; i++) {
        var candidate = (0, node_path_1.resolve)(dir, 'npm', 'packages');
        if ((0, node_fs_1.existsSync)(candidate))
            return candidate;
        var parent_1 = (0, node_path_1.resolve)(dir, '..');
        if (parent_1 === dir)
            break;
        dir = parent_1;
    }
    return null;
}
function pkgSrc(materializedName, packageName) {
    var shared = (0, node_path_1.resolve)(__dirname, '_shared', materializedName);
    if ((0, node_fs_1.existsSync)(shared))
        return shared;
    var workspace = findWorkspacePackages(__dirname);
    if (workspace)
        return (0, node_path_1.resolve)(workspace, packageName, 'src');
    // Last resort: the materialized path (vite reports a clear missing-alias error).
    return shared;
}
var CORE = pkgSrc('components_core', 'components-core');
var REACT = pkgSrc('components_react', 'components-react');
exports.default = (0, vite_1.defineConfig)({
    plugins: [(0, plugin_react_1.default)(), (0, vite_2.default)()],
    base: './',
    resolve: {
        alias: [
            { find: '@kdcube/components-react/chat', replacement: (0, node_path_1.resolve)(REACT, 'chat') },
            { find: '@kdcube/components-react', replacement: REACT },
            { find: '@kdcube/components-core/chat', replacement: (0, node_path_1.resolve)(CORE, 'chat') },
            { find: '@kdcube/components-core', replacement: CORE },
        ],
        // The materialized package source imports react / redux as bare specifiers;
        // dedupe so they bind to the widget's single copy, not a nested one.
        dedupe: ['react', 'react-dom', 'react-redux', '@reduxjs/toolkit'],
    },
    build: {
        outDir: process.env.OUTDIR || 'dist',
        emptyOutDir: true,
    },
    // Build-impl marker, surfaced on <html data-kdcube-chat-impl> + console by main.tsx.
    define: {
        __KDCUBE_CHAT_IMPL__: JSON.stringify('package-ui'),
    },
});

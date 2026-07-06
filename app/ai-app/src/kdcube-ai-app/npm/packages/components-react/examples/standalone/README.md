# Standalone `<Chat/>` harness

The "external React, no iframe" story made runnable: it mounts
`@kdcube/components-react/chat`'s drop-in `<Chat/>` directly against a backend,
with no scene / iframe / parent handshake.

```sh
cd app/ai-app/src/kdcube-ai-app/npm/packages/components-react/examples/standalone
npm install
npm run dev
# open the printed URL, optionally with connection query params:
#   ?baseUrl=http://localhost:8000&tenant=demo-tenant&project=demo-project&bundle=workspace@2026-03-31-13-36
```

- **Engine vs UI**: `<ChatStoreProvider config>` creates the headless engine
  (`@kdcube/components-core/chat`); `<Chat/>` is the default UI. To build your own
  UI instead, drop `<Chat/>` and use `useChatEngine()` / `useChatState()` /
  `useChatStatus()` from the same package.
- **Auth** lives outside the component. This harness uses `auth.mode: 'cookie'`
  (browser session). For a bearer flow use `mode: 'token'` with
  `getAccessToken` / `getIdToken`.
- **Styling**: `chat-ui.css` is the chat stylesheet (Tailwind import + the `k-*`
  classes); `@tailwindcss/vite` generates the utilities by scanning the package
  source. External apps either reuse this CSS + their own Tailwind, or (future) a
  prebuilt stylesheet shipped with the package.
- **Packages resolve from source** via the `vite.config.ts` aliases — no build or
  publish needed for local dev.
- **Composer "+" menu mock mode**: add `?mock=1` to run the per-user tools &
  skills menu against canned `agent_capabilities` / `agent_selection_update`
  responses — no backend needed. The mock keeps the deny-list in memory with the
  real merge semantics (`applySelectionPatch`), so toggles persist across menu
  reopens and every debounced save is logged to the console. `?agent=<id>`
  selects the engine's `agentId` (default `main`).

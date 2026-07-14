/**
 * Ported-agents scene content: what THIS app composes.
 *
 * The reusable scene-host mechanics (component registry model, route/runtime
 * context, widget URLs, the CONFIG handshake) come from
 * `@kdcube/components-react/scene`; this module keeps only the app-specific
 * pieces — its two dedicated chat components (one per hosted agent) and the
 * neutral host-embed params — and re-exports the package plumbing under the
 * names the scene host uses.
 *
 * Each chat tile is its OWN dedicated widget alias (`chat_lg_solution`,
 * `chat_lg_react`), each built from the SDK chat widget source with a per-alias
 * `VITE_CHAT_AGENT_ID` / `VITE_CHAT_BRAND_LABEL` bake (see the bundle's
 * `ui.widgets` config). So the agent is bound by the widget's OWN config, not by
 * an `?agent_id=` URL query the scene appends: the tile is a first-class,
 * agent-bound widget the scene simply mounts by alias.
 */

import {
  asRecord,
  asString,
  componentWidgetUrl,
  requestSceneRuntimeConfig,
  sceneContextFromConfig,
  sceneRouteContext,
  widgetUrlForBundle,
  type SceneComponentSpec,
  type SceneRouteContext,
  type SceneRuntimeConfigPayload,
} from '@kdcube/components-react/scene'

export const BUNDLE_ID = 'ported-langgraph-agents@2026-07-13'
export const CONFIG_IDENTITY = 'BUNDLE_LG_SCENE_MAIN_VIEW'

// The scene host's vocabulary stays stable; the shapes are the package's.
export type RouteContext = SceneRouteContext
export type RuntimeConfig = SceneRuntimeConfigPayload
export {
  asRecord,
  asString,
  componentWidgetUrl,
  widgetUrlForBundle,
  type SceneComponentSpec,
}

export function routeContext(): RouteContext {
  return sceneRouteContext(BUNDLE_ID, { tenant: 'demo-tenant', project: 'demo-project' })
}

export function contextFromConfig(config: RuntimeConfig | null, fallback: RouteContext): RouteContext {
  return sceneContextFromConfig(config, fallback)
}

export function requestRuntimeConfig(): Promise<RuntimeConfig | null> {
  return requestSceneRuntimeConfig(CONFIG_IDENTITY)
}

/**
 * Neutral host-embed params for a chat tile. Identity — brand label, config
 * identity, event prefix, and the bound agent — is baked into each dedicated
 * widget's build (VITE env), NOT appended here, so the URL carries only what the
 * host-embed contract needs.
 */
export function chatWidgetParams(ctx: RouteContext): Record<string, string> {
  return {
    chat_embed_mode: 'host',
    bundle_id: ctx.bundleId,
  }
}

/**
 * The two docked chat tiles — one dedicated widget per hosted agent. Both mount
 * the app's SDK chat widget (different alias => different agent-bound build); the
 * scene mounts each by its own alias, side by side, as one integral surface.
 */
export function defaultComponentSpecs(): SceneComponentSpec[] {
  return [
    {
      alias: 'chat_lg_solution',
      bundleId: '',
      widgetAlias: 'chat_lg_solution',
      title: 'lg-solution',
      accent: 'teal',
      gated: false,
      views: true,
      size: { w: 460, h: 680 },
      targetSurfaces: [],
      placement: 'docked',
      rail: true,
      defaultOpen: false,
      enabled: true,
      order: 10,
    },
    {
      alias: 'chat_lg_react',
      bundleId: '',
      widgetAlias: 'chat_lg_react',
      title: 'lg-react',
      accent: 'gold',
      gated: false,
      views: true,
      size: { w: 460, h: 680 },
      targetSurfaces: [],
      placement: 'docked',
      rail: true,
      defaultOpen: false,
      enabled: true,
      order: 20,
    },
  ]
}

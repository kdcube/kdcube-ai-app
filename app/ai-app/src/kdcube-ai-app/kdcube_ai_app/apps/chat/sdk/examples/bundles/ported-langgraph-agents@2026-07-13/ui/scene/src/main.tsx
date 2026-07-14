/**
 * Ported-agents scene — a focused, config-driven scene host that mounts the
 * app's TWO agents side by side as two dedicated chat components.
 *
 * Each tile is an iframe-mounted served chat widget of this app — `chat_lg_solution`
 * (agent `lg-solution`) and `chat_lg_react` (agent `lg-react`). The agent + brand
 * label are baked into each dedicated widget's build (VITE env), so the scene just
 * mounts each by alias; it does NOT append an `?agent_id=` query. The two tiles
 * dock side by side on the stage as one integral surface; each supports
 * pin/unpin (promote/dock), relocate (drag), and resize via `FloatingWindow` +
 * `useWindowManager`, and a right-edge rail re-summons a floated/closed tile.
 *
 * The scene only composes: the summon rail, floating windows, the docked stage,
 * the visible-viewport clip probe, focus-raise, and the
 * CONFIG_REQUEST/CONFIG_RESPONSE handshake that feeds each frame its runtime
 * config. (No pinboard / memories / usage / drag brokering / event relay — those
 * are workspace-scene concerns this app does not need.)
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  FloatingWindow,
  Rail,
  buriedAliases,
  setViewportBottomClip,
  useWindowManager,
  windowRectFromState,
  type RailEntry,
  type WindowSizing,
} from '@kdcube/components-react/scene'
import {
  asRecord,
  asString,
  chatWidgetParams,
  componentWidgetUrl,
  contextFromConfig,
  defaultComponentSpecs,
  requestRuntimeConfig,
  routeContext,
  type RouteContext,
  type SceneComponentSpec,
} from './sceneConfig'
import { componentIcon } from './icons'
import './styles.css'

function windowSizing(spec: SceneComponentSpec): WindowSizing {
  return { size: { w: spec.size.w, h: spec.size.h }, full: spec.full }
}

function hintFor(bundleId: string, widgetAlias: string, sceneBundle: string): string {
  return `app ${bundleId || sceneBundle} · ${widgetAlias} component`
}

function App() {
  const fallback = useMemo(() => routeContext(), [])
  const [ctx, setCtx] = useState<RouteContext>(fallback)
  const [ready, setReady] = useState(false)
  const manager = useWindowManager()
  const managerRef = useRef(manager)
  managerRef.current = manager
  const frameRefs = useRef<Record<string, HTMLIFrameElement | null>>({})
  /** Window/tile section elements — used to promote a docked tile in place. */
  const tileRefs = useRef<Record<string, HTMLElement | null>>({})
  const ctxRef = useRef(ctx)
  ctxRef.current = ctx

  const components = useMemo(() => defaultComponentSpecs(), [])
  const specByAlias = useMemo(() => new Map(components.map((spec) => [spec.alias, spec])), [components])

  const postToFrame = useCallback((alias: string, message: Record<string, unknown>): boolean => {
    const target = frameRefs.current[alias]?.contentWindow
    if (!target) return false
    target.postMessage(message, '*')
    return true
  }, [])

  const aliasForSource = useCallback((source: MessageEventSource | null): string => {
    for (const [alias, frame] of Object.entries(frameRefs.current)) {
      if (frame && frame.contentWindow === source) return alias
    }
    return ''
  }, [])

  /** A chat widget's compact/expanded view command (kdcube-set-view). */
  const syncWidgetView = useCallback((alias: string, view: 'compact' | 'expanded') => {
    const spec = specByAlias.get(alias)
    postToFrame(alias, { type: 'kdcube-set-view', widget: spec?.widgetAlias || alias, view })
  }, [postToFrame, specByAlias])

  /** Promote a docked tile into a floating window from its own rect (pin). */
  const promoteComponent = useCallback((alias: string) => {
    const tile = tileRefs.current[alias]
    const rect = tile?.getBoundingClientRect()
    managerRef.current.promote(alias, rect ? { x: rect.left, y: rect.top, w: rect.width, h: rect.height } : undefined)
  }, [])

  /** Send a floating tile home to its docked slot (unpin). */
  const dockComponent = useCallback((alias: string) => {
    managerRef.current.dock(alias)
    window.setTimeout(() => syncWidgetView(alias, 'compact'), 0)
  }, [syncWidgetView])

  const openComponent = useCallback((alias: string, options: { expanded?: boolean } = {}) => {
    const mgr = managerRef.current
    const spec = specByAlias.get(alias)
    if (!spec) return
    // Docked tiles are always present on the stage; an expand request promotes +
    // maximizes the tile, a collapse docks it home, a plain open raises it.
    mgr.ensureDocked(alias)
    if (options.expanded) {
      promoteComponent(alias)
      mgr.maximize(alias)
      window.setTimeout(() => syncWidgetView(alias, 'expanded'), 0)
    } else if (options.expanded === false) {
      dockComponent(alias)
    } else {
      mgr.front(alias)
    }
  }, [dockComponent, promoteComponent, specByAlias, syncWidgetView])

  // ---------------------------------------------------------------- boot
  useEffect(() => {
    requestRuntimeConfig()
      .then((config) => {
        setCtx(contextFromConfig(config, fallback))
        setReady(true)
      })
      .catch(() => setReady(true))
  }, [fallback])

  // Both tiles dock onto the stage as soon as the scene is ready.
  useEffect(() => {
    if (!ready) return
    components.forEach((spec) => {
      if (spec.placement === 'docked') managerRef.current.ensureDocked(spec.alias)
    })
  }, [components, ready])

  // ------------------------------------------- true visible viewport probe
  // When the scene runs as an iframe of an outer host, the host may size the frame
  // taller than the visible area. An IntersectionObserver on a full-height sentinel
  // measures how much of the scene is actually visible and feeds the clip into
  // layout (--kdc-clip-bottom for the docked stage, setViewportBottomClip for the
  // floating-window clamps).
  useEffect(() => {
    const sentinel = document.createElement('div')
    sentinel.setAttribute('data-kdc-viewport-sentinel', '')
    sentinel.style.cssText = 'position:fixed;left:0;top:0;bottom:0;width:1px;pointer-events:none;visibility:hidden;'
    document.body.appendChild(sentinel)
    let lastClip = -1
    const observer = new IntersectionObserver((entries) => {
      const entry = entries[entries.length - 1]
      if (!entry) return
      const total = entry.boundingClientRect.height
      const visible = entry.intersectionRect.height
      const clip = Math.max(0, Math.round(total - visible))
      if (clip === lastClip) return
      lastClip = clip
      document.documentElement.style.setProperty('--kdc-clip-bottom', `${clip}px`)
      setViewportBottomClip(clip)
      managerRef.current.reclampToViewport()
    }, { threshold: Array.from({ length: 21 }, (_, i) => i / 20) })
    observer.observe(sentinel)
    const onResize = () => managerRef.current.reclampToViewport()
    window.addEventListener('resize', onResize)
    return () => {
      observer.disconnect()
      sentinel.remove()
      window.removeEventListener('resize', onResize)
    }
  }, [])

  // ------------------------------------------------- raise on activation
  // Standard window-manager focus: activating a window anywhere — chrome OR content
  // — raises it. A transparent raise veil over each buried window (parent-owned, so
  // pointer-down always reaches the scene) raises then unmounts, letting the click
  // fall through to the iframe; a `focus` listener armed on each frame's
  // contentWindow raises when focus enters that frame.
  const armFrameFocusRaise = useCallback((alias: string) => {
    const frame = frameRefs.current[alias]
    try {
      const target = frame?.contentWindow
      if (!target) return
      target.addEventListener('focus', () => managerRef.current.front(alias))
    } catch {
      /* cross-origin focus arm unavailable; the raise veil still covers it */
    }
  }, [])

  const raiseVeilFor = useCallback((alias: string) => {
    return (
      <button
        type="button"
        className="kdc-raise-veil"
        aria-label="Bring window to front"
        onPointerDown={() => {
          managerRef.current.front(alias)
          try {
            frameRefs.current[alias]?.contentWindow?.focus()
          } catch {
            /* focus hand-off is best-effort */
          }
        }}
      />
    )
  }, [])

  // ------------------------------------------------------ message broker
  useEffect(() => {
    function respondConfig(sourceAlias: string, frame: HTMLIFrameElement, data: Record<string, unknown>): void {
      const identityValue = asString(asRecord(data.data).identity) || asString(data.identity)
      if (!identityValue) return
      const spec = specByAlias.get(sourceAlias)
      const active = ctxRef.current
      const config: Record<string, unknown> = {
        configSource: 'scene',
        hostedByScene: true,
        baseUrl: active.baseUrl,
        defaultTenant: active.tenant,
        defaultProject: active.project,
        defaultApp: spec?.bundleId || active.bundleId,
        scene: {
          embedded: true,
          configSource: 'host',
          surface_ref: `ported_lg.${sourceAlias}`,
          alias: sourceAlias,
        },
      }
      frame.contentWindow?.postMessage({ type: 'CONFIG_RESPONSE', identity: identityValue, config }, '*')
    }

    function onMessage(event: MessageEvent): void {
      const data = asRecord(event.data)
      const type = asString(data.type)
      if (!type) return

      const sourceAlias = aliasForSource(event.source)

      if (!sourceAlias) {
        // Responses relayed from the outer host (when the scene is embedded) fan
        // out to every child frame; each chat frame filters by its own identity.
        if (['CONFIG_RESPONSE', 'CONN_RESPONSE'].includes(type) && event.source !== window) {
          Object.values(frameRefs.current).forEach((frame) => {
            frame?.contentWindow?.postMessage(data, '*')
          })
        }
        return
      }

      const sourceFrame = frameRefs.current[sourceAlias] as HTMLIFrameElement

      if (type === 'CONFIG_REQUEST') {
        if (window.parent !== window) {
          // Embedded: the outer host owns runtime config; relay up and its
          // response back down (handled above).
          window.parent.postMessage(data, '*')
        } else {
          respondConfig(sourceAlias, sourceFrame, data)
        }
        return
      }

      // Auth changes and 401s bubble to an embedding host; standalone they are a
      // no-op (the chat re-auths on its own from the cookie).
      if (type === 'kdcube-auth-changed' || type === 'kdcube-auth-required') {
        if (window.parent !== window) window.parent.postMessage(data, '*')
        return
      }

      if (type === 'kdcube-resize') {
        if (window.parent !== window) window.parent.postMessage(data, '*')
        return
      }

      // A chat tile asking to expand/collapse: expand promotes + maximizes the
      // tile, collapse docks it home.
      if (type === 'kdcube-widget-view') {
        openComponent(sourceAlias, { expanded: data.view === 'expanded' })
        return
      }

      if (type === 'kdcube-widget-focus') {
        managerRef.current.front(sourceAlias)
        return
      }

      if (type === 'kdcube-set-view') {
        const spec = specByAlias.get(sourceAlias)
        if (spec) managerRef.current.setExpanded(sourceAlias, windowSizing(spec), data.view === 'expanded')
        return
      }
    }

    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [aliasForSource, openComponent, specByAlias])

  // ------------------------------------------------------------- render
  if (!ready) {
    return <div className="boot">Loading scene...</div>
  }

  const scope = `${ctx.tenant} / ${ctx.project}`

  // Highest z among open floating windows: a rail tap on a buried open window
  // raises it; only a tap on the topmost one docks it home.
  const topFloatingZ = Object.values(manager.wins)
    .filter((win) => win.open && win.floating)
    .reduce((top, win) => Math.max(top, win.z), 0)

  // A window is "buried" when another open window with a higher z overlaps its
  // rect — that window gets the raise veil (docked tiles included: all windows
  // share one z band, docked tiles simply start low).
  const buriedWindows = buriedAliases(manager.wins, (alias, state) => {
    if (state.floating) return windowRectFromState(state)
    const tile = tileRefs.current[alias]
    if (!tile) return null
    const r = tile.getBoundingClientRect()
    return { left: r.left, top: r.top, right: r.right, bottom: r.bottom }
  })
  const isBuried = (alias: string): boolean => buriedWindows.has(alias)

  const railEntries: RailEntry[] = components
    .filter((spec) => spec.rail)
    .map((spec) => {
      const state = manager.get(spec.alias)
      return {
        id: spec.alias,
        label: spec.title,
        title: spec.title,
        accent: spec.accent,
        icon: componentIcon(spec.alias),
        // A docked tile's rail button reflects (and toggles) its floating
        // promotion: pinned tiles show "open"; tapping pins/unpins or raises.
        open: Boolean(state?.floating),
        onToggle: () => {
          if (state?.floating) {
            if (state.z < topFloatingZ) managerRef.current.front(spec.alias)
            else dockComponent(spec.alias)
          } else {
            promoteComponent(spec.alias)
          }
        },
      }
    })

  const renderComponentWindow = (spec: SceneComponentSpec) => {
    const state = manager.get(spec.alias)
    if (!state?.everOpened) return null
    const buried = isBuried(spec.alias)
    const params = { ...chatWidgetParams(ctx), ...(spec.params ?? {}) }
    const src = componentWidgetUrl(ctx, { ...spec, params })
    return (
      <FloatingWindow
        key={spec.alias}
        id={spec.alias}
        title={spec.title}
        accent={spec.accent}
        icon={componentIcon(spec.alias)}
        hint={hintFor(spec.bundleId, spec.widgetAlias, ctx.bundleId)}
        state={state}
        hasViews={spec.views}
        manager={manager}
        sizing={windowSizing(spec)}
        dockable
        onUnpin={() => promoteComponent(spec.alias)}
        onDockBack={() => dockComponent(spec.alias)}
        sectionRef={(el) => { tileRefs.current[spec.alias] = el }}
        onViewChange={(view) => syncWidgetView(spec.alias, view)}
        dropOverlay={buried ? raiseVeilFor(spec.alias) : null}
      >
        <iframe
          ref={(el) => { frameRefs.current[spec.alias] = el }}
          className="kdc-frame"
          title={spec.title}
          src={src}
          allow="clipboard-write"
          onLoad={() => {
            armFrameFocusRaise(spec.alias)
            const win = managerRef.current.get(spec.alias)
            if (spec.views) syncWidgetView(spec.alias, win?.expanded ? 'expanded' : 'compact')
          }}
        />
      </FloatingWindow>
    )
  }

  const dockedSpecs = components.filter((spec) => spec.placement === 'docked')

  return (
    <main className="scene">
      <header className="scene-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <span className="eyebrow">KDCube</span>
            <span className="title">Ported Agents</span>
          </div>
        </div>
        <div className="status" title={scope}>
          <span className="dot" aria-hidden="true" />
          <span>{scope}</span>
        </div>
      </header>

      <Rail entries={railEntries} />

      {/* Docked tiles: the static stage layer, two equal side-by-side columns so
          the pair reads as one integral surface. Each slot keeps hosting its
          window element even while it floats (position:fixed escapes the slot), so
          the iframe is never reparented and keeps its chat state; the emptied slot
          shows a dashed placeholder. */}
      {dockedSpecs.length ? (
        <div
          className="scene-stage"
          style={{ gridTemplateColumns: dockedSpecs.map(() => 'minmax(0, 1fr)').join(' ') }}
        >
          {dockedSpecs.map((spec) => {
            const floated = Boolean(manager.get(spec.alias)?.floating)
            return (
              <div
                key={spec.alias}
                className={`kdc-dock-slot${floated ? ' floated' : ''}`}
                data-slot={spec.alias}
              >
                {renderComponentWindow(spec)}
              </div>
            )
          })}
        </div>
      ) : null}
    </main>
  )
}

const rootNode = document.getElementById('app')
if (!rootNode) {
  throw new Error('Missing #app root')
}

createRoot(rootNode).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

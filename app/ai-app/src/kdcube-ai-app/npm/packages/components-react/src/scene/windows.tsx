/**
 * Scene-host window layer — one generic window chrome (titlebar + drag +
 * corner resize + expand/collapse + close), the labeled accent rail, and the
 * window manager: a shared z-band for docked AND floating windows,
 * capture-phase raise on every window, same-element docked-tile promotion
 * (the iframe is never reparented, so widget state survives) with
 * visible-viewport clamps, re-clamp on host clip changes, and the
 * `setViewportBottomClip` feed from the visible-viewport probe. Windows hide
 * instead of unmounting so widgets keep their state across summons.
 * Content-free: the host supplies the component registry, icons, iframes,
 * and the raise-veil/drop overlays. Pair with the `sceneHost.css` stylesheet
 * shipped next to this module.
 */

import React, { useCallback, useRef, useState } from 'react'

export const WINDOW_BAR_HEIGHT = 36
const MIN_W = 300
const MIN_H = 210
const BASE_Z = 10010

/**
 * Bottom clip of the scene's own viewport, in px. When the scene runs as an
 * iframe of an outer host, the host may size the frame taller than the
 * visible area — the scene's `window.innerHeight` then extends below what
 * the user can see. The scene measures its true visibility
 * (IntersectionObserver sentinel in main.tsx) and every viewport-bottom
 * computation subtracts this clip.
 */
let viewportClipBottom = 0

export function setViewportBottomClip(clip: number): void {
  viewportClipBottom = Math.max(0, Math.round(clip) || 0)
}

function visibleBottom(): number {
  return Math.max(260, window.innerHeight - viewportClipBottom)
}

export interface SceneWindowRect {
  left: number
  top: number
  right: number
  bottom: number
}

export function rectsIntersect(a: SceneWindowRect, b: SceneWindowRect): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
}

/** Rect of a FLOATING window from its manager state (viewport coordinates). */
export function windowRectFromState(state: WindowState): SceneWindowRect {
  return { left: state.x, top: state.y, right: state.x + state.w, bottom: state.y + state.h }
}

/**
 * Aliases of open windows overlapped by another OPEN window with a higher z
 * — those windows show the raise veil (docked and floating alike). `rectOf`
 * supplies each window's viewport rect: floating from state
 * (`windowRectFromState`), docked from its tile element's bounding rect.
 */
export function buriedAliases(
  wins: Record<string, WindowState>,
  rectOf: (alias: string, state: WindowState) => SceneWindowRect | null,
): Set<string> {
  const open = Object.keys(wins).filter((id) => wins[id].open)
  const rects = new Map<string, SceneWindowRect | null>()
  open.forEach((id) => rects.set(id, rectOf(id, wins[id])))
  const buried = new Set<string>()
  open.forEach((id) => {
    const rect = rects.get(id)
    if (!rect) return
    for (const other of open) {
      if (other === id) continue
      if (wins[other].z <= wins[id].z) continue
      const orect = rects.get(other)
      if (orect && rectsIntersect(rect, orect)) {
        buried.add(id)
        break
      }
    }
  })
  return buried
}

export interface WindowState {
  open: boolean
  expanded: boolean
  /**
   * `false` while a docked component sits in its static stage slot; `true`
   * once it is promoted to a floating window (summoned widgets are always
   * floating). The SAME element is promoted in place — never reparented, so
   * the iframe keeps its state (website docked-tile model).
   */
  floating: boolean
  x: number
  y: number
  w: number
  h: number
  z: number
  /** The window has been summoned at least once → its iframe stays mounted. */
  everOpened: boolean
}

export interface WindowSizing {
  size: { w: number; h: number }
  full?: { w: number; h: number }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function clampedSize(size: { w: number; h: number }): { w: number; h: number } {
  return {
    w: Math.min(size.w, Math.max(MIN_W, window.innerWidth - 24)),
    h: Math.min(size.h + WINDOW_BAR_HEIGHT, Math.max(MIN_H, visibleBottom() - 80)),
  }
}

function defaultPlacement(sizing: WindowSizing, index: number): WindowState {
  const size = clampedSize(sizing.size)
  const offset = (index % 5) * 28
  return {
    open: false,
    expanded: false,
    floating: true,
    x: clamp(Math.round((window.innerWidth - size.w) / 2 - 40) + offset, 12, Math.max(12, window.innerWidth - size.w - 60)),
    y: 96 + offset,
    w: size.w,
    h: size.h,
    z: BASE_Z,
    everOpened: false,
  }
}

export interface WindowManager {
  wins: Record<string, WindowState>
  get: (id: string) => WindowState | undefined
  isOpen: (id: string) => boolean
  open: (id: string, sizing: WindowSizing, placement?: Partial<Pick<WindowState, 'x' | 'y' | 'w' | 'h'>>) => void
  close: (id: string) => void
  toggle: (id: string, sizing: WindowSizing) => void
  /** Register/show a docked component in its static stage slot. */
  ensureDocked: (id: string) => void
  /** Promote a docked component to a floating window at the tile's rect. */
  promote: (id: string, rect?: { x: number; y: number; w: number; h: number }) => void
  /** Send a floating docked component back to its static slot. */
  dock: (id: string) => void
  front: (id: string) => void
  setExpanded: (id: string, sizing: WindowSizing, expanded: boolean) => void
  moveTo: (id: string, x: number, y: number) => void
  resizeTo: (id: string, w: number, h: number) => void
  fitHeight: (id: string, contentHeight: number) => void
  maximize: (id: string) => void
  /** Pull open floating windows back inside the visible viewport. */
  reclampToViewport: () => void
}

export function useWindowManager(): WindowManager {
  const [wins, setWins] = useState<Record<string, WindowState>>({})
  const zRef = useRef(BASE_Z)
  const countRef = useRef(0)

  const front = useCallback((id: string) => {
    zRef.current += 3
    const z = zRef.current
    setWins((current) => (current[id] ? { ...current, [id]: { ...current[id], z } } : current))
  }, [])

  const open = useCallback((id: string, sizing: WindowSizing, placement?: Partial<Pick<WindowState, 'x' | 'y' | 'w' | 'h'>>) => {
    zRef.current += 3
    const z = zRef.current
    setWins((current) => {
      const existing = current[id]
      if (existing) {
        return { ...current, [id]: { ...existing, open: true, everOpened: true, z } }
      }
      const index = countRef.current
      countRef.current += 1
      const base = defaultPlacement(sizing, index)
      return {
        ...current,
        [id]: { ...base, ...placement, open: true, everOpened: true, z },
      }
    })
  }, [])

  const close = useCallback((id: string) => {
    setWins((current) => (current[id] ? { ...current, [id]: { ...current[id], open: false, expanded: false, floating: false } } : current))
  }, [])

  const ensureDocked = useCallback((id: string) => {
    setWins((current) => {
      const existing = current[id]
      if (existing) {
        if (existing.open) return current
        return { ...current, [id]: { ...existing, open: true, everOpened: true, floating: false, expanded: false } }
      }
      return {
        ...current,
        [id]: {
          open: true,
          expanded: false,
          floating: false,
          x: 20,
          y: 92,
          w: 480,
          h: 560,
          z: BASE_Z,
          everOpened: true,
        },
      }
    })
  }, [])

  const promote = useCallback((id: string, rect?: { x: number; y: number; w: number; h: number }) => {
    zRef.current += 3
    const z = zRef.current
    setWins((current) => {
      const win = current[id]
      if (!win) return current
      // Pop out from the tile's own place, like the website's floatTile:
      // the titlebar appears above the tile, the box keeps its size — then
      // the rect is clamped inside the viewport with a clear margin so the
      // bottom-right resize grip stays fully visible and grabbable. The top
      // edge is kept; the bottom/right are pulled in.
      let next: WindowState
      if (rect) {
        const margin = 28
        const x = clamp(Math.round(rect.x), 8, Math.max(8, window.innerWidth - MIN_W - margin))
        let y = Math.max(56, Math.round(rect.y - WINDOW_BAR_HEIGHT))
        const w = clamp(Math.round(rect.w), MIN_W, Math.max(MIN_W, window.innerWidth - x - margin))
        let h = clamp(Math.round(rect.h + WINDOW_BAR_HEIGHT), MIN_H, Math.max(MIN_H, visibleBottom() - y - margin))
        if (y + h > visibleBottom() - margin) {
          // Tiny viewport (height already at MIN_H): nudge the window up.
          y = Math.max(56, visibleBottom() - margin - h)
          h = Math.min(h, Math.max(MIN_H, visibleBottom() - y - margin))
        }
        next = { ...win, open: true, floating: true, everOpened: true, x, y, w, h, z }
      } else {
        next = { ...win, open: true, floating: true, everOpened: true, z }
      }
      return { ...current, [id]: next }
    })
  }, [])

  const dock = useCallback((id: string) => {
    setWins((current) => (current[id]
      ? { ...current, [id]: { ...current[id], floating: false, expanded: false, open: true } }
      : current))
  }, [])

  const toggle = useCallback((id: string, sizing: WindowSizing) => {
    setWins((current) => {
      const win = current[id]
      if (win?.open) {
        return { ...current, [id]: { ...win, open: false, expanded: false } }
      }
      zRef.current += 3
      const z = zRef.current
      if (win) {
        return { ...current, [id]: { ...win, open: true, everOpened: true, z } }
      }
      const index = countRef.current
      countRef.current += 1
      const base = defaultPlacement(sizing, index)
      return { ...current, [id]: { ...base, open: true, everOpened: true, z } }
    })
  }, [])

  const setExpanded = useCallback((id: string, sizing: WindowSizing, expanded: boolean) => {
    setWins((current) => {
      const win = current[id]
      if (!win) return current
      const target = expanded && sizing.full ? sizing.full : sizing.size
      let next: WindowState
      if (expanded && !sizing.full) {
        // Expand without a configured full size = maximize (bounded, leaves
        // the rail reachable), same as the website host.
        next = {
          ...win,
          expanded,
          x: 8,
          y: 58,
          w: Math.max(MIN_W, window.innerWidth - 8 - 56),
          h: Math.max(MIN_H, visibleBottom() - 58 - 8),
        }
      } else {
        const size = clampedSize(target)
        next = {
          ...win,
          expanded,
          w: size.w,
          h: size.h,
          x: clamp(win.x, 8, Math.max(8, window.innerWidth - size.w - 8)),
          y: clamp(win.y, 58, Math.max(58, visibleBottom() - 48)),
        }
      }
      return { ...current, [id]: next }
    })
  }, [])

  const moveTo = useCallback((id: string, x: number, y: number) => {
    setWins((current) => (current[id] ? { ...current, [id]: { ...current[id], x, y } } : current))
  }, [])

  const resizeTo = useCallback((id: string, w: number, h: number) => {
    setWins((current) => {
      const win = current[id]
      if (!win) return current
      // The grip must stay reachable: a resize can never push the window's
      // bottom/right past the VISIBLE viewport (host clip respected).
      return {
        ...current,
        [id]: {
          ...win,
          w: clamp(w, MIN_W, Math.max(MIN_W, window.innerWidth - win.x - 8)),
          h: clamp(h, MIN_H, Math.max(MIN_H, visibleBottom() - win.y - 8)),
        },
      }
    })
  }, [])

  /**
   * Pull every open floating window back inside the VISIBLE viewport —
   * keep the top edge, pull bottom/right in to a clear margin. Invoked when
   * the measured host clip changes (the embedding host resized/scrolled the
   * scene frame after windows were placed) and on window resize; docked
   * tiles follow automatically through the stage CSS.
   */
  const reclampToViewport = useCallback(() => {
    setWins((current) => {
      let changed = false
      const margin = 28
      const next: Record<string, WindowState> = {}
      Object.entries(current).forEach(([id, win]) => {
        if (!win.open || !win.floating) {
          next[id] = win
          return
        }
        const x = clamp(win.x, 2, Math.max(2, window.innerWidth - 60))
        let y = clamp(win.y, 56, Math.max(56, visibleBottom() - 40))
        const w = clamp(win.w, MIN_W, Math.max(MIN_W, window.innerWidth - x - margin))
        let h = clamp(win.h, MIN_H, Math.max(MIN_H, visibleBottom() - y - margin))
        if (y + h > visibleBottom() - margin) {
          y = Math.max(56, visibleBottom() - margin - h)
          h = Math.min(h, Math.max(MIN_H, visibleBottom() - y - margin))
        }
        if (x !== win.x || y !== win.y || w !== win.w || h !== win.h) {
          changed = true
          next[id] = { ...win, x, y, w, h }
        } else {
          next[id] = win
        }
      })
      return changed ? next : current
    })
  }, [])

  const fitHeight = useCallback((id: string, contentHeight: number) => {
    if (!contentHeight) return
    setWins((current) => {
      const win = current[id]
      if (!win || win.expanded) return current
      const h = Math.max(MIN_H, Math.min(Math.round(contentHeight) + WINDOW_BAR_HEIGHT, visibleBottom() - 80))
      if (Math.abs(h - win.h) <= 2) return current
      return { ...current, [id]: { ...win, h } }
    })
  }, [])

  const maximize = useCallback((id: string) => {
    zRef.current += 3
    const z = zRef.current
    setWins((current) => {
      const win = current[id]
      if (!win) return current
      return {
        ...current,
        [id]: {
          ...win,
          x: 8,
          y: 58,
          w: Math.max(MIN_W, window.innerWidth - 8 - 56),
          h: Math.max(MIN_H, visibleBottom() - 58 - 8),
          z,
        },
      }
    })
  }, [])

  const get = useCallback((id: string) => wins[id], [wins])
  const isOpen = useCallback((id: string) => Boolean(wins[id]?.open), [wins])

  return { wins, get, isOpen, open, close, toggle, ensureDocked, promote, dock, front, setExpanded, moveTo, resizeTo, fitHeight, maximize, reclampToViewport }
}

const ICON_EXPAND = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M3 16v3a2 2 0 0 0 2 2h3" />
  </svg>
)
const ICON_COLLAPSE = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M8 3v3a2 2 0 0 1-2 2H3M16 3v3a2 2 0 0 0 2 2h3M21 16h-3a2 2 0 0 0-2 2v3M3 16h3a2 2 0 0 1 2 2v3" />
  </svg>
)
const ICON_CLOSE = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" aria-hidden="true">
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
)
// "dock back" = send the tile home to its static slot (website I_DOCK glyph)
const ICON_DOCK = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 12h14M12 5l-7 7 7 7" />
  </svg>
)
const ICON_UNPIN = (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M7 17 17 7M9 7h8v8" />
  </svg>
)

export interface FloatingWindowProps {
  id: string
  title: string
  accent: string
  icon?: React.ReactNode
  hint?: string
  state: WindowState
  hasViews: boolean
  manager: WindowManager
  sizing: WindowSizing
  /** Extra titlebar buttons rendered before the view/close controls. */
  actions?: React.ReactNode
  onViewChange?: (view: 'compact' | 'expanded') => void
  onClose?: () => void
  /**
   * Docked-placement component: while `state.floating` is false the window
   * renders as a static tile filling its stage slot (no titlebar); when
   * floating, the titlebar close control becomes "dock back".
   */
  dockable?: boolean
  onUnpin?: () => void
  onDockBack?: () => void
  /** Observes the window element (used to promote from the tile's rect). */
  sectionRef?: (el: HTMLElement | null) => void
  /** Dashed drop overlay rendered over the window body during a context drag. */
  dropOverlay?: React.ReactNode
  children: React.ReactNode
}

export function FloatingWindow(props: FloatingWindowProps) {
  const { id, state, manager, sizing } = props
  const [hintVisible, setHintVisible] = useState(false)

  const startDrag = useCallback((event: React.PointerEvent<HTMLElement>) => {
    if ((event.target as HTMLElement).closest('button')) return
    manager.front(id)
    event.preventDefault()
    const handle = event.currentTarget
    try {
      handle.setPointerCapture?.(event.pointerId)
    } catch {
      /* pointer capture is best-effort */
    }
    document.body.classList.add('kdc-gesturing')
    const startX = event.clientX
    const startY = event.clientY
    const originX = state.x
    const originY = state.y
    const onMove = (move: PointerEvent) => {
      manager.moveTo(
        id,
        Math.max(2, Math.min(window.innerWidth - 60, originX + move.clientX - startX)),
        Math.max(56, Math.min(visibleBottom() - 40, originY + move.clientY - startY)),
      )
    }
    const finish = () => {
      document.body.classList.remove('kdc-gesturing')
      try {
        handle.releasePointerCapture?.(event.pointerId)
      } catch {
        /* may already be released */
      }
      handle.removeEventListener('pointermove', onMove)
      handle.removeEventListener('pointerup', finish)
      handle.removeEventListener('pointercancel', finish)
      handle.removeEventListener('lostpointercapture', finish)
    }
    handle.addEventListener('pointermove', onMove)
    handle.addEventListener('pointerup', finish)
    handle.addEventListener('pointercancel', finish)
    handle.addEventListener('lostpointercapture', finish)
  }, [id, manager, state.x, state.y])

  const startResize = useCallback((event: React.PointerEvent<HTMLElement>) => {
    manager.front(id)
    event.preventDefault()
    const handle = event.currentTarget
    try {
      handle.setPointerCapture?.(event.pointerId)
    } catch {
      /* pointer capture is best-effort */
    }
    document.body.classList.add('kdc-gesturing')
    const startX = event.clientX
    const startY = event.clientY
    const startW = state.w
    const startH = state.h
    const onMove = (move: PointerEvent) => {
      manager.resizeTo(id, startW + move.clientX - startX, startH + move.clientY - startY)
    }
    const finish = () => {
      document.body.classList.remove('kdc-gesturing')
      try {
        handle.releasePointerCapture?.(event.pointerId)
      } catch {
        /* may already be released */
      }
      handle.removeEventListener('pointermove', onMove)
      handle.removeEventListener('pointerup', finish)
      handle.removeEventListener('pointercancel', finish)
      handle.removeEventListener('lostpointercapture', finish)
    }
    handle.addEventListener('pointermove', onMove)
    handle.addEventListener('pointerup', finish)
    handle.addEventListener('pointercancel', finish)
    handle.addEventListener('lostpointercapture', finish)
  }, [id, manager, state.w, state.h])

  const toggleView = useCallback(() => {
    const next = !state.expanded
    manager.setExpanded(id, sizing, next)
    props.onViewChange?.(next ? 'expanded' : 'compact')
  }, [id, manager, props, sizing, state.expanded])

  const close = useCallback(() => {
    if (props.dockable && props.onDockBack) props.onDockBack()
    else if (props.onClose) props.onClose()
    else manager.close(id)
  }, [id, manager, props])

  if (!state.everOpened) return null

  const docked = Boolean(props.dockable && !state.floating)
  const closeTitle = props.dockable ? 'Dock back into the page' : 'Close'

  return (
    <section
      ref={(el) => props.sectionRef?.(el)}
      className={`kdc-win${docked ? ' kdc-win--docked' : ''}${state.open ? '' : ' kdc-win-hidden'}`}
      data-accent={props.accent}
      /* Docked windows carry their z too: the stage creates no stacking
       * context, so an activated docked window can stack above floating
       * windows — standard window-manager focus order for every window. */
      style={docked ? { zIndex: state.z } : { left: state.x, top: state.y, width: state.w, height: state.h, zIndex: state.z }}
      aria-label={props.title}
      onPointerDownCapture={() => manager.front(id)}
    >
      <header
        className="kdc-wbar"
        data-accent={props.accent}
        onPointerDown={docked ? undefined : startDrag}
        onMouseEnter={() => setHintVisible(true)}
        onMouseLeave={() => setHintVisible(false)}
      >
        <span className="t">
          {props.icon}
          <span>{props.title}</span>
        </span>
        {props.actions}
        {props.hasViews ? (
          <button
            type="button"
            onClick={toggleView}
            title={state.expanded ? 'Compact form' : 'Expand to full form'}
            aria-label={state.expanded ? 'Compact form' : 'Expand to full form'}
          >
            {state.expanded ? ICON_COLLAPSE : ICON_EXPAND}
          </button>
        ) : null}
        <button type="button" onClick={close} title={closeTitle} aria-label={closeTitle}>
          {props.dockable ? ICON_DOCK : ICON_CLOSE}
        </button>
      </header>
      <div className="kdc-wbody">{props.children}</div>
      <button
        type="button"
        className="kdc-wgrip"
        onPointerDown={startResize}
        title="Resize"
        aria-label="Resize"
      />
      {props.hint && hintVisible ? <div className="kdc-whint show">{props.hint}</div> : null}
      {docked && props.onUnpin ? (
        <button
          type="button"
          className="kdc-unpin"
          onClick={props.onUnpin}
          title={`Pop out ${props.title}`}
          aria-label={`Pop out ${props.title}`}
        >
          {ICON_UNPIN}
        </button>
      ) : null}
      {props.dropOverlay}
    </section>
  )
}

export interface RailEntry {
  id: string
  label: string
  title: string
  accent: string
  icon: React.ReactNode
  open: boolean
  pulse?: boolean
  onToggle: () => void
}

export function Rail({ entries }: { entries: RailEntry[] }) {
  return (
    <nav className="kdc-rail" aria-label="Summon widgets">
      {entries.map((entry) => (
        <button
          key={entry.id}
          type="button"
          data-summon={entry.id}
          data-accent={entry.accent}
          className={`${entry.open ? 'open' : ''}${entry.pulse ? ' kdc-railpulse' : ''}`}
          title={entry.title}
          aria-pressed={entry.open}
          onClick={entry.onToggle}
        >
          {entry.icon}
          <span className="vl">{entry.label}</span>
        </button>
      ))}
    </nav>
  )
}

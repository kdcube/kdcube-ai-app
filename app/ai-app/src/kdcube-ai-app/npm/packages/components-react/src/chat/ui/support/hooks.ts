/**
 * Typed Redux hooks + `useStableCallback`. Ported from the in-tree widget
 * (src/app/hooks.ts); the store types now come from the engine package
 * (`@kdcube/components-core/chat`) since the UI binds to the engine's RTK store
 * provided by <ChatStoreProvider>.
 */
import { useCallback, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import type { TypedUseSelectorHook } from 'react-redux'
import type { AppDispatch, RootState } from '@kdcube/components-core/chat'

export const useAppDispatch: () => AppDispatch = useDispatch
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector

/** A stable function reference that always calls the latest implementation —
 *  a small polyfill for the React `useEvent` proposal. */
export function useStableCallback<A extends unknown[], R>(
  fn: (...args: A) => R,
): (...args: A) => R {
  const ref = useRef(fn)
  useEffect(() => {
    ref.current = fn
  }, [fn])
  return useCallback((...args: A) => ref.current(...args), [])
}

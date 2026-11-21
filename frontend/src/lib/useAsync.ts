import { useCallback, useEffect, useState } from 'react'
import { useLatest } from './useLatest'

export type AsyncState<T> =
  { status: 'loading' } | { status: 'success'; data: T } | { status: 'error'; error: unknown }

export type AsyncResult<T> = AsyncState<T> & {
  /** Load again in the background, keeping the current data on screen. */
  reload: () => void
}

/**
 * Loads data for `key` (e.g. a search query) and reloads whenever the key
 * changes. A run that is overtaken by a newer one is aborted.
 */
export function useAsync<T>(
  load: (signal: AbortSignal) => Promise<T>,
  key: string,
): AsyncResult<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })
  const [loadedKey, setLoadedKey] = useState(key)
  const [reloadCount, setReloadCount] = useState(0)
  const loadRef = useLatest(load)

  // a new key shows the loading state right away instead of the old data
  if (key !== loadedKey) {
    setLoadedKey(key)
    setState({ status: 'loading' })
  }

  useEffect(() => {
    const controller = new AbortController()
    loadRef.current(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ status: 'success', data })
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setState({ status: 'error', error })
      },
    )
    return () => controller.abort()
  }, [key, reloadCount, loadRef])

  const reload = useCallback(() => setReloadCount((count) => count + 1), [])
  return { ...state, reload }
}

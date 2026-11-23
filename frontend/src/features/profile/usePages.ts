import { useEffect, useState } from 'react'
import { errorMessage } from '../../lib/format'
import { useLatest } from '../../lib/useLatest'

/** The API's page size: a full page means there may be more. */
const PAGE_SIZE = 30

export interface Pages<T> {
  items: T[]
  loading: boolean
  error: string | null
  hasMore: boolean
  loadMore: () => void
  /** Start over from the first page. */
  reload: () => void
}

/**
 * Items loaded a page at a time: the API continues after `before`, the
 * `lastAt` of the last item so far. Starts over when `key` changes.
 */
export function usePages<T extends { lastAt: string }>(
  load: (before: string | undefined, signal: AbortSignal) => Promise<T[]>,
  key: string,
): Pages<T> {
  const [request, setRequest] = useState<{ key: string; before?: string; attempt: number }>({
    key,
    attempt: 0,
  })
  const [result, setResult] = useState<{ key: string; items: T[]; hasMore: boolean } | null>(null)
  // the request that last finished, and how
  const [outcome, setOutcome] = useState<{ request: object; error: string | null } | null>(null)
  const loadRef = useLatest(load)

  if (request.key !== key) setRequest({ key, attempt: 0 })

  useEffect(() => {
    const controller = new AbortController()
    loadRef.current(request.before, controller.signal).then(
      (page) => {
        if (controller.signal.aborted) return
        setResult((current) => ({
          key: request.key,
          items:
            request.before !== undefined && current?.key === request.key
              ? [...current.items, ...page]
              : page,
          hasMore: page.length >= PAGE_SIZE,
        }))
        setOutcome({ request, error: null })
      },
      (reason: unknown) => {
        if (!controller.signal.aborted) setOutcome({ request, error: errorMessage(reason) })
      },
    )
    return () => controller.abort()
  }, [request, loadRef])

  const loading = outcome?.request !== request
  const error = outcome?.request === request ? outcome.error : null
  const current = result?.key === key ? result : null
  const items = current?.items ?? []
  const lastAt = items.at(-1)?.lastAt
  return {
    items,
    loading,
    error,
    hasMore: current?.hasMore ?? false,
    loadMore: () => setRequest((previous) => ({ key: previous.key, before: lastAt, attempt: 0 })),
    reload: () => setRequest((previous) => ({ key: previous.key, attempt: previous.attempt + 1 })),
  }
}

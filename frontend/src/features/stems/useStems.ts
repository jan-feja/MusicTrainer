import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { errorMessage } from '../../lib/format'
import { loadStems } from './loadStems'
import { type StemsStatus, loadingProgress } from './stems'

const POLL_INTERVAL_MS = 1000

export interface Stems {
  status: StemsStatus
  /** Try again after a failure. */
  retry: () => void
}

/**
 * The stems of a downloaded video while `enabled`: starts the separation on the
 * server if it never ran, polls while it runs, then downloads and decodes the
 * stems. Turning it off drops the decoded audio (hundreds of MB).
 */
export function useStems(videoId: string, enabled: boolean): Stems {
  const [attempt, setAttempt] = useState(0)
  const key = `${videoId}:${attempt}`
  const [result, setResult] = useState<{ key: string; status: StemsStatus } | null>(null)

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    const { signal } = controller
    let timer: number | undefined
    const show = (status: StemsStatus) => {
      if (!signal.aborted) setResult({ key, status })
    }

    const poll = async (first: boolean) => {
      try {
        let state = await api.getStems(videoId, signal)
        // a failure from before is shown, until the user asks to try again
        if (state.status === 'not_started' || (first && attempt > 0 && state.status === 'failed')) {
          state = await api.separateStems(videoId)
        }
        if (state.status === 'failed') {
          show({ kind: 'failed', error: state.error ?? 'Separation failed' })
        } else if (state.status === 'completed' && state.stems) {
          show({ kind: 'loading', progress: 0 })
          const tracks = await loadStems(videoId, state.stems, signal, (files) =>
            show({ kind: 'loading', progress: loadingProgress(files) }),
          )
          show({ kind: 'ready', tracks })
        } else if (!signal.aborted) {
          const progress = state.status === 'analyzing' ? (state.progress ?? 0) : null
          show({ kind: 'separating', progress })
          timer = window.setTimeout(() => void poll(false), POLL_INTERVAL_MS)
        }
      } catch (error) {
        show({ kind: 'failed', error: errorMessage(error) })
      }
    }
    void poll(true)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
      setResult(null) // lets go of the decoded audio
    }
  }, [videoId, enabled, attempt, key])

  let status: StemsStatus = { kind: 'off' }
  if (enabled) status = result?.key === key ? result.status : { kind: 'checking' }
  return { status, retry: () => setAttempt((count) => count + 1) }
}

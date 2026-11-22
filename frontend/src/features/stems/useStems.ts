import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { StemSet } from '../../api/types'
import { errorMessage } from '../../lib/format'
import { loadStems } from './loadStems'
import { type StemTrack, type StemsStatus, loadingProgress } from './stems'

const POLL_INTERVAL_MS = 1000

export interface Stems {
  status: StemsStatus
  /** Try again after a failure. */
  retry: () => void
}

type Separation =
  | { kind: 'separating'; progress: number | null; songsAhead: number | null }
  | { kind: 'separated'; stems: StemSet }
  | { kind: 'failed'; error: string }

type Loading =
  | { kind: 'loading'; progress: number }
  | { kind: 'ready'; tracks: StemTrack[] }
  | { kind: 'failed'; error: string }

/**
 * The stems of a downloaded video. The server separates new downloads by
 * itself; opening the video puts it first in the queue (or starts it, for
 * older videos), and it is polled while it runs.
 * While `enabled`, the separated stems are downloaded and decoded; switching
 * off drops the decoded audio (hundreds of MB).
 */
export function useStems(videoId: string | undefined, enabled: boolean): Stems {
  const [separationAttempt, setSeparationAttempt] = useState(0)
  const [loadAttempt, setLoadAttempt] = useState(0)
  const separationKey = `${videoId}:${separationAttempt}`
  const [separation, setSeparation] = useState<{ key: string; state: Separation } | null>(null)
  const current = separation?.key === separationKey ? separation.state : null
  const stemSet = current?.kind === 'separated' ? current.stems : null
  const loadKey = `${separationKey}:${loadAttempt}`
  const [loading, setLoading] = useState<{ key: string; state: Loading } | null>(null)

  useEffect(() => {
    if (!videoId) return
    const controller = new AbortController()
    const { signal } = controller
    let timer: number | undefined
    const show = (state: Separation) => {
      if (!signal.aborted) setSeparation({ key: separationKey, state })
    }
    const poll = async (first: boolean) => {
      try {
        let state = await api.getStems(videoId, signal)
        // a failure from before is shown, until the user asks to try again
        const retrying = first && separationAttempt > 0 && state.status === 'failed'
        // the open song goes first in the queue
        const waiting = first && state.status === 'queued'
        if (state.status === 'not_started' || retrying || waiting) {
          state = await api.separateStems(videoId)
        }
        if (state.status === 'failed') {
          show({ kind: 'failed', error: state.error ?? 'Separation failed' })
        } else if (state.status === 'completed' && state.stems) {
          show({ kind: 'separated', stems: state.stems })
        } else if (!signal.aborted) {
          const progress = state.status === 'analyzing' ? (state.progress ?? 0) : null
          show({ kind: 'separating', progress, songsAhead: state.queuePosition })
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
    }
  }, [videoId, separationAttempt, separationKey])

  useEffect(() => {
    if (!videoId || !enabled || !stemSet) return
    const controller = new AbortController()
    const { signal } = controller
    const show = (state: Loading) => {
      if (!signal.aborted) setLoading({ key: loadKey, state })
    }
    loadStems(videoId, stemSet, signal, (files) =>
      show({ kind: 'loading', progress: loadingProgress(files) }),
    ).then(
      (tracks) => show({ kind: 'ready', tracks }),
      (error: unknown) => show({ kind: 'failed', error: errorMessage(error) }),
    )
    return () => {
      controller.abort()
      setLoading(null) // lets go of the decoded audio
    }
  }, [videoId, enabled, stemSet, loadKey])

  let status: StemsStatus = { kind: 'checking' }
  if (current?.kind === 'separating') status = current
  else if (current?.kind === 'failed') status = current
  else if (stemSet && !enabled) status = { kind: 'available' }
  else if (stemSet) {
    const state = loading?.key === loadKey ? loading.state : null
    status =
      state?.kind === 'failed'
        ? { ...state, separated: true }
        : (state ?? { kind: 'loading', progress: 0 })
  }
  const retry = () => {
    if (current?.kind === 'failed') setSeparationAttempt((count) => count + 1)
    else setLoadAttempt((count) => count + 1)
  }
  return { status, retry }
}

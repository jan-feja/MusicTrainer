import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { BeatTrackingState } from '../../api/types'
import { errorMessage } from '../../lib/format'

const POLL_INTERVAL_MS = 1000

export interface BeatTracking {
  /** null until the first answer arrives */
  state: BeatTrackingState | null
  /** The server could not be asked (as opposed to detection failing). */
  requestError: string | null
  /** Ask again, or detect again after a failure. */
  retry: () => void
}

function isRunning(state: BeatTrackingState): boolean {
  return state.status === 'queued' || state.status === 'analyzing'
}

/**
 * Loads the beat grid of a downloaded video. Starts detection if it never ran
 * and polls while it runs. Does nothing until `enabled`.
 */
export function useBeatTracking(videoId: string, enabled = true): BeatTracking {
  const [state, setState] = useState<BeatTrackingState | null>(null)
  const [requestError, setRequestError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    let timer: number | undefined

    const poll = async () => {
      try {
        let current = await api.getBeats(videoId, controller.signal)
        if (current.status === 'not_started') {
          current = await api.detectBeats(videoId)
        }
        if (controller.signal.aborted) return
        setState(current)
        setRequestError(null)
        if (isRunning(current)) timer = window.setTimeout(poll, POLL_INTERVAL_MS)
      } catch (error) {
        if (!controller.signal.aborted) setRequestError(errorMessage(error))
      }
    }
    void poll()
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [videoId, enabled, attempt])

  const retry = () => {
    setRequestError(null)
    const pollAgain = () => setAttempt((count) => count + 1)
    if (state?.status === 'failed') {
      api.detectBeats(videoId, true).then(
        (restarted) => {
          setState(restarted)
          pollAgain()
        },
        (error: unknown) => setRequestError(errorMessage(error)),
      )
    } else {
      pollAgain()
    }
  }

  return { state, requestError, retry }
}

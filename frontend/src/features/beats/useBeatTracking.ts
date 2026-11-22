import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { BeatAnalysis, BeatGridHints, BeatTrackingState } from '../../api/types'
import { errorMessage } from '../../lib/format'

const POLL_INTERVAL_MS = 1000
// new hints often finish in well under a second: ask again sooner at first
const FIRST_POLL_INTERVAL_MS = 200
const FIRST_POLLS = 5

export interface BeatTracking {
  /** null until the first answer arrives */
  state: BeatTrackingState | null
  /** The latest finished beat grid; stays while a new one is detected. */
  analysis: BeatAnalysis | null
  /** A new grid is being detected (e.g. after new hints). */
  updating: boolean
  /** The server could not be asked (as opposed to detection failing). */
  requestError: string | null
  /** Ask again, or detect again after a failure. */
  retry: () => void
  /** Detect the grid again with what the user knows about the song. */
  setHints: (hints: BeatGridHints) => void
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
  const [finished, setFinished] = useState<{ videoId: string; analysis: BeatAnalysis } | null>(null)
  const [requestError, setRequestError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    let timer: number | undefined

    let polls = 0
    const poll = async () => {
      try {
        let current = await api.getBeats(videoId, controller.signal)
        if (current.status === 'not_started') {
          current = await api.detectBeats(videoId)
        }
        if (controller.signal.aborted) return
        setState(current)
        if (current.analysis) setFinished({ videoId, analysis: current.analysis })
        setRequestError(null)
        polls += 1
        const delay = polls <= FIRST_POLLS ? FIRST_POLL_INTERVAL_MS : POLL_INTERVAL_MS
        if (isRunning(current)) timer = window.setTimeout(poll, delay)
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

  const pollAgain = () => setAttempt((count) => count + 1)

  const restart = (options: Parameters<typeof api.detectBeats>[1]) => {
    api.detectBeats(videoId, options).then(
      (restarted) => {
        setState(restarted)
        pollAgain()
      },
      (error: unknown) => setRequestError(errorMessage(error)),
    )
  }

  const retry = () => {
    setRequestError(null)
    if (state?.status === 'failed') {
      restart({ force: true })
    } else {
      pollAgain()
    }
  }

  const setHints = (hints: BeatGridHints) => {
    setRequestError(null)
    restart({ hints })
  }

  const analysis = finished?.videoId === videoId ? finished.analysis : null
  const updating = state !== null && isRunning(state) && analysis !== null
  return { state, analysis, updating, requestError, retry, setHints }
}

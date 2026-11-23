import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { BeatAnalysis, BeatGridHints, BeatTrackingState } from '../../api/types'
import { errorMessage } from '../../lib/format'

const POLL_INTERVAL_MS = 1000
// a stored network output is decoded in well under a second: ask again sooner at first
const FIRST_POLL_INTERVAL_MS = 200
const FIRST_POLLS = 5

export interface BeatTracking {
  /** The detection's state; null until the first answer arrives. */
  state: BeatTrackingState | null
  /** The user's beat grid: the detected one with their fixes. Stays while a new one loads. */
  analysis: BeatAnalysis | null
  /** A new grid is on its way (new fixes, or detecting again). */
  updating: boolean
  /** The server could not be asked (as opposed to detection failing). */
  requestError: string | null
  /** Ask again, or detect again after a failure. */
  retry: () => void
  /** The user's fixes; null: the detected grid as it is. */
  hints: BeatGridHints | null
  /** Fix the grid with what the user knows about the song (their own grid only). */
  setHints: (hints: BeatGridHints) => void
}

function isRunning(state: BeatTrackingState): boolean {
  return state.status === 'queued' || state.status === 'analyzing'
}

/** Fixes that change nothing are no fixes. */
function meaningfulHints(hints: BeatGridHints | null | undefined): BeatGridHints | null {
  if (!hints) return null
  const none =
    hints.beatsPerBar === null &&
    hints.tempoBpm === null &&
    hints.barStarts.length === 0 &&
    !hints.steadyTempo
  return none ? null : hints
}

/**
 * The user's beat grid of a downloaded video. Starts the detection (shared by
 * everyone who has the song) if it never ran and polls while it runs; with the
 * user's fixes, asks for their own grid. Does nothing until `enabled`.
 */
export function useBeatTracking(
  videoId: string,
  enabled: boolean,
  initialHints: BeatGridHints | null = null,
): BeatTracking {
  const [state, setState] = useState<BeatTrackingState | null>(null)
  const [detected, setDetected] = useState<BeatAnalysis | null>(null)
  const [hints, setHintsState] = useState(() => meaningfulHints(initialHints))
  // the user's grid, with the fixes it was made with
  const [fixed, setFixed] = useState<{ key: string; analysis: BeatAnalysis } | null>(null)
  // with saved fixes, the detected grid is not shown while the user's own one loads
  const [showDetected, setShowDetected] = useState(hints === null)
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
        if (current.analysis) setDetected(current.analysis)
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

  const hintsKey = hints ? JSON.stringify(hints) : ''
  useEffect(() => {
    if (!detected || !hints) return
    const controller = new AbortController()
    const key = JSON.stringify(hints)
    api.getBeatGrid(videoId, hints, controller.signal).then(
      (analysis) => {
        setFixed({ key, analysis })
        setRequestError(null)
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setRequestError(errorMessage(error))
      },
    )
    return () => controller.abort()
  }, [videoId, detected, hints, attempt])

  const retry = () => {
    setRequestError(null)
    if (state?.status === 'failed') {
      api.detectBeats(videoId, { force: true }).then(
        (restarted) => {
          setState(restarted)
          setAttempt((count) => count + 1)
        },
        (error: unknown) => setRequestError(errorMessage(error)),
      )
    } else {
      setAttempt((count) => count + 1)
    }
  }

  const setHints = (next: BeatGridHints) => {
    setRequestError(null)
    setHintsState(meaningfulHints(next))
    setShowDetected(true)
  }

  let analysis = showDetected ? detected : null
  // the previous grid stays on screen while the new one loads
  if (hints && fixed) analysis = fixed.analysis
  const loadingFixed = hints !== null && detected !== null && fixed?.key !== hintsKey
  const updating =
    analysis !== null && ((state !== null && isRunning(state)) || (loadingFixed && !requestError))
  return { state, analysis, updating, requestError, retry, hints, setHints }
}

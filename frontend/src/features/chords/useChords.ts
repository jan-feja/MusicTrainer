import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { BeatAnalysis, ChordAnalysis } from '../../api/types'
import { errorMessage } from '../../lib/format'

const POLL_INTERVAL_MS = 500

export type ChordsStatus =
  | { kind: 'off' }
  | { kind: 'detecting' }
  | { kind: 'ready'; analysis: ChordAnalysis }
  | { kind: 'failed'; error: string }

export interface Chords {
  status: ChordsStatus
  retry: () => void
}

/**
 * The chords of a video on its beat grid, while `enabled`: starts detection if
 * needed (a few seconds) and polls. Asks again when the beat grid changes (the
 * user's hints), since the chords sit on it.
 */
export function useChords(videoId: string, beats: BeatAnalysis | null, enabled: boolean): Chords {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ key: string; status: ChordsStatus } | null>(null)
  const active = enabled && beats !== null
  // changes with the beat grid (and with a retry)
  const key = active ? `${videoId}:${attempt}:${gridSignature(beats.beats)}` : ''

  useEffect(() => {
    if (!active) return
    const controller = new AbortController()
    const { signal } = controller
    let timer: number | undefined
    const show = (status: ChordsStatus) => {
      if (!signal.aborted) setResult({ key, status })
    }
    const poll = async (first: boolean) => {
      try {
        let state = await api.getChords(videoId, signal)
        if (state.status === 'not_started' || (first && attempt > 0 && state.status === 'failed')) {
          state = await api.detectChords(videoId)
        }
        if (state.status === 'completed' && state.analysis) {
          show({ kind: 'ready', analysis: state.analysis })
        } else if (state.status === 'failed') {
          show({ kind: 'failed', error: state.error ?? 'Chord detection failed' })
        } else if (!signal.aborted) {
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
  }, [videoId, active, attempt, key])

  let status: ChordsStatus = { kind: 'off' }
  if (active) {
    // the chords of the previous grid stay on screen while the new ones are detected
    if (result?.key === key) status = result.status
    else if (result?.status.kind === 'ready') status = result.status
    else status = { kind: 'detecting' }
  }
  return { status, retry: () => setAttempt((count) => count + 1) }
}

function gridSignature(beats: readonly number[]): string {
  return `${beats.length}:${beats.reduce((sum, beat) => sum + beat, 0).toFixed(3)}`
}

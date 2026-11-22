import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { PlayerSettings, SavedLoop } from '../../api/types'
import { errorMessage } from '../../lib/format'
import { type AsyncResult, useAsync } from '../../lib/useAsync'
import { useLatest } from '../../lib/useLatest'

export interface PracticeData {
  loops: SavedLoop[]
  settings: PlayerSettings
}

export interface PracticeStorage {
  data: AsyncResult<PracticeData>
  /** Store the loops / settings a moment later; the latest value wins. */
  saveLoops: (loops: SavedLoop[]) => void
  saveSettings: (settings: PlayerSettings) => void
  /** The last save failed with this message. */
  saveError: string | null
}

const LOOPS_SAVE_DELAY_MS = 300
// settings change often (volume drags, the position while playing)
const SETTINGS_SAVE_DELAY_MS = 1000

/** Loads a video's saved loops and player settings, and stores changes to them. */
export function usePracticeStorage(videoId: string): PracticeStorage {
  const data = useAsync(async (signal) => {
    const [loops, settings] = await Promise.all([
      api.getLoops(videoId, signal),
      api.getPlayerSettings(videoId, signal),
    ])
    return { loops, settings }
  }, videoId)
  const loops = useDelayedSave<SavedLoop[]>(
    (value, keepalive) => api.saveLoops(videoId, value, keepalive),
    LOOPS_SAVE_DELAY_MS,
  )
  const settings = useDelayedSave<PlayerSettings>(
    (value, keepalive) => api.savePlayerSettings(videoId, value, keepalive),
    SETTINGS_SAVE_DELAY_MS,
  )
  return {
    data,
    saveLoops: loops.save,
    saveSettings: settings.save,
    saveError: loops.error ?? settings.error,
  }
}

/**
 * Saves the latest value `delayMs` after the last change, one request at a
 * time. Whatever is pending is sent when the page is left or closed.
 */
function useDelayedSave<T>(
  send: (value: T, keepalive: boolean) => Promise<unknown>,
  delayMs: number,
): { save: (value: T) => void; error: string | null } {
  const sendRef = useLatest(send)
  const pending = useRef<{ value: T } | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const [error, setError] = useState<string | null>(null)

  const flush = useCallback(
    (keepalive: boolean) => {
      clearTimeout(timer.current)
      const next = pending.current
      if (next === null) return
      pending.current = null
      // one request at a time, so an older value never overwrites a newer one
      queue.current = queue.current
        .then(() => sendRef.current(next.value, keepalive))
        .then(
          () => setError(null),
          (reason: unknown) => setError(errorMessage(reason)),
        )
    },
    [sendRef],
  )

  const save = useCallback(
    (value: T) => {
      pending.current = { value }
      clearTimeout(timer.current)
      timer.current = setTimeout(() => flush(false), delayMs)
    },
    [flush, delayMs],
  )

  useEffect(() => {
    const leave = () => flush(true)
    window.addEventListener('pagehide', leave)
    return () => {
      window.removeEventListener('pagehide', leave)
      leave()
    }
  }, [flush])

  return { save, error }
}

import { useCallback, useEffect, useRef, useState } from 'react'
import type { PlayerSettings, Preset } from '../../api/types'
import { errorMessage } from '../../lib/format'
import { type AsyncResult, useAsync } from '../../lib/useAsync'
import { useLatest } from '../../lib/useLatest'
import { type PracticeData, useMyLibrary } from '../library/myLibrary'

export interface PracticeStorage {
  data: AsyncResult<PracticeData>
  /** Store the presets / settings a moment later; the latest value wins. */
  savePresets: (presets: Preset[]) => void
  saveSettings: (settings: PlayerSettings) => void
  /** The last save failed with this message. */
  saveError: string | null
}

const PRESETS_SAVE_DELAY_MS = 300
// settings change often (volume drags, the position while playing)
const SETTINGS_SAVE_DELAY_MS = 1000

/**
 * Adds the video to the user's library, loads the user's presets and
 * player settings for it, and stores changes to them (on the server for an
 * account, in this browser for a guest).
 */
export function usePracticeStorage(videoId: string): PracticeStorage {
  const library = useMyLibrary()
  const data = useAsync((signal) => library.openSong(videoId, signal), videoId)
  const presets = useDelayedSave<Preset[]>(
    (value, keepalive) => library.savePresets(videoId, value, keepalive),
    PRESETS_SAVE_DELAY_MS,
  )
  const settings = useDelayedSave<PlayerSettings>(
    (value, keepalive) => library.saveSettings(videoId, value, keepalive),
    SETTINGS_SAVE_DELAY_MS,
  )
  return {
    data,
    savePresets: presets.save,
    saveSettings: settings.save,
    saveError: presets.error ?? settings.error,
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

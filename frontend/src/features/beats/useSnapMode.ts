import { useCallback, useState } from 'react'
import { type SnapMode, isSnapMode } from './beatGrid'

const STORAGE_KEY = 'musicTrainer.loopSnapMode'

function readStoredSnapMode(): SnapMode {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isSnapMode(stored) ? stored : 'off'
  } catch {
    return 'off' // storage blocked (private mode, ...)
  }
}

/**
 * The loop snap setting. Starts at `initial` (the video's own setting), else
 * at the one used last in this browser, which each change also remembers.
 */
export function useSnapMode(initial?: SnapMode | null): [SnapMode, (mode: SnapMode) => void] {
  const [mode, setMode] = useState<SnapMode>(() => initial ?? readStoredSnapMode())

  const changeMode = useCallback((next: SnapMode) => {
    setMode(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // not remembered; still works for this page
    }
  }, [])

  return [mode, changeMode]
}

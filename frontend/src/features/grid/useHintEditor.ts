import { useCallback, useEffect, useRef, useState } from 'react'
import type { BeatGridHints } from '../../api/types'
import { useLatest } from '../../lib/useLatest'
import type { BeatTracking } from '../beats/useBeatTracking'
import { sameHints } from './gridHints'

/** Edits are sent this long after the last one (taps come in quick succession). */
export const SEND_DELAY_MS = 700
const HISTORY_LENGTH = 50

export interface HintEditor {
  /** The hints with the user's latest edits (shown at once, decoded a moment later). */
  hints: BeatGridHints | null
  /** Edits not yet in the grid. */
  pending: boolean
  edit: (next: BeatGridHints) => void
  undo: () => void
  canUndo: boolean
}

/**
 * The grid editor's hints. Edits apply locally at once and go to the backend a moment after
 * the last one, one decoding at a time (the backend ignores hints while it decodes).
 */
export function useHintEditor(tracking: BeatTracking): HintEditor {
  const { analysis, updating } = tracking
  const setHints = useLatest(tracking.setHints)
  const [draft, setDraft] = useState<BeatGridHints | null>(null)
  const [history, setHistory] = useState<BeatGridHints[]>([])
  const sent = useRef<BeatGridHints | null>(null)
  const applied = analysis?.hints ?? null
  const hints = draft ?? applied

  // the grid caught up with the draft: nothing pending any more
  if (draft && applied && !updating && sameHints(draft, applied)) setDraft(null)

  useEffect(() => {
    if (!draft || !applied || updating || sameHints(draft, applied)) return
    if (sent.current && sameHints(sent.current, draft)) return // on its way
    const timer = window.setTimeout(() => {
      sent.current = draft
      setHints.current(draft)
    }, SEND_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [draft, applied, updating, setHints])

  // a new grid arrived: what was sent is done (if it differs, it is sent again)
  useEffect(() => {
    sent.current = null
  }, [applied])

  const edit = useCallback(
    (next: BeatGridHints) => {
      if (!hints || sameHints(next, hints)) return
      setHistory((past) => [...past, hints].slice(-HISTORY_LENGTH))
      setDraft(next)
    },
    [hints],
  )

  const undo = useCallback(() => {
    const previous = history.at(-1)
    if (!previous) return
    setHistory((past) => past.slice(0, -1))
    setDraft(previous)
  }, [history])

  return { hints, pending: draft !== null, edit, undo, canUndo: history.length > 0 }
}

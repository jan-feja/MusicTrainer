import { useCallback, useEffect, useRef, useState } from 'react'
import type { SavedLoop } from '../../api/types'
import { useLatest } from '../../lib/useLatest'
import { changedLoop, sortLoops } from './loopList'

export interface SavedLoops {
  /** In playing order. */
  loops: SavedLoop[]
  /** The saved loop being played and edited. */
  activeId: string | null
  active: SavedLoop | null
  /** Add a loop and make it the active one. */
  add: (loop: SavedLoop) => void
  update: (id: string, changes: Partial<SavedLoop>) => void
  remove: (id: string) => void
  setActiveId: (id: string | null) => void
}

/** The saved loops of a video; `onChange` gets every changed list (to store it). */
export function useSavedLoops(
  initialLoops: readonly SavedLoop[],
  initialActiveId: string | null,
  onChange?: (loops: SavedLoop[]) => void,
): SavedLoops {
  const [loops, setLoops] = useState(() => sortLoops(initialLoops))
  const [activeId, setActiveId] = useState(() =>
    initialLoops.some((loop) => loop.id === initialActiveId) ? initialActiveId : null,
  )
  const onChangeRef = useLatest(onChange)
  const reported = useRef(loops)

  useEffect(() => {
    if (loops === reported.current) return
    reported.current = loops
    onChangeRef.current?.(loops)
  }, [loops, onChangeRef])

  const add = useCallback((loop: SavedLoop) => {
    setLoops((current) => sortLoops([...current, loop]))
    setActiveId(loop.id)
  }, [])

  const update = useCallback((id: string, changes: Partial<SavedLoop>) => {
    setLoops((current) => {
      const index = current.findIndex((loop) => loop.id === id)
      const next = index === -1 ? null : changedLoop(current[index], changes)
      return next ? sortLoops(current.map((loop, i) => (i === index ? next : loop))) : current
    })
  }, [])

  const remove = useCallback((id: string) => {
    setLoops((current) => current.filter((loop) => loop.id !== id))
    setActiveId((current) => (current === id ? null : current))
  }, [])

  const active = loops.find((loop) => loop.id === activeId) ?? null
  return { loops, activeId, active, add, update, remove, setActiveId }
}

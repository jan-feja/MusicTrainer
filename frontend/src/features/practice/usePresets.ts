import { useCallback, useEffect, useRef, useState } from 'react'
import type { Preset } from '../../api/types'
import { useLatest } from '../../lib/useLatest'
import { sortPresets } from './presets'

export interface Presets {
  /** Whole-song presets first, then the loops in playing order. */
  presets: Preset[]
  /** The preset chosen last. */
  activeId: string | null
  active: Preset | null
  /** Add a preset and make it the active one. */
  add: (preset: Preset) => void
  /** Replace a preset (same id), e.g. with the player as it is now. */
  replace: (preset: Preset) => void
  rename: (id: string, name: string) => void
  remove: (id: string) => void
  setActiveId: (id: string | null) => void
}

/** The presets of a video; `onChange` gets every changed list (to store it). */
export function usePresets(
  initialPresets: readonly Preset[],
  initialActiveId: string | null,
  onChange?: (presets: Preset[]) => void,
): Presets {
  const [presets, setPresets] = useState(() => sortPresets(initialPresets))
  const [activeId, setActiveId] = useState(() =>
    initialPresets.some((preset) => preset.id === initialActiveId) ? initialActiveId : null,
  )
  const onChangeRef = useLatest(onChange)
  const reported = useRef(presets)

  useEffect(() => {
    if (presets === reported.current) return
    reported.current = presets
    onChangeRef.current?.(presets)
  }, [presets, onChangeRef])

  const add = useCallback((preset: Preset) => {
    setPresets((current) => sortPresets([...current, preset]))
    setActiveId(preset.id)
  }, [])

  const replace = useCallback((preset: Preset) => {
    setPresets((current) =>
      sortPresets(current.map((candidate) => (candidate.id === preset.id ? preset : candidate))),
    )
  }, [])

  const rename = useCallback((id: string, name: string) => {
    setPresets((current) =>
      current.map((preset) =>
        preset.id === id && preset.name !== name ? { ...preset, name } : preset,
      ),
    )
  }, [])

  const remove = useCallback((id: string) => {
    setPresets((current) => current.filter((preset) => preset.id !== id))
    setActiveId((current) => (current === id ? null : current))
  }, [])

  const active = presets.find((preset) => preset.id === activeId) ?? null
  return { presets, activeId, active, add, replace, rename, remove, setActiveId }
}

/**
 * Saved loops: the practice loops kept with a video. Pure functions, no React.
 */
import type { LoopSnapMode, SavedLoop } from '../../api/types'
import { formatTimePrecise } from '../../lib/format'
import { type BeatGrid, describeGridLength, gridPoints, stepsBetween } from '../beats/beatGrid'
import { formatPlaybackRate } from '../player/playbackRate'

export const MAX_LOOP_NAME_LENGTH = 100

/** In playing order: by start, then by end. */
export function sortLoops(loops: readonly SavedLoop[]): SavedLoop[] {
  return [...loops].sort((a, b) => a.start - b.start || a.end - b.end)
}

/** An id unique enough within one video (also where crypto.randomUUID is missing: plain http). */
export function newLoopId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
}

/** "Loop 1", "Loop 2", ...: one more than the highest number used so far. */
export function nextLoopName(loops: readonly SavedLoop[]): string {
  const numbers = loops.map((loop) => /^Loop (\d+)$/.exec(loop.name)?.[1]).map(Number)
  const highest = Math.max(0, ...numbers.filter(Number.isFinite))
  return `Loop ${highest + 1}`
}

export function createLoop(
  loops: readonly SavedLoop[],
  region: { start: number; end: number },
  snapMode: LoopSnapMode,
  playbackRate: number,
): SavedLoop {
  return {
    id: newLoopId(),
    name: nextLoopName(loops),
    start: region.start,
    end: region.end,
    snapMode,
    playbackRate,
  }
}

/** The loop with `changes`, or null when they change nothing. */
export function changedLoop(loop: SavedLoop, changes: Partial<SavedLoop>): SavedLoop | null {
  const next = { ...loop, ...changes }
  const keys = Object.keys(changes) as (keyof SavedLoop)[]
  return keys.some((key) => next[key] !== loop[key]) ? next : null
}

/** A name as typed: trimmed and not too long; null if nothing is left. */
export function cleanLoopName(name: string): string | null {
  const trimmed = name.trim().slice(0, MAX_LOOP_NAME_LENGTH)
  return trimmed === '' ? null : trimmed
}

/** "1:00.6 · 2 bars · 0.75×": where the loop starts, its length and its speed. */
export function describeLoop(loop: SavedLoop, grid: BeatGrid | null): string {
  const unit = loop.snapMode === 'off' ? null : loop.snapMode
  const length =
    grid && unit
      ? describeGridLength(
          stepsBetween(gridPoints(grid, unit), loop.start, loop.end),
          unit,
          grid.beatsPerBar,
        )
      : `${(loop.end - loop.start).toFixed(1)} s`
  const parts = [formatTimePrecise(loop.start), length]
  if (loop.playbackRate !== 1) parts.push(formatPlaybackRate(loop.playbackRate))
  return parts.join(' · ')
}

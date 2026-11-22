/**
 * Beat grid: snapping loop points to beats or bar starts. Pure functions, no React.
 */
import type { BeatAnalysis } from '../../api/types'

export type SnapMode = 'off' | 'beat' | 'bar'
export type GridUnit = Exclude<SnapMode, 'off'>

export const SNAP_MODES: readonly SnapMode[] = ['off', 'beat', 'bar']

/**
 * When the loop is snapped to the grid, it is played this much early. The beat
 * detector places beats ~20 ms after sharp attacks (experiments/test_beats_followup.py),
 * so without a lead every repeat would clip the attack of the first note.
 */
export const SNAP_LEAD_SECONDS = 0.03

export interface BeatGrid {
  beats: readonly number[]
  /** Bar starts, after the user's correction of the bar position. */
  bars: readonly number[]
  beatsPerBar: number | null
  bpm: number | null
}

/**
 * Build the grid. `barShift` moves every bar start by whole beats, for songs
 * where the detector put the bar start on the wrong beat.
 */
export function createBeatGrid(analysis: BeatAnalysis): BeatGrid {
  return {
    beats: analysis.beats,
    bars: analysis.downbeats,
    beatsPerBar: analysis.beatsPerBar,
    bpm: analysis.bpm,
  }
}

/**
 * The bar starts to send as a hint when the user moves the bars one beat
 * earlier (-1) or later (+1) from the bar at `time` on. Their other bar starts
 * stay, so a fix after an odd bar keeps the bars before it.
 */
export function shiftedBarStarts(analysis: BeatAnalysis, time: number, delta: -1 | 1): number[] {
  const { beats, downbeats, hints } = analysis
  if (beats.length === 0) return hints.barStarts
  let bar = 0
  while (bar + 1 < downbeats.length && downbeats[bar + 1] <= time + 1e-3) bar += 1
  const barStart = downbeats.length > 0 ? downbeats[bar] : beats[0]
  const nextBarStart = bar + 1 < downbeats.length ? downbeats[bar + 1] : Infinity
  let target = nearestIndex(beats, barStart) + delta
  // no beat before the first one: moving earlier there means the next bar starts a beat early
  if (target < 0) target += analysis.beatsPerBar ?? 4
  const targetTime = beats[Math.min(target, beats.length - 1)]
  const from = Math.min(barStart, targetTime) - 1e-3
  const kept = hints.barStarts.filter((t) => t < from || t >= nextBarStart)
  return [...kept, targetTime].sort((a, b) => a - b)
}

export function gridPoints(grid: BeatGrid, unit: GridUnit): readonly number[] {
  return unit === 'bar' ? grid.bars : grid.beats
}

/** Index of the point nearest to `time` (binary search); -1 if there are no points. */
export function nearestIndex(points: readonly number[], time: number): number {
  if (points.length === 0) return -1
  let low = 0
  let high = points.length - 1
  while (low < high) {
    const middle = (low + high) >> 1
    if (points[middle] < time) low = middle + 1
    else high = middle
  }
  // `low` is the first point >= time; the one before may be closer
  return low > 0 && time - points[low - 1] <= points[low] - time ? low - 1 : low
}

export function snapToGrid(points: readonly number[], time: number): number {
  const index = nearestIndex(points, time)
  return index === -1 ? time : points[index]
}

/** From the point nearest to `time`, move `steps` points (negative = earlier), staying on the grid. */
export function stepOnGrid(points: readonly number[], time: number, steps: number): number {
  const index = nearestIndex(points, time)
  if (index === -1) return time
  return points[Math.min(Math.max(index + steps, 0), points.length - 1)]
}

/** Number of grid steps between two times, after snapping both. */
export function stepsBetween(points: readonly number[], start: number, end: number): number {
  return nearestIndex(points, end) - nearestIndex(points, start)
}

/**
 * Snap both loop points. If both land on the same point, the end moves to the
 * next point (or the start to the previous one), so the loop never vanishes.
 */
export function snapRegion(
  points: readonly number[],
  start: number,
  end: number,
): { start: number; end: number } | null {
  if (points.length < 2) return null
  let startIndex = nearestIndex(points, start)
  let endIndex = nearestIndex(points, end)
  if (endIndex <= startIndex) {
    if (startIndex < points.length - 1) endIndex = startIndex + 1
    else startIndex = endIndex - 1
  }
  return { start: points[startIndex], end: points[endIndex] }
}

export function nextSnapMode(mode: SnapMode): SnapMode {
  return SNAP_MODES[(SNAP_MODES.indexOf(mode) + 1) % SNAP_MODES.length]
}

export function isSnapMode(value: unknown): value is SnapMode {
  return typeof value === 'string' && (SNAP_MODES as readonly string[]).includes(value)
}

/** "4 bars", "1 beat", "16 beats (4 bars)" */
export function describeGridLength(
  steps: number,
  unit: GridUnit,
  beatsPerBar: number | null,
): string {
  const count = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
  if (unit === 'bar') return count(steps, 'bar')
  const beats = count(steps, 'beat')
  return beatsPerBar && steps >= beatsPerBar && steps % beatsPerBar === 0
    ? `${beats} (${count(steps / beatsPerBar, 'bar')})`
    : beats
}

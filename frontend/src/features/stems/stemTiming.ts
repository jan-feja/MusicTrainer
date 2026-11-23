/**
 * Timing of the stem player (see stemPlayer.ts), free of browser APIs so it is
 * easy to test. Positions are song time in seconds; `at` is AudioContext time.
 */
import type { LoopRegion } from '../player/loop'
import type { LoopSchedule } from '../player/loopSchedule'

/**
 * What the stems play from `at` on: song time `from` onwards at `rate`, looping
 * the region if one is given. Like the plain loop, a start at or after the loop
 * end starts the loop over.
 */
export function stemSchedule(
  at: number,
  from: number,
  rate: number,
  region: LoopRegion | null,
): LoopSchedule {
  if (!region) return { at, from: Math.max(0, from), rate, start: 0, end: Infinity }
  const start = from >= region.end ? region.start : Math.max(0, from)
  return { at, from: start, rate, start: region.start, end: region.end }
}

/** Pitch shift that undoes the pitch change of playing `rate` times as fast. */
export function semitonesFor(rate: number): number {
  return -12 * Math.log2(rate)
}

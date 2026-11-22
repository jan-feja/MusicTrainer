import type { BeatGrid } from '../beats/beatGrid'
import type { LoopRegion } from '../player/loop'

export interface MetronomeClick {
  /** Seconds from the clock position used to plan the clicks. */
  offset: number
  accent: boolean
}

function lowerBound(points: readonly number[], time: number): number {
  let low = 0
  let high = points.length
  while (low < high) {
    const middle = (low + high) >> 1
    if (points[middle] < time) low = middle + 1
    else high = middle
  }
  return low
}

/** Project a song position through the active loop, including the approach to it. */
export function metronomePosition(
  position: number,
  distance: number,
  loop: LoopRegion | null,
): number {
  const next = position + distance
  if (!loop || position >= loop.end || next < loop.end) return next
  return loop.start + ((next - loop.end) % (loop.end - loop.start))
}

/** Plan beats in the half-open clock interval [from, to), following loop wraps. */
export function planMetronomeClicks(
  grid: BeatGrid,
  position: number,
  rate: number,
  from: number,
  to: number,
  loop: LoopRegion | null,
): MetronomeClick[] {
  if (rate <= 0 || from >= to) return []
  const clicks: MetronomeClick[] = []
  const accents = new Set(grid.bars)
  const epsilon = 1e-9
  const addClick = (time: number, beat: number) => {
    let offset = time
    if (Math.abs(offset - from) < epsilon) offset = from
    if (Math.abs(offset - to) < epsilon) offset = to
    if (offset >= from && offset < to) clicks.push({ offset, accent: accents.has(beat) })
  }
  const wraps = loop !== null && position < loop.end
  const firstEnd = wraps ? loop.end : Infinity
  const firstBeat = Math.max(position, position + from * rate - epsilon)
  for (let index = lowerBound(grid.beats, firstBeat); index < grid.beats.length; index += 1) {
    const beat = grid.beats[index]
    if (beat >= firstEnd || (beat - position) / rate > to + epsilon) break
    addClick((beat - position) / rate, beat)
  }
  if (wraps) {
    const period = (loop.end - loop.start) / rate
    for (let index = lowerBound(grid.beats, loop.start); index < grid.beats.length; index += 1) {
      const beat = grid.beats[index]
      if (beat >= loop.end) break
      const first = (loop.end - position + beat - loop.start) / rate
      let repeat = Math.max(0, Math.floor((from - first) / period))
      while (first + repeat * period <= to + epsilon) {
        addClick(first + repeat * period, beat)
        repeat += 1
      }
    }
  }
  return clicks.sort((a, b) => a.offset - b.offset)
}

/** Distance on the song clock, treating the two sides of a loop boundary as adjacent. */
export function metronomeDrift(actual: number, expected: number, loop: LoopRegion | null): number {
  const distance = Math.abs(actual - expected)
  if (
    !loop ||
    actual < loop.start ||
    actual >= loop.end ||
    expected < loop.start ||
    expected >= loop.end
  ) {
    return distance
  }
  return Math.min(distance, loop.end - loop.start - distance)
}

/**
 * Timing rules of the gapless loop (see gaplessLoop.ts), free of browser APIs
 * so they are easy to test. Times named `at`, `now` or `time` are on the audio
 * clock (AudioContext time); everything else is song time in seconds.
 */
import type { LoopRegion } from './loop'

/** What the loop voice plays: from `at` on, song time `from` onwards at `rate`, looping [start, end). */
export interface LoopSchedule {
  at: number
  from: number
  rate: number
  start: number
  end: number
}

/** A stretch of the song's audio held in the browser. */
export interface AudioWindow {
  start: number
  end: number
}

/** Audio fetched on each side of the loop, so that moving its points rarely needs a new fetch. */
export const WINDOW_MARGIN = 10
/** Audio the time stretcher reads around the position it plays. */
const STRETCH_CONTEXT = 0.5
/** A window ending this close to the end of the media counts as reaching it (audio tracks end early). */
const END_TOLERANCE = 0.5

/** Song time that `schedule` plays at `time` (its start for times before `at`). */
export function scheduledPosition(schedule: LoopSchedule, time: number): number {
  const { at, from, rate, start, end } = schedule
  const position = from + Math.max(0, time - at) * rate
  return position < end ? position : start + ((position - end) % (end - start))
}

/**
 * The schedule from `at` on after a change of rate or loop points. Playback
 * continues where it is (or at `from`); a position outside the loop starts it over.
 */
export function rescheduled(
  schedule: LoopSchedule,
  at: number,
  changes: Partial<Pick<LoopSchedule, 'rate' | 'start' | 'end'>>,
  from = scheduledPosition(schedule, at),
): LoopSchedule {
  const next = { ...schedule, ...changes, at, from }
  if (next.from < next.start || next.from >= next.end) next.from = next.start
  return next
}

/** The audio to fetch for a loop: the loop and margins, within the media, on whole milliseconds. */
export function audioWindowFor(region: LoopRegion, duration: number): AudioWindow {
  return {
    start: Math.floor(Math.max(0, region.start - WINDOW_MARGIN) * 1000) / 1000,
    end: Math.ceil(Math.min(duration, region.end + WINDOW_MARGIN) * 1000) / 1000,
  }
}

/** Whether `window` holds all the audio needed to play the loop. */
export function windowCovers(window: AudioWindow, region: LoopRegion, duration: number): boolean {
  const startCovered = window.start === 0 || region.start - STRETCH_CONTEXT >= window.start
  const endCovered =
    window.end >= duration - END_TOLERANCE || region.end + STRETCH_CONTEXT <= window.end
  return startCovered && endCovered
}

/**
 * When the loop voice should take over from the video: the audio-clock time at
 * which the video reaches the loop end, or null while that is more than
 * `lookahead` away. Never sooner than `earliest` from now.
 */
export function handoverTime(
  now: number,
  videoTime: number,
  rate: number,
  loopEnd: number,
  earliest: number,
  lookahead: number,
): number | null {
  const untilEnd = (loopEnd - videoTime) / rate
  if (untilEnd > lookahead) return null
  return now + Math.max(untilEnd, earliest)
}

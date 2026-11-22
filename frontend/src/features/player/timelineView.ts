/**
 * Timeline zoom: which part of the song the timeline shows. Pure functions, no React.
 */
import { clamp } from '../../lib/math'

/** The shown part of the song, in seconds. */
export interface TimeView {
  start: number
  end: number
}

/** The timeline zooms in no further than this many seconds. */
export const MIN_VIEW_SECONDS = 1
/** One click on zoom in / out. */
export const ZOOM_STEP = 2
/** Fitting a loop leaves this share of its length free on each side (the loop fills ~83 %). */
const FIT_MARGIN = 0.1
/** When the playhead runs off the right edge, the view moves on and shows it this far in. */
const FOLLOW_OFFSET = 0.05

export function wholeView(duration: number): TimeView {
  return { start: 0, end: Math.max(0, duration) }
}

/** The view kept inside the song and between MIN_VIEW_SECONDS and the whole song long. */
export function clampView(view: TimeView, duration: number): TimeView {
  if (duration <= 0) return wholeView(0)
  const length = clamp(view.end - view.start, Math.min(MIN_VIEW_SECONDS, duration), duration)
  const start = clamp(view.start, 0, duration - length)
  return { start, end: start + length }
}

export function isZoomed(view: TimeView, duration: number): boolean {
  return duration > 0 && view.end - view.start < duration - 1e-6
}

/** How many times the view is zoomed in (1 = the whole song). */
export function zoomFactor(view: TimeView, duration: number): number {
  const length = view.end - view.start
  return length > 0 ? duration / length : 1
}

/** Zoom by `factor` (below 1 zooms in), keeping the time `anchor` where it is on screen. */
export function zoomView(
  view: TimeView,
  factor: number,
  anchor: number,
  duration: number,
): TimeView {
  const length = view.end - view.start
  const newLength = clamp(length * factor, Math.min(MIN_VIEW_SECONDS, duration), duration)
  const ratio = length > 0 ? clamp((anchor - view.start) / length, 0, 1) : 0.5
  const start = anchor - ratio * newLength
  return clampView({ start, end: start + newLength }, duration)
}

/** Move the view by `seconds` (negative = earlier), within the song. */
export function panView(view: TimeView, seconds: number, duration: number): TimeView {
  return clampView({ start: view.start + seconds, end: view.end + seconds }, duration)
}

/** A view in which `region` fills most of the timeline. */
export function fitView(region: { start: number; end: number }, duration: number): TimeView {
  const margin = (region.end - region.start) * FIT_MARGIN
  let start = region.start - margin
  let end = region.end + margin
  if (end - start < MIN_VIEW_SECONDS) {
    const middle = (start + end) / 2
    start = middle - MIN_VIEW_SECONDS / 2
    end = middle + MIN_VIEW_SECONDS / 2
  }
  return clampView({ start, end }, duration)
}

/**
 * While playing, the view moves on when the playhead runs off its right edge.
 * Only if the playhead was in view before, so a view the user moved elsewhere
 * stays where it is. Null: leave the view as it is.
 */
export function followPlayhead(
  view: TimeView,
  previousTime: number,
  time: number,
  duration: number,
): TimeView | null {
  const wasInView = previousTime >= view.start && previousTime <= view.end
  if (!wasInView || time <= view.end) return null
  const length = view.end - view.start
  const start = time - length * FOLLOW_OFFSET
  return clampView({ start, end: start + length }, duration)
}

/** Index of the first of the sorted `times` at or after `time`. */
export function firstIndexFrom(times: readonly number[], time: number): number {
  let low = 0
  let high = times.length
  while (low < high) {
    const middle = (low + high) >> 1
    if (times[middle] < time) low = middle + 1
    else high = middle
  }
  return low
}

/** The range [first, last) of the sorted `times` inside the view. */
export function visibleRange(times: readonly number[], view: TimeView): [number, number] {
  return [firstIndexFrom(times, view.start), firstIndexFrom(times, view.end + 1e-9)]
}

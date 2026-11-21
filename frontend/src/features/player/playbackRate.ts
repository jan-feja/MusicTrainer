import { clamp } from '../../lib/math'

export const MIN_PLAYBACK_RATE = 0.25
export const MAX_PLAYBACK_RATE = 2
export const PLAYBACK_RATE_STEP = 0.05
export const PLAYBACK_RATE_PRESETS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2] as const

/** Keep the rate in range and on the 0.05 grid (avoids values like 0.8500000001). */
export function normalizePlaybackRate(rate: number): number {
  const snapped = Math.round(rate / PLAYBACK_RATE_STEP) * PLAYBACK_RATE_STEP
  return Number(clamp(snapped, MIN_PLAYBACK_RATE, MAX_PLAYBACK_RATE).toFixed(2))
}

/** Change the rate by `steps` steps of 0.05 (negative = slower). */
export function stepPlaybackRate(rate: number, steps: number): number {
  return normalizePlaybackRate(rate + steps * PLAYBACK_RATE_STEP)
}

/** 0.85 -> "0.85×", 1 -> "1×" */
export function formatPlaybackRate(rate: number): string {
  return `${Number(rate.toFixed(2))}×`
}

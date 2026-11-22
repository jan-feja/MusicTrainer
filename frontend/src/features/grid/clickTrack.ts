/**
 * A click on every beat of the grid while the song plays, higher and louder on bar starts:
 * to hear whether the grid is right, and to practice with.
 *
 * A timer looks a little ahead of the song position and schedules the clicks due in that
 * time on a Web Audio clock (sample-exact, unlike timers). A jump of the position (a seek,
 * the loop going back to its start) starts the schedule over from there.
 */
import { useEffect } from 'react'
import { useLatest } from '../../lib/useLatest'

/** Clicks are scheduled this far ahead (seconds of real time). */
export const LOOKAHEAD_SECONDS = 0.12
const TICK_MS = 25
/** The position this far from where it should be: a seek or a loop jump. */
const JUMP_TOLERANCE = 0.2
const CLICK_SECONDS = 0.05

export interface DueClick {
  /** Seconds from now (real time). */
  delay: number
  accent: boolean
}

/** First beat at or after `time`. */
export function firstBeatFrom(beats: readonly number[], time: number): number {
  let lo = 0
  let hi = beats.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (beats[mid] < time) lo = mid + 1
    else hi = mid
  }
  return lo
}

/**
 * The clicks to schedule now: beats from index `next` on that are heard within `lookahead`
 * seconds at `rate`, and the index to go on from. Beats already behind the position are
 * skipped silently.
 */
export function dueClicks(
  beats: readonly number[],
  bars: ReadonlySet<number>,
  next: number,
  position: number,
  rate: number,
  lookahead: number = LOOKAHEAD_SECONDS,
): { clicks: DueClick[]; next: number } {
  const clicks: DueClick[] = []
  let i = next
  while (i < beats.length && beats[i] < position + lookahead * rate) {
    const delay = (beats[i] - position) / rate
    if (delay > -0.01)
      clicks.push({ delay: Math.max(0, delay), accent: bars.has(timeKey(beats[i])) })
    i += 1
  }
  return { clicks, next: i }
}

/** Beats and bar starts are matched to the millisecond. */
export function timeKey(time: number): number {
  return Math.round(time * 1000)
}

let clickContext: AudioContext | null = null

function context(): AudioContext {
  clickContext ??= new AudioContext({ latencyHint: 'interactive' })
  return clickContext
}

function click(audio: AudioContext, at: number, accent: boolean, volume: number): void {
  const oscillator = audio.createOscillator()
  const gain = audio.createGain()
  oscillator.type = 'triangle'
  oscillator.frequency.value = accent ? 1760 : 1175
  const peak = (accent ? 0.9 : 0.5) * volume
  gain.gain.setValueAtTime(0, at)
  gain.gain.linearRampToValueAtTime(peak, at + 0.002)
  gain.gain.exponentialRampToValueAtTime(0.0005, at + CLICK_SECONDS)
  oscillator.connect(gain).connect(audio.destination)
  oscillator.start(at)
  oscillator.stop(at + CLICK_SECONDS + 0.01)
}

export interface ClickTrackOptions {
  enabled: boolean
  playing: boolean
  beats: readonly number[]
  bars: readonly number[]
  rate: number
  /** 0-1 */
  volume: number
  /** The song position being heard now (seconds). */
  position: () => number
}

/** Plays the click track while `enabled` and `playing`. */
export function useClickTrack(options: ClickTrackOptions): void {
  const { enabled, playing, beats, bars } = options
  const latest = useLatest(options)

  useEffect(() => {
    if (!enabled || !playing || beats.length === 0 || typeof AudioContext === 'undefined') return
    const audio = context()
    if (audio.state === 'suspended') void audio.resume()
    const barSet = new Set(bars.map(timeKey))
    let position = latest.current.position()
    let wall = performance.now()
    let next = firstBeatFrom(beats, position)
    const timer = window.setInterval(() => {
      const { position: now, rate, volume } = latest.current
      const current = now()
      const clock = performance.now()
      const expected = position + ((clock - wall) / 1000) * rate
      if (Math.abs(current - expected) > JUMP_TOLERANCE) next = firstBeatFrom(beats, current)
      position = current
      wall = clock
      const due = dueClicks(beats, barSet, next, current, rate)
      next = due.next
      for (const { delay, accent } of due.clicks) {
        click(audio, audio.currentTime + delay, accent, volume)
      }
    }, TICK_MS)
    return () => window.clearInterval(timer)
  }, [enabled, playing, beats, bars, latest])
}

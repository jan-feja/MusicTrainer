import { useEffect, useState } from 'react'
import { useLatest } from '../../lib/useLatest'

/** Practice time is reported in parts this long (and what is left when the page is left). */
export const REPORT_SECONDS = 30
const TICK_MS = 5000

/** Adds up the time the music plays; `take` hands out whole seconds not reported yet. */
export class PracticeCounter {
  private counted = 0
  private playingSince: number | null = null

  private readonly now: () => number

  constructor(now: () => number = () => performance.now()) {
    this.now = now
  }

  start(): void {
    this.playingSince ??= this.now()
  }

  stop(): void {
    this.tally()
    this.playingSince = null
  }

  /** The whole seconds counted, if at least `minimum`; they are then not counted again. */
  take(minimum: number): number | null {
    this.tally()
    const seconds = Math.floor(this.counted)
    if (seconds < Math.max(1, minimum)) return null
    this.counted -= seconds
    return seconds
  }

  private tally(): void {
    if (this.playingSince === null) return
    const now = this.now()
    this.counted += (now - this.playingSince) / 1000
    this.playingSince = now
  }
}

/**
 * Counts how long the music plays and reports it in parts, for the practice
 * history; the rest is reported when the player closes or the page is left.
 */
export function usePracticeTime(
  isPlaying: boolean,
  report: ((seconds: number, keepalive: boolean) => void) | undefined,
): void {
  const reportRef = useLatest(report)
  const [counter] = useState(() => new PracticeCounter())

  useEffect(() => {
    if (!isPlaying) return
    counter.start()
    const timer = window.setInterval(() => {
      const seconds = counter.take(REPORT_SECONDS)
      if (seconds !== null) reportRef.current?.(seconds, false)
    }, TICK_MS)
    return () => {
      window.clearInterval(timer)
      counter.stop()
    }
  }, [isPlaying, counter, reportRef])

  useEffect(() => {
    const leave = () => {
      const seconds = counter.take(1)
      if (seconds !== null) reportRef.current?.(seconds, true)
    }
    window.addEventListener('pagehide', leave)
    return () => {
      window.removeEventListener('pagehide', leave)
      leave()
    }
  }, [counter, reportRef])
}

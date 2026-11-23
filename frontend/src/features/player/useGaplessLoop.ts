import { type RefObject, useEffect, useRef } from 'react'
import { useLatest } from '../../lib/useLatest'
import { GaplessLoop } from './gaplessLoop'
import type { LoopRegion } from './loop'

/**
 * Plays the loop gapless (see gaplessLoop.ts) where the browser supports it.
 * The ref holds null until then and without an `audioUrl`.
 *
 * @param region the loop to play (shifted by any lead), or null when looping is off
 * @param expectedStart the loop start while its end is not set yet: its audio is fetched ahead
 */
export function useGaplessLoop(
  videoRef: RefObject<HTMLVideoElement | null>,
  audioUrl: string | undefined,
  region: LoopRegion | null,
  expectedStart: number | null,
  onAudioError?: (error: unknown) => void,
): RefObject<GaplessLoop | null> {
  const loopRef = useRef<GaplessLoop | null>(null)
  const regionRef = useLatest(region)
  const expectedStartRef = useLatest(expectedStart)
  const onAudioErrorRef = useLatest(onAudioError)

  useEffect(() => {
    const video = videoRef.current
    if (!video || !audioUrl || !GaplessLoop.isSupported()) return
    const loop = new GaplessLoop(video, audioUrl, (error) => onAudioErrorRef.current?.(error))
    loop.setRegion(regionRef.current)
    loop.expectLoopAt(expectedStartRef.current)
    loopRef.current = loop
    return () => {
      loopRef.current = null
      loop.dispose()
    }
  }, [videoRef, audioUrl, regionRef, expectedStartRef, onAudioErrorRef])

  const start = region?.start ?? null
  const end = region?.end ?? null
  useEffect(() => {
    loopRef.current?.setRegion(start !== null && end !== null ? { start, end } : null)
  }, [start, end])

  useEffect(() => {
    loopRef.current?.expectLoopAt(expectedStart)
  }, [expectedStart])

  return loopRef
}

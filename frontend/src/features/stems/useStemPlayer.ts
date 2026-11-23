import { type RefObject, useEffect, useRef } from 'react'
import { useLatest } from '../../lib/useLatest'
import type { LoopRegion } from '../player/loop'
import { StemPlayer } from './stemPlayer'
import type { StemTrack } from './stems'

/**
 * Plays the stems in place of the video's sound while `tracks` are given (see
 * stemPlayer.ts). The ref holds null otherwise, and where Web Audio is missing.
 *
 * @param gains gain per stem name (volume, mute, solo)
 * @param region the loop to play (shifted by any lead), or null when looping is off
 */
export function useStemPlayer(
  videoRef: RefObject<HTMLVideoElement | null>,
  tracks: StemTrack[] | null,
  gains: Record<string, number>,
  region: LoopRegion | null,
): RefObject<StemPlayer | null> {
  const playerRef = useRef<StemPlayer | null>(null)
  const gainsRef = useLatest(gains)
  const regionRef = useLatest(region)

  useEffect(() => {
    const video = videoRef.current
    if (!video || !tracks || !StemPlayer.isSupported()) return
    const player = new StemPlayer(video, tracks, gainsRef.current, regionRef.current)
    playerRef.current = player
    return () => {
      playerRef.current = null
      player.dispose()
    }
  }, [videoRef, tracks, gainsRef, regionRef])

  const gainsKey = JSON.stringify(gains)
  useEffect(() => {
    playerRef.current?.setGains(JSON.parse(gainsKey) as Record<string, number>)
  }, [gainsKey])

  const start = region?.start ?? null
  const end = region?.end ?? null
  useEffect(() => {
    playerRef.current?.setRegion(start !== null && end !== null ? { start, end } : null)
  }, [start, end])

  return playerRef
}

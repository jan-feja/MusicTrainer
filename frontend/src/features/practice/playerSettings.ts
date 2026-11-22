/**
 * Restoring the player as it was left for a video, and reporting its state to
 * be stored (player.json).
 */
import { type RefObject, useEffect, useRef, useState } from 'react'
import type { PlayerSettings, SavedLoop } from '../../api/types'
import { useLatest } from '../../lib/useLatest'
import { SNAP_LEAD_SECONDS } from '../beats/beatGrid'
import { EMPTY_LOOP, type LoopState, MIN_LOOP_LENGTH } from '../player/loop'
import { normalizePlaybackRate } from '../player/playbackRate'

/** While playing without a loop, the stored position moves in steps this long (fewer saves). */
export const POSITION_STEP_SECONDS = 5

/** The loop to start with: the active saved loop, else the loop that was set. */
export function initialLoopState(
  settings: PlayerSettings | null,
  activeLoop: SavedLoop | null,
): LoopState {
  if (activeLoop) {
    return { start: activeLoop.start, end: activeLoop.end, enabled: settings?.loopEnabled ?? true }
  }
  if (!settings) return EMPTY_LOOP
  const { loopStart: start, loopEnd: end } = settings
  if (start !== null && end !== null && end - start < MIN_LOOP_LENGTH) {
    return { start, end: null, enabled: false }
  }
  return { start, end, enabled: settings.loopEnabled && start !== null && end !== null }
}

/**
 * The position to store: the loop start while looping, else the playhead (in
 * coarse steps while playing, to the tenth of a second when paused).
 */
export function storedPosition(loop: LoopState, currentTime: number, playing: boolean): number {
  if (loop.enabled && loop.start !== null && loop.end !== null) return loop.start
  if (playing) return Math.floor(currentTime / POSITION_STEP_SECONDS) * POSITION_STEP_SECONDS
  return Math.round(currentTime * 10) / 10
}

interface Restore {
  volume: number
  muted: boolean
  playbackRate: number
  /** Where to start: the loop start (a little early when snapped), else the stored position. */
  position: number
}

/**
 * Once, when the video opens: volume, mute, speed and position as they were
 * left (speed and position need the video's metadata).
 */
export function useRestorePlayerSettings(
  videoRef: RefObject<HTMLVideoElement | null>,
  settings: PlayerSettings | null,
  activeLoop: SavedLoop | null,
  loop: LoopState,
): void {
  const [restore] = useState<Restore | null>(() => {
    if (!settings) return null
    const snapMode = activeLoop?.snapMode ?? settings.snapMode
    const lead = snapMode && snapMode !== 'off' ? SNAP_LEAD_SECONDS : 0
    const looping = loop.enabled && loop.start !== null && loop.end !== null
    return {
      volume: settings.volume,
      muted: settings.muted,
      playbackRate: normalizePlaybackRate(activeLoop?.playbackRate ?? settings.playbackRate),
      position: looping && loop.start !== null ? Math.max(0, loop.start - lead) : settings.position,
    }
  })

  useEffect(() => {
    const video = videoRef.current
    if (!video || !restore) return
    video.volume = restore.volume
    video.muted = restore.muted
    // loading a video resets its speed, so speed and position wait for the metadata
    const apply = () => {
      video.playbackRate = restore.playbackRate
      if (restore.position > 0 && restore.position < video.duration - 1) {
        video.currentTime = restore.position
      }
    }
    if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
      apply()
      return
    }
    video.addEventListener('loadedmetadata', apply, { once: true })
    return () => video.removeEventListener('loadedmetadata', apply)
  }, [videoRef, restore])
}

/**
 * Reports the player's state when it changes, once the video is ready (before
 * that the state is not restored yet). The first report is skipped when it
 * equals what was loaded.
 */
export function useReportPlayerSettings(
  settings: PlayerSettings,
  ready: boolean,
  initial: PlayerSettings | null,
  onChange?: (settings: PlayerSettings) => void,
): void {
  const key = JSON.stringify(settings)
  const reported = useRef(initial ? JSON.stringify(initial) : null)
  const onChangeRef = useLatest(onChange)
  useEffect(() => {
    if (!ready || key === reported.current) return
    reported.current = key
    onChangeRef.current?.(JSON.parse(key) as PlayerSettings)
  }, [key, ready, onChangeRef])
}

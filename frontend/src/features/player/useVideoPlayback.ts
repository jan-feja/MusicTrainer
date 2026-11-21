import { type RefObject, useEffect, useMemo, useState } from 'react'
import { clamp } from '../../lib/math'
import { useLatest } from '../../lib/useLatest'
import { normalizePlaybackRate, stepPlaybackRate } from './playbackRate'

export interface PlaybackState {
  currentTime: number
  duration: number
  isPlaying: boolean
  playbackRate: number
  volume: number
  isMuted: boolean
}

export interface PlaybackControls {
  togglePlay: () => void
  play: () => void
  seek: (time: number) => void
  seekBy: (seconds: number) => void
  setPlaybackRate: (rate: number) => void
  /** Faster (positive) or slower (negative) by `steps` steps of 0.05. */
  stepPlaybackRate: (steps: number) => void
  setVolume: (volume: number) => void
  toggleMute: () => void
  /** Exact position right now (the state above updates once per frame). */
  getCurrentTime: () => number
}

interface PlaybackOptions {
  /** Called on every animation frame while playing. */
  onFrame?: (video: HTMLVideoElement) => void
  onEnded?: (video: HTMLVideoElement) => void
}

const INITIAL_STATE: PlaybackState = {
  currentTime: 0,
  duration: 0,
  isPlaying: false,
  playbackRate: 1,
  volume: 1,
  isMuted: false,
}

const STATE_EVENTS = [
  'loadedmetadata',
  'durationchange',
  'timeupdate',
  'play',
  'pause',
  'ratechange',
  'volumechange',
  'seeked',
  'emptied',
] as const

/** Mirrors a <video> element's state into React and offers controls for it. */
export function useVideoPlayback(
  videoRef: RefObject<HTMLVideoElement | null>,
  { onFrame, onEnded }: PlaybackOptions = {},
): PlaybackState & PlaybackControls {
  const [state, setState] = useState(INITIAL_STATE)
  const onFrameRef = useLatest(onFrame)
  const onEndedRef = useLatest(onEnded)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    // keep the pitch when slowing down or speeding up (the browser default, made explicit)
    video.preservesPitch = true

    const readState = () =>
      setState({
        currentTime: video.currentTime,
        duration: Number.isFinite(video.duration) ? video.duration : 0,
        isPlaying: !video.paused && !video.ended,
        playbackRate: video.playbackRate,
        volume: video.volume,
        isMuted: video.muted,
      })

    // While playing, follow the playhead every frame: a smooth seek bar and
    // loop jumps within ~16 ms instead of the ~250 ms of 'timeupdate'.
    let frame = 0
    const onAnimationFrame = () => {
      onFrameRef.current?.(video)
      setState((s) =>
        s.currentTime === video.currentTime ? s : { ...s, currentTime: video.currentTime },
      )
      frame = requestAnimationFrame(onAnimationFrame)
    }
    const startFrames = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(onAnimationFrame)
    }
    const stopFrames = () => cancelAnimationFrame(frame)
    const handleEnded = () => {
      stopFrames()
      readState()
      onEndedRef.current?.(video)
    }

    STATE_EVENTS.forEach((name) => video.addEventListener(name, readState))
    video.addEventListener('playing', startFrames)
    video.addEventListener('pause', stopFrames)
    video.addEventListener('ended', handleEnded)
    readState()
    return () => {
      STATE_EVENTS.forEach((name) => video.removeEventListener(name, readState))
      video.removeEventListener('playing', startFrames)
      video.removeEventListener('pause', stopFrames)
      video.removeEventListener('ended', handleEnded)
      stopFrames()
    }
  }, [videoRef, onFrameRef, onEndedRef])

  const controls = useMemo<PlaybackControls>(() => {
    const withVideo = (action: (video: HTMLVideoElement) => void) => {
      if (videoRef.current) action(videoRef.current)
    }
    const play = (video: HTMLVideoElement) => {
      // play() rejects when interrupted by pause() or blocked by autoplay rules; nothing to do then
      video.play().catch(() => {})
    }
    return {
      play: () => withVideo(play),
      togglePlay: () =>
        withVideo((video) => (video.paused || video.ended ? play(video) : video.pause())),
      seek: (time) =>
        withVideo((video) => {
          video.currentTime = clamp(time, 0, video.duration || 0)
        }),
      seekBy: (seconds) =>
        withVideo((video) => {
          video.currentTime = clamp(video.currentTime + seconds, 0, video.duration || 0)
        }),
      setPlaybackRate: (rate) =>
        withVideo((video) => {
          video.playbackRate = normalizePlaybackRate(rate)
        }),
      // read the element, not React state: quick repeated presses must all count
      stepPlaybackRate: (steps) =>
        withVideo((video) => {
          video.playbackRate = stepPlaybackRate(video.playbackRate, steps)
        }),
      setVolume: (volume) =>
        withVideo((video) => {
          video.volume = clamp(volume, 0, 1)
          video.muted = volume === 0
        }),
      toggleMute: () =>
        withVideo((video) => {
          video.muted = !video.muted
        }),
      getCurrentTime: () => videoRef.current?.currentTime ?? 0,
    }
  }, [videoRef])

  return { ...state, ...controls }
}

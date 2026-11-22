import { type RefObject, useEffect, useRef, useState } from 'react'

/** Reloads in a row before giving up and showing the error. */
const MAX_RELOADS = 3
/** Failures further apart than this start the count again. */
const RELOAD_WINDOW_MS = 30_000
/** Each further reload starts this much later, past a frame that will not decode. */
const SKIP_SECONDS = 0.5

/**
 * Where to reload the video after a failure, or null to give up.
 * `failures`: when the earlier failures happened (ms), oldest first.
 */
export function reloadPosition(
  time: number,
  failures: readonly number[],
  now: number,
): number | null {
  const recent = failures.filter((at) => now - at < RELOAD_WINDOW_MS).length
  if (recent >= MAX_RELOADS) return null
  return time + recent * SKIP_SECONDS
}

/** Load the video's source again and carry on at `time`, at the same speed. */
function reloadAt(video: HTMLVideoElement, time: number, play: boolean): void {
  const rate = video.playbackRate
  video.addEventListener(
    'loadedmetadata',
    () => {
      video.currentTime = Math.min(time, Number.isFinite(video.duration) ? video.duration : time)
      video.playbackRate = rate
      if (play) video.play().catch(() => {})
    },
    { once: true },
  )
  video.load()
}

export interface VideoRecovery {
  /** Set when the video failed and reloading did not help. */
  error: string | null
  /** Try again after `error`. */
  reload: () => void
}

/**
 * Browsers sometimes fail to decode a frame of a file that plays fine
 * otherwise, and the video then stops for good. This reloads it where it was
 * (a little further on each time); after a few failures it gives up.
 */
export function useVideoRecovery(
  videoRef: RefObject<HTMLVideoElement | null>,
  src: string,
): VideoRecovery {
  // kept with its source: another video starts without it
  const [failed, setFailed] = useState<{ src: string; message: string } | null>(null)
  const failures = useRef<number[]>([])
  const lastTime = useRef(0)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    failures.current = []
    lastTime.current = 0
    const setError = (message: string) => setFailed({ src, message })
    const onTimeUpdate = () => {
      if (!video.error) lastTime.current = video.currentTime
    }
    const onError = () => {
      const { error: mediaError } = video
      if (!mediaError || mediaError.code === MediaError.MEDIA_ERR_ABORTED) return
      const message = mediaError.message || 'The video could not be played'
      if (mediaError.code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) {
        setError(message)
        return
      }
      const now = performance.now()
      const time = Math.max(video.currentTime, lastTime.current)
      const position = reloadPosition(time, failures.current, now)
      console.warn('Video failed, reloading:', message)
      if (position === null) {
        setError(message)
        return
      }
      failures.current = [...failures.current, now]
      reloadAt(video, position, !video.paused)
    }
    video.addEventListener('timeupdate', onTimeUpdate)
    video.addEventListener('error', onError)
    return () => {
      video.removeEventListener('timeupdate', onTimeUpdate)
      video.removeEventListener('error', onError)
    }
  }, [videoRef, src])

  const reload = () => {
    const video = videoRef.current
    if (!video) return
    failures.current = []
    setFailed(null)
    reloadAt(video, lastTime.current, true)
  }
  return { error: failed?.src === src ? failed.message : null, reload }
}

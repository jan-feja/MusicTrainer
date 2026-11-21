import { useReducer, useRef } from 'react'
import { ExitFullscreenIcon, FullscreenIcon, PauseIcon, PlayIcon } from '../../components/icons'
import { formatTime } from '../../lib/format'
import { useLatest } from '../../lib/useLatest'
import { LoopControls } from './LoopControls'
import { EMPTY_LOOP, getLoopRegion, loopJumpTarget, loopReducer } from './loop'
import { SeekBar } from './SeekBar'
import { ShortcutHelp } from './ShortcutHelp'
import { SpeedControl } from './SpeedControl'
import { useFullscreen } from './useFullscreen'
import { usePlayerShortcuts } from './usePlayerShortcuts'
import { useVideoPlayback } from './useVideoPlayback'
import { VolumeControl } from './VolumeControl'
import controlStyles from './PlayerControls.module.css'
import styles from './VideoPlayer.module.css'

const SEEK_STEP_SECONDS = 5

interface VideoPlayerProps {
  src: string
  poster?: string
  autoPlay?: boolean
}

/**
 * Video player with speed control and an A–B loop. Give it a `key` per video
 * so the loop resets when the video changes.
 */
export function VideoPlayer({ src, poster, autoPlay = true }: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [loop, dispatchLoop] = useReducer(loopReducer, EMPTY_LOOP)
  const loopRef = useLatest(loop)

  const playback = useVideoPlayback(videoRef, {
    onFrame: (video) => {
      const target = loopJumpTarget(loopRef.current, video.currentTime)
      if (target !== null) video.currentTime = target
    },
    // a loop that ends at the very end of the video: start over instead of stopping
    onEnded: (video) => {
      const region = getLoopRegion(loopRef.current)
      if (loopRef.current.enabled && region) {
        video.currentTime = region.start
        video.play().catch(() => {})
      }
    },
  })
  const { isFullscreen, toggleFullscreen } = useFullscreen(containerRef)

  const moveLoopPoint = (type: 'setStart' | 'setEnd' | 'moveStart' | 'moveEnd', time: number) =>
    dispatchLoop({ type, time, duration: playback.duration })
  const setLoopStartHere = () => moveLoopPoint('setStart', playback.getCurrentTime())
  const setLoopEndHere = () => moveLoopPoint('setEnd', playback.getCurrentTime())
  const moveLoopStart = (time: number) => moveLoopPoint('moveStart', time)
  const moveLoopEnd = (time: number) => moveLoopPoint('moveEnd', time)
  const toggleLoop = () => dispatchLoop({ type: 'toggle' })
  const clearLoop = () => dispatchLoop({ type: 'clear' })

  usePlayerShortcuts({
    togglePlay: playback.togglePlay,
    seekBackward: () => playback.seekBy(-SEEK_STEP_SECONDS),
    seekForward: () => playback.seekBy(SEEK_STEP_SECONDS),
    slower: () => playback.stepPlaybackRate(-1),
    faster: () => playback.stepPlaybackRate(1),
    setLoopStart: setLoopStartHere,
    setLoopEnd: setLoopEndHere,
    toggleLoop,
    clearLoop,
    jumpToLoopStart: () => playback.seek(loop.start ?? 0),
    toggleMute: playback.toggleMute,
    toggleFullscreen,
  })

  return (
    <div>
      <div ref={containerRef} className={styles.player} data-fullscreen={isFullscreen}>
        <video
          ref={videoRef}
          className={styles.video}
          src={src}
          poster={poster}
          autoPlay={autoPlay}
          playsInline
          preload="auto"
          onClick={playback.togglePlay}
          onDoubleClick={toggleFullscreen}
        />
        <div className={controlStyles.controls}>
          <SeekBar
            currentTime={playback.currentTime}
            duration={playback.duration}
            loop={loop}
            onSeek={playback.seek}
            onMoveLoopStart={moveLoopStart}
            onMoveLoopEnd={moveLoopEnd}
          />
          <div className={controlStyles.row}>
            <button
              type="button"
              className="icon-button icon-button-large"
              onClick={playback.togglePlay}
              aria-label={playback.isPlaying ? 'Pause' : 'Play'}
              title={playback.isPlaying ? 'Pause (Space)' : 'Play (Space)'}
            >
              {playback.isPlaying ? <PauseIcon /> : <PlayIcon />}
            </button>
            <VolumeControl
              volume={playback.volume}
              isMuted={playback.isMuted}
              onVolumeChange={playback.setVolume}
              onToggleMute={playback.toggleMute}
            />
            <span className={controlStyles.time}>
              {formatTime(playback.currentTime)} / {formatTime(playback.duration)}
            </span>
            <span className={controlStyles.spacer} />
            <SpeedControl
              rate={playback.playbackRate}
              onChange={playback.setPlaybackRate}
              onStep={playback.stepPlaybackRate}
            />
            <button
              type="button"
              className="icon-button"
              onClick={toggleFullscreen}
              aria-label={isFullscreen ? 'Exit full screen' : 'Full screen'}
              title={isFullscreen ? 'Exit full screen (F)' : 'Full screen (F)'}
            >
              {isFullscreen ? <ExitFullscreenIcon /> : <FullscreenIcon />}
            </button>
          </div>
          <div className={controlStyles.row}>
            <LoopControls
              loop={loop}
              onSetStart={setLoopStartHere}
              onSetEnd={setLoopEndHere}
              onMoveStart={moveLoopStart}
              onMoveEnd={moveLoopEnd}
              onToggle={toggleLoop}
              onClear={clearLoop}
            />
          </div>
        </div>
      </div>
      <ShortcutHelp />
    </div>
  )
}

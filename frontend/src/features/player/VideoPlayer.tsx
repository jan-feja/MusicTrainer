import { useMemo, useReducer, useRef, useState } from 'react'
import { ExitFullscreenIcon, FullscreenIcon, PauseIcon, PlayIcon } from '../../components/icons'
import { formatTime } from '../../lib/format'
import { useLatest } from '../../lib/useLatest'
import { BeatSnapControls } from '../beats/BeatSnapControls'
import { BeatTicks } from '../beats/BeatTicks'
import {
  type GridUnit,
  SNAP_LEAD_SECONDS,
  type SnapMode,
  createBeatGrid,
  shiftedBarStarts,
  describeGridLength,
  gridPoints,
  nextSnapMode,
  snapRegion,
  snapToGrid,
  stepOnGrid,
  stepsBetween,
} from '../beats/beatGrid'
import type { BeatTracking } from '../beats/useBeatTracking'
import { useSnapMode } from '../beats/useSnapMode'
import { LoopControls } from './LoopControls'
import { EMPTY_LOOP, LOOP_NUDGE_SECONDS, getLoopRegion, loopJumpTarget, loopReducer } from './loop'
import { SeekBar } from './SeekBar'
import { ShortcutHelp } from './ShortcutHelp'
import { SpeedControl } from './SpeedControl'
import { useFullscreen } from './useFullscreen'
import { usePlayerShortcuts } from './usePlayerShortcuts'
import { useGaplessLoop } from './useGaplessLoop'
import { useVideoPlayback } from './useVideoPlayback'
import { VolumeControl } from './VolumeControl'
import controlStyles from './PlayerControls.module.css'
import styles from './VideoPlayer.module.css'

const SEEK_STEP_SECONDS = 5
/** Shift + arrow on a loop handle, without snapping. */
const COARSE_NUDGE_SECONDS = 1
/** Shift + arrow on a loop handle, with snapping. */
const COARSE_GRID_STEPS = 4
/** Beat marks are drawn only up to this many beats; more would merge into a solid bar. */
const MAX_BEAT_MARKS = 600

type LoopPoint = 'start' | 'end'

interface VideoPlayerProps {
  src: string
  /** Sections of the audio as WAV (`?start=&end=`); lets the loop play without a gap. */
  audioUrl?: string
  poster?: string
  autoPlay?: boolean
  /** Beat grid of the video; lets the loop snap to beats and bars. */
  beatTracking?: BeatTracking
}

/**
 * Video player with speed control and an A–B loop that can snap to the beat
 * grid. Give it a `key` per video so the loop resets when the video changes.
 */
export function VideoPlayer({
  src,
  audioUrl,
  poster,
  autoPlay = true,
  beatTracking,
}: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [loop, dispatchLoop] = useReducer(loopReducer, EMPTY_LOOP)
  const [snapMode, setSnapMode] = useSnapMode()

  const analysis = beatTracking?.analysis ?? null
  const grid = useMemo(
    () => (analysis && analysis.beats.length >= 2 ? createBeatGrid(analysis) : null),
    [analysis],
  )
  const snapUnit: GridUnit | null = grid && snapMode !== 'off' ? snapMode : null
  const snapPoints = grid && snapUnit ? gridPoints(grid, snapUnit) : null
  // a loop snapped to the grid plays slightly early so the first note keeps its attack
  const lead = snapPoints ? SNAP_LEAD_SECONDS : 0
  const loopRef = useLatest(loop)
  const leadRef = useLatest(lead)

  const region = getLoopRegion(loop)
  const playedRegion =
    loop.enabled && region
      ? { start: Math.max(0, region.start - lead), end: region.end - lead }
      : null
  const expectedStart = loop.start !== null && loop.end === null ? loop.start - lead : null
  const gaplessLoop = useGaplessLoop(videoRef, audioUrl, playedRegion, expectedStart)

  const playback = useVideoPlayback(videoRef, {
    onFrame: (video) => {
      if (gaplessLoop.current?.tick()) return
      const target = loopJumpTarget(loopRef.current, video.currentTime, leadRef.current)
      if (target !== null) video.currentTime = target
    },
    // a loop that ends at the very end of the video: start over instead of stopping
    onEnded: (video) => {
      const region = getLoopRegion(loopRef.current)
      if (loopRef.current.enabled && region && !gaplessLoop.current?.active) {
        video.currentTime = Math.max(0, region.start - leadRef.current)
        video.play().catch(() => {})
      }
    },
    clock: () => gaplessLoop.current?.position() ?? null,
  })
  const { isFullscreen, toggleFullscreen } = useFullscreen(containerRef)
  const duration = playback.duration

  const snap = (time: number) => (snapPoints ? snapToGrid(snapPoints, time) : time)
  const setLoopPoint = (type: 'setStart' | 'setEnd' | 'moveStart' | 'moveEnd', time: number) =>
    dispatchLoop({ type, time, duration })
  const setLoopStartHere = () => setLoopPoint('setStart', snap(playback.getCurrentTime()))
  const setLoopEndHere = () => setLoopPoint('setEnd', snap(playback.getCurrentTime()))

  // with snapping, a dragged point jumps from grid point to grid point and never crosses the other
  const moveLoopStart = (time: number) => {
    const target = snap(time)
    if (snapPoints && loop.end !== null && target >= loop.end) return
    setLoopPoint('moveStart', target)
  }
  const moveLoopEnd = (time: number) => {
    const target = snap(time)
    if (snapPoints && loop.start !== null && target <= loop.start) return
    setLoopPoint('moveEnd', target)
  }

  /** One step earlier or later: a beat or bar when snapping, otherwise 50 ms (1 s coarse). */
  const nudgeLoopPoint = (point: LoopPoint, direction: -1 | 1, coarse = false) => {
    const time = point === 'start' ? loop.start : loop.end
    if (time === null) return
    const target = snapPoints
      ? stepOnGrid(snapPoints, time, direction * (coarse ? COARSE_GRID_STEPS : 1))
      : time + direction * (coarse ? COARSE_NUDGE_SECONDS : LOOP_NUDGE_SECONDS)
    if (point === 'start') moveLoopStart(target)
    else moveLoopEnd(target)
  }

  const snapLoopTo = (points: readonly number[]) => {
    const region = getLoopRegion(loop)
    if (region) {
      const snapped = snapRegion(points, region.start, region.end)
      if (snapped) dispatchLoop({ type: 'setRegion', ...snapped, duration })
    } else if (loop.start !== null) {
      setLoopPoint('moveStart', snapToGrid(points, loop.start))
    } else if (loop.end !== null) {
      setLoopPoint('moveEnd', snapToGrid(points, loop.end))
    }
  }

  const changeSnapMode = (mode: SnapMode) => {
    setSnapMode(mode)
    if (grid && mode !== 'off') snapLoopTo(gridPoints(grid, mode))
  }

  const cycleSnapMode = () => {
    if (!grid) return
    let next = nextSnapMode(snapMode)
    if (next === 'bar' && grid.bars.length < 2) next = nextSnapMode(next)
    changeSnapMode(next)
  }

  // a new grid (new hints, moved bar starts): keep a snapped loop on it
  const [previousGrid, setPreviousGrid] = useState(grid)
  if (grid !== previousGrid) {
    setPreviousGrid(grid)
    if (previousGrid && grid && snapUnit) snapLoopTo(gridPoints(grid, snapUnit))
  }

  const moveBarStarts = (delta: -1 | 1) => {
    if (!analysis || !beatTracking) return
    const barStarts = shiftedBarStarts(analysis, playback.getCurrentTime(), delta)
    beatTracking.setHints({ ...analysis.hints, barStarts })
  }

  const resetBarStarts = () => {
    if (analysis && beatTracking) beatTracking.setHints({ ...analysis.hints, barStarts: [] })
  }

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
    cycleSnapMode,
    jumpToLoopStart: () => playback.seek(Math.max(0, (loop.start ?? 0) - lead)),
    toggleMute: playback.toggleMute,
    toggleFullscreen,
  })

  let lengthLabel: string | null = null
  if (region && snapPoints && snapUnit) {
    const steps = stepsBetween(snapPoints, region.start, region.end)
    lengthLabel = describeGridLength(steps, snapUnit, grid?.beatsPerBar ?? null)
  } else if (region) {
    lengthLabel = `${(region.end - region.start).toFixed(1)} s`
  }
  const stepLabel = snapUnit ? `1 ${snapUnit}` : `${LOOP_NUDGE_SECONDS * 1000} ms`
  const showBeatMarks = snapUnit === 'beat' && grid !== null && grid.beats.length <= MAX_BEAT_MARKS

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
            duration={duration}
            loop={loop}
            onSeek={playback.seek}
            onMoveLoopStart={moveLoopStart}
            onMoveLoopEnd={moveLoopEnd}
            onNudgeLoopStart={(direction, coarse) => nudgeLoopPoint('start', direction, coarse)}
            onNudgeLoopEnd={(direction, coarse) => nudgeLoopPoint('end', direction, coarse)}
            markers={
              grid && (
                <BeatTicks
                  duration={duration}
                  bars={grid.bars}
                  beats={showBeatMarks ? grid.beats : undefined}
                />
              )
            }
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
              {formatTime(playback.currentTime)} / {formatTime(duration)}
            </span>
            <span className={controlStyles.spacer} />
            <SpeedControl
              rate={playback.playbackRate}
              onChange={playback.setPlaybackRate}
              onStep={playback.stepPlaybackRate}
              bpm={grid?.bpm}
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
              onNudgeStart={(direction) => nudgeLoopPoint('start', direction)}
              onNudgeEnd={(direction) => nudgeLoopPoint('end', direction)}
              onToggle={toggleLoop}
              onClear={clearLoop}
              stepLabel={stepLabel}
              lengthLabel={lengthLabel}
            />
          </div>
          {beatTracking && (
            <div className={controlStyles.row}>
              <BeatSnapControls
                tracking={beatTracking}
                snapMode={snapMode}
                onSnapModeChange={changeSnapMode}
                onMoveBarStarts={moveBarStarts}
                onResetBarStarts={resetBarStarts}
              />
            </div>
          )}
        </div>
      </div>
      <ShortcutHelp />
    </div>
  )
}

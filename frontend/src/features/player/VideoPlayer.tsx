import { useEffect, useMemo, useReducer, useRef, useState } from 'react'
import type { MixerSettings, PlayerSettings, SavedLoop } from '../../api/types'
import { ExitFullscreenIcon, FullscreenIcon, PauseIcon, PlayIcon } from '../../components/icons'
import { formatTime } from '../../lib/format'
import { useLatest } from '../../lib/useLatest'
import { BeatSnapControls } from '../beats/BeatSnapControls'
import { BeatTicks } from '../beats/BeatTicks'
import { useChords } from '../chords/useChords'
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
import { MetronomeControls } from '../metronome/MetronomeControls'
import { useMetronome } from '../metronome/useMetronome'
import {
  initialLoopState,
  storedPosition,
  useReportPlayerSettings,
  useRestorePlayerSettings,
} from '../practice/playerSettings'
import { SavedLoopMarks } from '../practice/SavedLoopMarks'
import {
  mixerGains,
  withLevel,
  withMuteSwitched,
  withSoloToggled,
  withStemsEnabled,
} from '../stems/mixer'
import { StemsControls } from '../stems/StemsControls'
import { TrackLanes } from '../stems/TrackLanes'
import { useStemPlayer } from '../stems/useStemPlayer'
import { useStems } from '../stems/useStems'
import { SavedLoops } from '../practice/SavedLoops'
import { createLoop, describeLoop } from '../practice/loopList'
import { useSavedLoops } from '../practice/useSavedLoops'
import { LoopControls } from './LoopControls'
import { LOOP_NUDGE_SECONDS, getLoopRegion, loopJumpTarget, loopReducer } from './loop'
import { normalizePlaybackRate, stepPlaybackRate } from './playbackRate'
import { SeekBar } from './SeekBar'
import { ShortcutHelp } from './ShortcutHelp'
import { SpeedControl } from './SpeedControl'
import { TimelineOverview } from './TimelineOverview'
import { followPlayhead, visibleRange } from './timelineView'
import { useFullscreen } from './useFullscreen'
import { useVideoRecovery } from './useVideoRecovery'
import { usePlayerShortcuts } from './usePlayerShortcuts'
import { useGaplessLoop } from './useGaplessLoop'
import { useTimelineZoom } from './useTimelineZoom'
import { useVideoPlayback } from './useVideoPlayback'
import { VolumeControl } from './VolumeControl'
import { ZoomControls } from './ZoomControls'
import controlStyles from './PlayerControls.module.css'
import styles from './VideoPlayer.module.css'

const SEEK_STEP_SECONDS = 5
/** Shift + arrow on a loop handle, without snapping. */
const COARSE_NUDGE_SECONDS = 1
/** Shift + arrow on a loop handle, with snapping. */
const COARSE_GRID_STEPS = 4
/** Beat marks are drawn up to this many in view when snapping to beats; more would merge. */
const MAX_BEAT_MARKS = 600
/** Otherwise beat marks appear once this few are in view (zoomed in). */
const MAX_HELPER_BEAT_MARKS = 120
/** Bars are numbered once this few are in view. */
const MAX_BAR_NUMBERS = 40
/** Z without a loop zooms this far in around the playhead. */
const PLAIN_ZOOM_FACTOR = 8
const NO_LOOPS: SavedLoop[] = []

type LoopPoint = 'start' | 'end'

/** A video's saved loops and player settings, and where to report changes to store them. */
export interface PlayerPractice {
  loops: SavedLoop[]
  settings: PlayerSettings
  onLoopsChange: (loops: SavedLoop[]) => void
  onSettingsChange: (settings: PlayerSettings) => void
  /** The last save failed with this message. */
  saveError: string | null
}

interface VideoPlayerProps {
  /** The library video; offers its stems (instruments separated on the server). */
  videoId?: string
  src: string
  /** Sections of the audio as WAV (`?start=&end=`); lets the loop play without a gap. */
  audioUrl?: string
  poster?: string
  autoPlay?: boolean
  /** Beat grid of the video; lets the loop snap to beats and bars. */
  beatTracking?: BeatTracking
  /** Saved loops and settings; without them nothing is restored or stored. */
  practice?: PlayerPractice
}

/**
 * Video player with speed control, a zoomable timeline and an A–B loop that
 * can snap to the beat grid and be saved. Give it a `key` per video so its
 * state starts over when the video changes.
 */
export function VideoPlayer({
  videoId,
  src,
  audioUrl,
  poster,
  autoPlay = true,
  beatTracking,
  practice,
}: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const initialSettings = practice?.settings ?? null
  const saved = useSavedLoops(
    practice?.loops ?? NO_LOOPS,
    initialSettings?.activeLoopId ?? null,
    practice?.onLoopsChange,
  )
  const [loop, dispatchLoop] = useReducer(loopReducer, null, () =>
    initialLoopState(initialSettings, saved.active),
  )
  const [snapMode, setSnapMode] = useSnapMode(
    saved.active?.snapMode ?? initialSettings?.snapMode ?? null,
  )
  useRestorePlayerSettings(videoRef, initialSettings, saved.active, loop)

  const [mixer, setMixer] = useState<MixerSettings | null>(initialSettings?.mixer ?? null)
  const stemsEnabled = mixer?.enabled ?? false
  const stems = useStems(videoId, stemsEnabled)
  const stemTracks = stems.status.kind === 'ready' ? stems.status.tracks : null
  const visibleStemTracks = useMemo(
    () => stemTracks?.filter((track) => !track.quiet) ?? [],
    [stemTracks],
  )
  const stemGains = useMemo(
    () => mixerGains(stemTracks?.map((track) => track.name) ?? [], mixer),
    [stemTracks, mixer],
  )

  const analysis = beatTracking?.analysis ?? null
  const grid = useMemo(
    () => (analysis && analysis.beats.length >= 2 ? createBeatGrid(analysis) : null),
    [analysis],
  )
  // the chord lane is part of the stem lanes, and its chords come from the pitched stems
  const chords = useChords(videoId ?? '', analysis, stemTracks !== null)
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
  // the stems play loops gapless themselves
  const stemPlayer = useStemPlayer(videoRef, stemTracks, stemGains, playedRegion)
  const gaplessLoop = useGaplessLoop(
    videoRef,
    stemTracks ? undefined : audioUrl,
    playedRegion,
    expectedStart,
  )

  const playback = useVideoPlayback(videoRef, {
    onFrame: (video) => {
      if (stemPlayer.current?.tick()) return
      if (gaplessLoop.current?.tick()) return
      const target = loopJumpTarget(loopRef.current, video.currentTime, leadRef.current)
      if (target !== null) video.currentTime = target
    },
    // a loop that ends at the very end of the video: start over instead of stopping
    onEnded: (video) => {
      const region = getLoopRegion(loopRef.current)
      const playedElsewhere = gaplessLoop.current?.active || stemPlayer.current?.active
      if (loopRef.current.enabled && region && !playedElsewhere) {
        video.currentTime = Math.max(0, region.start - leadRef.current)
        video.play().catch(() => {})
      }
    },
    clock: () => stemPlayer.current?.position() ?? gaplessLoop.current?.position() ?? null,
  })
  // while the gapless loop or the stems play the sound, they also move the muted video
  const videoFollowsOtherSound = () =>
    Boolean(gaplessLoop.current?.active || stemPlayer.current?.active)
  const metronome = useMetronome(
    videoRef,
    grid,
    playedRegion,
    playback.getCurrentTime,
    videoFollowsOtherSound,
  )
  const { isFullscreen, toggleFullscreen } = useFullscreen(containerRef)
  const recovery = useVideoRecovery(videoRef, src)
  const duration = playback.duration
  const zoom = useTimelineZoom(duration)

  useReportPlayerSettings(
    {
      volume: playback.volume,
      muted: playback.isMuted,
      playbackRate: playback.playbackRate,
      snapMode,
      position: storedPosition(loop, playback.currentTime, playback.isPlaying),
      loopStart: loop.start,
      loopEnd: loop.end,
      loopEnabled: loop.enabled,
      activeLoopId: saved.activeId,
      mixer,
    },
    duration > 0,
    initialSettings,
    practice?.onSettingsChange,
  )

  // edits of the active saved loop go into it; a loop without both points lets go of it
  const { activeId, update: updateSaved, setActiveId } = saved
  useEffect(() => {
    if (activeId === null) return
    if (loop.start === null || loop.end === null) setActiveId(null)
    else updateSaved(activeId, { start: loop.start, end: loop.end })
  }, [loop.start, loop.end, activeId, updateSaved, setActiveId])

  // the loop that was open last time fills the timeline once the duration is known
  const [fittedAtStart, setFittedAtStart] = useState(false)
  if (!fittedAtStart && duration > 0) {
    setFittedAtStart(true)
    if (region) zoom.fit(region)
  }

  // a zoomed view moves on with the playhead
  const previousTime = useRef(playback.currentTime)
  useEffect(() => {
    const previous = previousTime.current
    previousTime.current = playback.currentTime
    if (!playback.isPlaying || !zoom.zoomed) return
    const next = followPlayhead(zoom.view, previous, playback.currentTime, duration)
    if (next) zoom.setView(next)
  }, [playback.currentTime, playback.isPlaying, zoom, duration])

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
    if (activeId) updateSaved(activeId, { snapMode: mode })
    if (grid && mode !== 'off') snapLoopTo(gridPoints(grid, mode))
  }

  const cycleSnapMode = () => {
    if (!grid) return
    let next = nextSnapMode(snapMode)
    if (next === 'bar' && grid.bars.length < 2) next = nextSnapMode(next)
    changeSnapMode(next)
  }

  // the speed of the active saved loop is kept with it
  const changeRate = (rate: number) => {
    const next = normalizePlaybackRate(rate)
    playback.setPlaybackRate(next)
    if (activeId) updateSaved(activeId, { playbackRate: next })
  }
  const stepRate = (steps: number) =>
    changeRate(stepPlaybackRate(videoRef.current?.playbackRate ?? playback.playbackRate, steps))

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

  /** Load a saved loop with its snap and speed, go to its start and zoom to it. */
  const selectLoop = (id: string) => {
    const chosen = saved.loops.find((candidate) => candidate.id === id)
    if (!chosen) return
    setActiveId(id)
    setSnapMode(chosen.snapMode)
    dispatchLoop({ type: 'load', start: chosen.start, end: chosen.end, duration })
    playback.setPlaybackRate(chosen.playbackRate)
    const chosenLead = grid && chosen.snapMode !== 'off' ? SNAP_LEAD_SECONDS : 0
    playback.seek(Math.max(0, chosen.start - chosenLead))
    zoom.fit(chosen)
  }
  const canSaveLoop = practice !== undefined && region !== null && activeId === null
  const saveLoop = () => {
    if (!canSaveLoop || !region) return
    saved.add(createLoop(saved.loops, region, snapMode, playback.playbackRate))
  }
  const deleteLoop = (id: string) => {
    const doomed = saved.loops.find((candidate) => candidate.id === id)
    if (doomed && window.confirm(`Delete the saved loop “${doomed.name}”?`)) saved.remove(id)
  }
  const toggleZoom = () => {
    if (zoom.zoomed) zoom.reset()
    else if (region) zoom.fit(region)
    else zoom.zoomBy(1 / PLAIN_ZOOM_FACTOR, playback.getCurrentTime())
  }

  usePlayerShortcuts({
    togglePlay: playback.togglePlay,
    seekBackward: () => playback.seekBy(-SEEK_STEP_SECONDS),
    seekForward: () => playback.seekBy(SEEK_STEP_SECONDS),
    slower: () => stepRate(-1),
    faster: () => stepRate(1),
    setLoopStart: setLoopStartHere,
    setLoopEnd: setLoopEndHere,
    toggleLoop,
    clearLoop,
    saveLoop,
    selectSavedLoop: (key) => {
      const chosen = saved.loops[Number(key) - 1]
      if (chosen) selectLoop(chosen.id)
    },
    toggleZoom,
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

  const view = zoom.view
  const [firstBeat, lastBeat] = grid ? visibleRange(grid.beats, view) : [0, 0]
  const [firstBar, lastBar] = grid ? visibleRange(grid.bars, view) : [0, 0]
  const beatsInView = lastBeat - firstBeat
  const showBeatMarks =
    snapUnit === 'beat' ? beatsInView <= MAX_BEAT_MARKS : beatsInView <= MAX_HELPER_BEAT_MARKS

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
        {recovery.error && (
          <div className={styles.videoError} role="alert">
            <span>Video could not be played: {recovery.error}</span>
            <button type="button" className="button button-small" onClick={recovery.reload}>
              Reload video
            </button>
          </div>
        )}
        <div className={controlStyles.controls}>
          <SeekBar
            currentTime={playback.currentTime}
            duration={duration}
            view={view}
            loop={loop}
            onSeek={playback.seek}
            onMoveLoopStart={moveLoopStart}
            onMoveLoopEnd={moveLoopEnd}
            onNudgeLoopStart={(direction, coarse) => nudgeLoopPoint('start', direction, coarse)}
            onNudgeLoopEnd={(direction, coarse) => nudgeLoopPoint('end', direction, coarse)}
            onZoom={zoom.zoomBy}
            onPan={zoom.pan}
            markers={
              <>
                {grid && (
                  <BeatTicks
                    view={view}
                    bars={grid.bars}
                    beats={showBeatMarks ? grid.beats : undefined}
                    barNumbers={lastBar - firstBar <= MAX_BAR_NUMBERS}
                  />
                )}
                <SavedLoopMarks view={view} loops={saved.loops} activeId={activeId} />
              </>
            }
          />
          {/* the space stays when not zoomed, so the controls below never jump */}
          <div className={controlStyles.overviewSlot}>
            {zoom.zoomed && (
              <TimelineOverview
                duration={duration}
                view={view}
                currentTime={playback.currentTime}
                loop={loop}
                savedLoops={saved.loops}
                onViewChange={zoom.setView}
              />
            )}
          </div>
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
              onChange={changeRate}
              onStep={stepRate}
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
            <ZoomControls zoom={zoom} region={region} />
          </div>
          <div className={controlStyles.row}>
            <MetronomeControls
              available={grid !== null}
              enabled={metronome.enabled}
              starting={metronome.starting}
              volume={metronome.volume}
              error={metronome.error}
              onToggle={metronome.toggle}
              onVolumeChange={metronome.setVolume}
            />
          </div>
          {practice && (
            <div className={controlStyles.row}>
              <SavedLoops
                loops={saved.loops}
                activeId={activeId}
                canSave={canSaveLoop}
                describe={(candidate) => describeLoop(candidate, grid)}
                onSelect={selectLoop}
                onSave={saveLoop}
                onNew={clearLoop}
                onRename={(id, name) => updateSaved(id, { name })}
                onDelete={deleteLoop}
                saveError={practice.saveError}
              />
            </div>
          )}
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
          {videoId && (
            <div className={controlStyles.row}>
              <StemsControls
                stems={stems}
                enabled={stemsEnabled}
                onToggle={() => setMixer((current) => withStemsEnabled(current, !stemsEnabled))}
              />
            </div>
          )}
          {stemTracks && (
            <TrackLanes
              // stems hardly in the song are not shown (they still play, as part of the mix)
              tracks={visibleStemTracks}
              chords={analysis ? chords : undefined}
              mixer={mixer}
              gains={stemGains}
              duration={duration}
              currentTime={playback.currentTime}
              view={view}
              loop={loop}
              bars={grid?.bars}
              beats={showBeatMarks ? grid?.beats : undefined}
              onSeek={playback.seek}
              onZoom={zoom.zoomBy}
              onPan={zoom.pan}
              onToggleMute={(name) => setMixer((current) => withMuteSwitched(current, name))}
              onToggleSolo={(name) => setMixer((current) => withSoloToggled(current, name))}
              onLevelChange={(name, level) =>
                setMixer((current) => withLevel(current, name, level))
              }
            />
          )}
        </div>
      </div>
      <ShortcutHelp />
    </div>
  )
}

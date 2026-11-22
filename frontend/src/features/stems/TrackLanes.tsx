import { useRef } from 'react'
import type { MixerSettings } from '../../api/types'
import { clamp } from '../../lib/math'
import { BeatTicks } from '../beats/BeatTicks'
import { type LoopState, getLoopRegion } from '../player/loop'
import { useWheelZoom } from '../player/useWheelZoom'
import type { TimeView } from '../player/timelineView'
import { usePointerDrag } from '../player/usePointerDrag'
import { stemLevel } from './mixer'
import type { StemTrack } from './stems'
import { StemWaveform } from './StemWaveform'
import styles from './TrackLanes.module.css'

/** Waveform colours per instrument; others get the last one. */
const STEM_COLORS: Record<string, string> = {
  drums: '#fb923c',
  bass: '#4ade80',
  vocals: '#f472b6',
  guitar: '#60a5fa',
  piano: '#c084fc',
  other: '#94a3b8',
}

export interface TrackLanesProps {
  /** The stems to show (not the ones hardly in the song). */
  tracks: StemTrack[]
  mixer: MixerSettings | null
  /** What each stem is heard at (after mute and solo). */
  gains: Record<string, number>
  duration: number
  currentTime: number
  /** The part of the song shown: the same as the timeline above. */
  view: TimeView
  loop: LoopState
  /** Bar and beat marks drawn across the lanes. */
  bars?: readonly number[]
  beats?: readonly number[]
  onSeek: (time: number) => void
  onZoom: (factor: number, anchor: number) => void
  onPan: (seconds: number) => void
  onToggleMute: (name: string) => void
  onToggleSolo: (name: string) => void
  onLevelChange: (name: string, level: number) => void
}

/** One lane per stem, like a video editor: mixer controls on the left, the waveform on the right. */
export function TrackLanes({
  tracks,
  mixer,
  gains,
  duration,
  currentTime,
  view,
  loop,
  bars,
  beats,
  onSeek,
  onZoom,
  onPan,
  onToggleMute,
  onToggleSolo,
  onLevelChange,
}: TrackLanesProps) {
  const timelineRef = useRef<HTMLDivElement>(null)
  const length = view.end - view.start
  const percent = (time: number) => (length > 0 ? ((time - view.start) / length) * 100 : 0)
  const timeAt = (clientX: number) => {
    const rect = timelineRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return view.start
    return view.start + clamp((clientX - rect.left) / rect.width, 0, 1) * length
  }
  const seekDrag = usePointerDrag((clientX) => onSeek(timeAt(clientX)))
  useWheelZoom(timelineRef, view, duration, onZoom, onPan)

  const region = getLoopRegion(loop)
  const shownRegion = region && {
    start: Math.max(region.start, view.start),
    end: Math.min(region.end, view.end),
  }

  return (
    <div className={styles.lanes} role="group" aria-label="Stem tracks">
      <div className={styles.headers}>
        {tracks.map((track) => (
          <LaneHeader
            key={track.name}
            track={track}
            mixer={mixer}
            heard={(gains[track.name] ?? 1) > 0}
            onToggleMute={onToggleMute}
            onToggleSolo={onToggleSolo}
            onLevelChange={onLevelChange}
          />
        ))}
      </div>
      <div
        ref={timelineRef}
        className={styles.timeline}
        title="Click or drag to seek; Ctrl + scroll to zoom"
        {...seekDrag}
      >
        {tracks.map((track) => (
          <div key={track.name} className={styles.wave} data-heard={(gains[track.name] ?? 1) > 0}>
            <StemWaveform
              peaks={track.peaks}
              view={view}
              color={STEM_COLORS[track.name] ?? STEM_COLORS.other}
            />
          </div>
        ))}
        {shownRegion && shownRegion.end > shownRegion.start && (
          <div
            className={styles.loop}
            data-enabled={loop.enabled}
            style={{
              left: `${percent(shownRegion.start)}%`,
              width: `${percent(shownRegion.end) - percent(shownRegion.start)}%`,
            }}
          />
        )}
        {bars && (
          <div className={styles.ticks}>
            <BeatTicks view={view} bars={bars} beats={beats} />
          </div>
        )}
        {currentTime >= view.start && currentTime <= view.end && (
          <div className={styles.playhead} style={{ left: `${percent(currentTime)}%` }} />
        )}
      </div>
    </div>
  )
}

interface LaneHeaderProps {
  track: StemTrack
  mixer: MixerSettings | null
  heard: boolean
  onToggleMute: (name: string) => void
  onToggleSolo: (name: string) => void
  onLevelChange: (name: string, level: number) => void
}

function LaneHeader({
  track,
  mixer,
  heard,
  onToggleMute,
  onToggleSolo,
  onLevelChange,
}: LaneHeaderProps) {
  const { name, label } = track
  const muted = mixer?.muted.includes(name) ?? false
  const solo = mixer?.solo.includes(name) ?? false
  // the slider shows what is heard: 0 while muted or left out of a solo
  const level = stemLevel(mixer, name)
  return (
    <div className={styles.header} data-heard={heard}>
      <span
        className={styles.swatch}
        style={{ background: STEM_COLORS[name] ?? STEM_COLORS.other }}
        aria-hidden="true"
      />
      <span className={styles.name}>{label}</span>
      <button
        type="button"
        className={`button button-small ${styles.toggle}`}
        aria-pressed={muted}
        onClick={() => onToggleMute(name)}
        aria-label={`Mute ${label}`}
        title={`Mute ${label}`}
      >
        M
      </button>
      <button
        type="button"
        className={`button button-small ${styles.toggle} ${styles.solo}`}
        aria-pressed={solo}
        onClick={() => onToggleSolo(name)}
        aria-label={`Solo ${label}`}
        title={`Solo ${label}: hear only the soloed stems`}
      >
        S
      </button>
      <input
        type="range"
        className={styles.volume}
        min={0}
        max={1}
        step={0.05}
        value={level}
        onChange={(event) => onLevelChange(name, Number(event.target.value))}
        aria-label={`${label} volume`}
        title={`${label}: ${Math.round(level * 100)} %`}
      />
    </div>
  )
}

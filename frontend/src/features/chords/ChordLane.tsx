import type { TimeView } from '../player/timelineView'
import { chordAt, chordName } from './chordNames'
import type { Chords } from './useChords'
import styles from './ChordLane.module.css'

interface ChordLaneProps {
  chords: Chords
  view: TimeView
  currentTime: number
}

/** Left column of the chord lane: its name and the chord playing now, large. */
export function ChordLaneHeader({ chords, currentTime }: Omit<ChordLaneProps, 'view'>) {
  const { status } = chords
  let current: string | null = null
  if (status.kind === 'ready') {
    const chord = chordAt(status.analysis.chords, currentTime)
    current = chord ? chordName(chord.label) : null
  }
  return (
    <div className={styles.header}>
      <span className={styles.title}>Chords</span>
      <span className={styles.current} aria-live="off" title="The chord playing now">
        {current ?? '–'}
      </span>
    </div>
  )
}

/** The chords as blocks along the shown part of the song; the current one lit. */
export function ChordLane({ chords, view, currentTime }: ChordLaneProps) {
  const { status } = chords
  const length = view.end - view.start
  if (status.kind === 'detecting' || status.kind === 'off') {
    return (
      <div className={styles.lane}>
        <span className={styles.note}>Finding chords…</span>
      </div>
    )
  }
  if (status.kind === 'failed') {
    return (
      <div className={styles.lane}>
        <span className={styles.error} role="alert">
          Chords not available: {status.error}
          <button
            type="button"
            className="button button-small"
            onClick={chords.retry}
            onPointerDown={(event) => event.stopPropagation()} // not a seek
          >
            Try again
          </button>
        </span>
      </div>
    )
  }
  const percent = (time: number) => ((time - view.start) / length) * 100
  const shown = status.analysis.chords.filter(
    (chord) => chord.label !== 'N' && chord.end > view.start && chord.start < view.end,
  )
  return (
    <div
      className={styles.lane}
      aria-label={status.analysis.fromStems ? 'Chords (from the stems)' : 'Chords'}
    >
      {shown.map((chord) => {
        const left = Math.max(0, percent(chord.start))
        const right = Math.min(100, percent(chord.end))
        const playing = chord.start <= currentTime && currentTime < chord.end
        return (
          <span
            key={chord.start}
            className={styles.chord}
            data-playing={playing}
            style={{ left: `${left}%`, width: `${right - left}%` }}
            title={`${chordName(chord.label)}: ${chord.start.toFixed(1)}–${chord.end.toFixed(1)} s`}
          >
            {chordName(chord.label)}
          </span>
        )
      })}
    </div>
  )
}

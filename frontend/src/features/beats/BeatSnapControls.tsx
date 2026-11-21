import type { BeatAnalysis } from '../../api/types'
import { SNAP_MODES, type SnapMode } from './beatGrid'
import type { BeatTracking } from './useBeatTracking'
import styles from './BeatSnapControls.module.css'

const MODE_LABELS: Record<SnapMode, string> = { off: 'Off', beat: 'Beats', bar: 'Bars' }

interface BeatSnapControlsProps {
  tracking: BeatTracking
  snapMode: SnapMode
  onSnapModeChange: (mode: SnapMode) => void
  /** Which beat of the bar the detected bar start is moved to (0 = as detected). */
  barShift: number
  onBarShiftChange: (delta: -1 | 1) => void
}

/** Beat detection status and the loop snap setting. */
export function BeatSnapControls({
  tracking,
  snapMode,
  onSnapModeChange,
  barShift,
  onBarShiftChange,
}: BeatSnapControlsProps) {
  return (
    <div className={styles.group} role="group" aria-label="Beat grid">
      <span className={styles.label}>Snap loop</span>
      <BeatStatus
        tracking={tracking}
        snapMode={snapMode}
        onSnapModeChange={onSnapModeChange}
        barShift={barShift}
        onBarShiftChange={onBarShiftChange}
      />
    </div>
  )
}

function BeatStatus({
  tracking,
  snapMode,
  onSnapModeChange,
  barShift,
  onBarShiftChange,
}: BeatSnapControlsProps) {
  const { state, requestError, retry } = tracking

  if (requestError) {
    return <Problem message={`Could not load the beats: ${requestError}`} onRetry={retry} />
  }
  if (state === null || state.status === 'not_started') {
    return <Busy text="Loading beats…" />
  }
  if (state.status === 'queued' || state.status === 'analyzing') {
    return <Busy text="Detecting beats…" />
  }
  if (state.status === 'failed' || state.analysis === null) {
    return (
      <Problem
        message={`Beat detection failed: ${state.error ?? 'unknown error'}`}
        onRetry={retry}
      />
    )
  }
  if (state.analysis.beats.length < 2) {
    return <span className={styles.note}>No beats found in this video</span>
  }
  return (
    <>
      <SnapModeSwitch analysis={state.analysis} mode={snapMode} onChange={onSnapModeChange} />
      <span className={styles.note}>{describeTempo(state.analysis)}</span>
      {snapMode === 'bar' && (
        <span className={styles.barShift}>
          <button
            type="button"
            className="icon-button icon-button-small"
            onClick={() => onBarShiftChange(-1)}
            aria-label="Move bar starts one beat earlier"
            title="Bar starts on the wrong beat? Move them one beat earlier"
          >
            ‹
          </button>
          <span className={styles.note}>Bar start{barShift !== 0 && ` (+${barShift})`}</span>
          <button
            type="button"
            className="icon-button icon-button-small"
            onClick={() => onBarShiftChange(1)}
            aria-label="Move bar starts one beat later"
            title="Bar starts on the wrong beat? Move them one beat later"
          >
            ›
          </button>
        </span>
      )}
    </>
  )
}

function SnapModeSwitch({
  analysis,
  mode,
  onChange,
}: {
  analysis: BeatAnalysis
  mode: SnapMode
  onChange: (mode: SnapMode) => void
}) {
  return (
    <span className={styles.switch} role="radiogroup" aria-label="Snap loop points to">
      {SNAP_MODES.map((option) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={mode === option}
          className={styles.option}
          disabled={option === 'bar' && analysis.downbeats.length < 2}
          onClick={() => onChange(option)}
          title={`Snap loop points: ${MODE_LABELS[option]} (G)`}
        >
          {MODE_LABELS[option]}
        </button>
      ))}
    </span>
  )
}

function describeTempo(analysis: BeatAnalysis): string {
  const parts = []
  if (analysis.bpm !== null) parts.push(`${Math.round(analysis.bpm)} BPM`)
  if (analysis.beatsPerBar !== null) parts.push(`${analysis.beatsPerBar} beats per bar`)
  return parts.join(' · ')
}

function Busy({ text }: { text: string }) {
  return (
    <span className={styles.note} role="status">
      <span className={styles.spinner} aria-hidden="true" /> {text}
    </span>
  )
}

function Problem({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <span className={styles.problem} role="alert">
      {message}
      <button type="button" className="button button-small" onClick={onRetry}>
        Retry
      </button>
    </span>
  )
}

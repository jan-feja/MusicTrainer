import type { BeatAnalysis, BeatGridHints } from '../../api/types'
import { SNAP_MODES, type SnapMode, barLengths } from './beatGrid'
import type { BeatTracking } from './useBeatTracking'
import styles from './BeatSnapControls.module.css'

const MODE_LABELS: Record<SnapMode, string> = { off: 'Off', beat: 'Beats', bar: 'Bars' }
const BEATS_PER_BAR_CHOICES = [2, 3, 4, 5, 6, 7, 8, 9, 12]

interface BeatSnapControlsProps {
  tracking: BeatTracking
  snapMode: SnapMode
  onSnapModeChange: (mode: SnapMode) => void
  /** Move the bar starts one beat earlier or later, from the bar at the playhead on. */
  onMoveBarStarts: (delta: -1 | 1) => void
  /** Go back to the detected bar starts. */
  onResetBarStarts: () => void
}

/** Beat detection status, the loop snap setting and fixes for the beat grid. */
export function BeatSnapControls(props: BeatSnapControlsProps) {
  return (
    <div className={styles.group} role="group" aria-label="Beat grid">
      <span className={styles.label}>Snap loop</span>
      <BeatStatus {...props} />
    </div>
  )
}

function BeatStatus({
  tracking,
  snapMode,
  onSnapModeChange,
  onMoveBarStarts,
  onResetBarStarts,
}: BeatSnapControlsProps) {
  const { state, analysis, updating, requestError, retry, setHints } = tracking

  if (requestError) {
    return <Problem message={`Could not load the beats: ${requestError}`} onRetry={retry} />
  }
  if (state?.status === 'failed') {
    return (
      <Problem
        message={`Beat detection failed: ${state.error ?? 'unknown error'}`}
        onRetry={retry}
      />
    )
  }
  if (analysis === null) {
    const detecting = state?.status === 'queued' || state?.status === 'analyzing'
    return <Busy text={detecting ? 'Detecting beats…' : 'Loading beats…'} />
  }
  if (analysis.beats.length < 2) {
    return <span className={styles.note}>No beats found in this video</span>
  }
  return (
    <>
      <SnapModeSwitch analysis={analysis} mode={snapMode} onChange={onSnapModeChange} />
      <GridHints analysis={analysis} onChange={setHints} disabled={updating} />
      {snapMode === 'bar' && (
        <span className={styles.barShift} role="group" aria-label="Bar starts">
          <button
            type="button"
            className="icon-button icon-button-small"
            onClick={() => onMoveBarStarts(-1)}
            disabled={updating}
            aria-label="Move bar starts from here on one beat earlier"
            title="Bar starts on the wrong beat from here on? Move them one beat earlier"
          >
            ‹
          </button>
          <span className={styles.note}>Bar start</span>
          <button
            type="button"
            className="icon-button icon-button-small"
            onClick={() => onMoveBarStarts(1)}
            disabled={updating}
            aria-label="Move bar starts from here on one beat later"
            title="Bar starts on the wrong beat from here on? Move them one beat later"
          >
            ›
          </button>
          {analysis.hints.barStarts.length > 0 && (
            <button
              type="button"
              className={styles.small}
              onClick={onResetBarStarts}
              disabled={updating}
              aria-label="Use the detected bar starts"
              title="Use the detected bar starts again"
            >
              ↺
            </button>
          )}
        </span>
      )}
      {updating && <Busy text="Updating…" />}
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

/** Detected tempo and meter, with fixes for when the detection picked the wrong one. */
function GridHints({
  analysis,
  onChange,
  disabled,
}: {
  analysis: BeatAnalysis
  onChange: (hints: BeatGridHints) => void
  disabled: boolean
}) {
  const { hints, bpm, beatsPerBar } = analysis
  // sections in other meters show as e.g. "Auto (4, 3)"
  const detected = barLengths(analysis)
  const autoLabel = detected.length > 0 ? detected.join(', ') : beatsPerBar
  // a new tempo or meter makes new beats: bar starts the user placed no longer fit
  const setTempo = (tempoBpm: number | null) => onChange({ ...hints, tempoBpm, barStarts: [] })
  return (
    <>
      {bpm !== null && (
        <span className={styles.hint} role="group" aria-label="Tempo">
          <span className={styles.note}>{Math.round(bpm)} BPM</span>
          <button
            type="button"
            className={styles.small}
            onClick={() => setTempo(Math.round(bpm / 2))}
            disabled={disabled || bpm / 2 < 30}
            aria-label="Half the tempo"
            title="Beats detected twice too fast? Detect them at half the tempo"
          >
            ½×
          </button>
          <button
            type="button"
            className={styles.small}
            onClick={() => setTempo(Math.round(bpm * 2))}
            disabled={disabled || bpm * 2 > 300}
            aria-label="Double the tempo"
            title="Beats detected half too slow? Detect them at double the tempo"
          >
            2×
          </button>
          {hints.tempoBpm !== null && (
            <button
              type="button"
              className={styles.small}
              onClick={() => setTempo(null)}
              disabled={disabled}
              aria-label="Detect the tempo automatically"
              title="Detect the tempo automatically"
            >
              ↺
            </button>
          )}
          <button
            type="button"
            className={styles.small}
            onClick={() => onChange({ ...hints, steadyTempo: !hints.steadyTempo })}
            disabled={disabled}
            aria-pressed={hints.steadyTempo}
            title="Played to a click? Space all beats exactly evenly, so every bar has the same length"
          >
            Steady
          </button>
        </span>
      )}
      <label className={styles.hint}>
        <select
          className={styles.select}
          value={hints.beatsPerBar ?? 'auto'}
          disabled={disabled}
          onChange={(event) => {
            const value = event.target.value
            const beatsPerBar = value === 'auto' ? null : Number(value)
            onChange({ ...hints, beatsPerBar, barStarts: [] })
          }}
          aria-label="Beats per bar"
          title="Beats per bar: detected (several when the meter changes between sections), or set one for the whole song if the bars come out wrong"
        >
          <option value="auto">
            {hints.beatsPerBar === null && autoLabel !== null ? `Auto (${autoLabel})` : 'Auto'}
          </option>
          {BEATS_PER_BAR_CHOICES.map((count) => (
            <option key={count} value={count}>
              {count}
            </option>
          ))}
        </select>
        <span className={styles.note}>beats per bar</span>
      </label>
    </>
  )
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

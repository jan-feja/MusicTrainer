import {
  MAX_PLAYBACK_RATE,
  MIN_PLAYBACK_RATE,
  PLAYBACK_RATE_PRESETS,
  PLAYBACK_RATE_STEP,
  formatPlaybackRate,
} from './playbackRate'
import styles from './PlayerControls.module.css'

interface SpeedControlProps {
  rate: number
  /** Set an exact rate (slider, presets). */
  onChange: (rate: number) => void
  /** Change the rate by steps of 0.05 (− / + buttons). */
  onStep: (steps: number) => void
  /** Tempo of the song; shown as the tempo at the current speed. */
  bpm?: number | null
}

export function SpeedControl({ rate, onChange, onStep, bpm }: SpeedControlProps) {
  const preset = (PLAYBACK_RATE_PRESETS as readonly number[]).includes(rate) ? String(rate) : ''

  return (
    <div className={styles.group} role="group" aria-label="Playback speed">
      <span className={styles.groupLabel}>Speed</span>
      <button
        type="button"
        className="icon-button"
        onClick={() => onStep(-1)}
        disabled={rate <= MIN_PLAYBACK_RATE}
        aria-label="Slower"
        title="Slower (−)"
      >
        −
      </button>
      <input
        type="range"
        className={styles.slider}
        min={MIN_PLAYBACK_RATE}
        max={MAX_PLAYBACK_RATE}
        step={PLAYBACK_RATE_STEP}
        value={rate}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-label="Playback speed"
        aria-valuetext={formatPlaybackRate(rate)}
      />
      <button
        type="button"
        className="icon-button"
        onClick={() => onStep(1)}
        disabled={rate >= MAX_PLAYBACK_RATE}
        aria-label="Faster"
        title="Faster (+)"
      >
        +
      </button>
      <select
        className={styles.select}
        value={preset}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-label="Speed presets"
      >
        {preset === '' && <option value="">{formatPlaybackRate(rate)}</option>}
        {PLAYBACK_RATE_PRESETS.map((value) => (
          <option key={value} value={value}>
            {formatPlaybackRate(value)}
          </option>
        ))}
      </select>
      {bpm != null && (
        <span
          className={styles.tempo}
          title={`Song tempo ${Math.round(bpm)} BPM × ${formatPlaybackRate(rate)}`}
        >
          {Math.round(bpm * rate)} BPM
        </span>
      )}
    </div>
  )
}

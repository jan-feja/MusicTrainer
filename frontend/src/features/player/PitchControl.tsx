import { MAX_PITCH, MIN_PITCH } from './pitchShift'
import styles from './PlayerControls.module.css'

interface PitchControlProps {
  semitones: number
  busy: boolean
  available: boolean
  error: string | null
  onChange: (semitones: number) => void
}

export function PitchControl({ semitones, busy, available, error, onChange }: PitchControlProps) {
  const disabled = busy || !available
  const label = semitones > 0 ? `+${semitones}` : String(semitones)
  return (
    <div className={styles.group} role="group" aria-label="Pitch shift">
      <span className={styles.groupLabel}>Pitch</span>
      <button
        type="button"
        className="icon-button"
        disabled={disabled || semitones <= MIN_PITCH}
        onClick={() => onChange(semitones - 1)}
        aria-label="Lower pitch"
        title="Lower pitch by one semitone"
      >
        −
      </button>
      <span className={styles.time} aria-live="polite">
        {label} semitones
      </span>
      <button
        type="button"
        className="icon-button"
        disabled={disabled || semitones >= MAX_PITCH}
        onClick={() => onChange(semitones + 1)}
        aria-label="Raise pitch"
        title="Raise pitch by one semitone"
      >
        +
      </button>
      <button
        type="button"
        className="button button-small"
        disabled={disabled || semitones === 0}
        onClick={() => onChange(0)}
      >
        Reset
      </button>
      {!available && <span className={styles.tempo}>Pitch shift unavailable</span>}
      {error && <span role="alert">{error}</span>}
    </div>
  )
}

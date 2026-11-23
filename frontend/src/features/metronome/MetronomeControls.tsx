import styles from '../player/PlayerControls.module.css'

interface MetronomeControlsProps {
  available: boolean
  enabled: boolean
  starting: boolean
  volume: number
  error: string | null
  onToggle: () => void
  onVolumeChange: (volume: number) => void
}

export function MetronomeControls({
  available,
  enabled,
  starting,
  volume,
  error,
  onToggle,
  onVolumeChange,
}: MetronomeControlsProps) {
  return (
    <div className={styles.group} role="group" aria-label="Metronome">
      <button
        type="button"
        className="button button-small"
        aria-pressed={enabled}
        disabled={starting || (!available && !enabled)}
        onClick={onToggle}
        title={available ? 'Play a click on each beat' : 'Metronome needs a detected beat grid'}
      >
        Metronome {starting ? 'Starting…' : enabled ? 'On' : 'Off'}
      </button>
      <label className={styles.group}>
        <span className={styles.groupLabel}>Click volume</span>
        <input
          type="range"
          className={`${styles.slider} ${styles.volumeSlider}`}
          min={0}
          max={1}
          step={0.05}
          value={volume}
          onChange={(event) => onVolumeChange(Number(event.target.value))}
          aria-label="Metronome volume"
        />
      </label>
      {!available && <span className={styles.tempo}>Waiting for beats</span>}
      {error && <span role="alert">{error}</span>}
    </div>
  )
}

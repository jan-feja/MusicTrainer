import { MutedIcon, VolumeIcon } from '../../components/icons'
import styles from './PlayerControls.module.css'

interface VolumeControlProps {
  volume: number
  isMuted: boolean
  onVolumeChange: (volume: number) => void
  onToggleMute: () => void
}

export function VolumeControl({
  volume,
  isMuted,
  onVolumeChange,
  onToggleMute,
}: VolumeControlProps) {
  const silent = isMuted || volume === 0
  return (
    <div className={styles.group}>
      <button
        type="button"
        className="icon-button"
        onClick={onToggleMute}
        aria-label={silent ? 'Unmute' : 'Mute'}
        title={silent ? 'Unmute (M)' : 'Mute (M)'}
      >
        {silent ? <MutedIcon /> : <VolumeIcon />}
      </button>
      <input
        type="range"
        className={`${styles.slider} ${styles.volumeSlider}`}
        min={0}
        max={1}
        step={0.05}
        value={silent ? 0 : volume}
        onChange={(event) => onVolumeChange(Number(event.target.value))}
        aria-label="Volume"
      />
    </div>
  )
}

import type { MixerSettings } from '../../api/types'
import { ProgressBar } from '../../components/ProgressBar'
import type { StemTrack } from './stems'
import type { Stems } from './useStems'
import styles from './StemsControls.module.css'

interface MixerProps {
  mixer: MixerSettings | null
  /** What each stem is heard at (after mute and solo). */
  gains: Record<string, number>
  onToggleMute: (name: string) => void
  onToggleSolo: (name: string) => void
  onVolumeChange: (name: string, volume: number) => void
}

interface StemsControlsProps extends MixerProps {
  stems: Stems
  enabled: boolean
  onToggle: () => void
}

/** Turns the stems on and off, shows how far they are, and mixes them once loaded. */
export function StemsControls({ stems, enabled, onToggle, ...mixer }: StemsControlsProps) {
  return (
    <div className={styles.group}>
      <span className={styles.label}>Stems</span>
      <button
        type="button"
        className="button button-small"
        onClick={onToggle}
        aria-pressed={enabled}
        title="Separate the song into instruments to mute or solo them"
      >
        {enabled ? 'On' : 'Off'}
      </button>
      <StemsStatusView stems={stems} mixer={mixer} />
    </div>
  )
}

function percent(value: number): string {
  return `${Math.round(value * 100)} %`
}

function StemsStatusView({ stems, mixer }: { stems: Stems; mixer: MixerProps }) {
  const { status } = stems
  switch (status.kind) {
    case 'off':
      return null
    case 'checking':
      return (
        <span className={styles.note} role="status">
          <span className={styles.spinner} aria-hidden="true" />
          Looking for stems…
        </span>
      )
    case 'separating':
      return (
        <span className={styles.progress} role="status">
          {status.progress === null ? (
            <span className={styles.note}>
              <span className={styles.spinner} aria-hidden="true" />
              Waiting to separate…
            </span>
          ) : (
            <>
              <span className={styles.note}>
                Separating instruments… {percent(status.progress)}
              </span>
              <span className={styles.bar}>
                <ProgressBar value={status.progress} label="Separating instruments" />
              </span>
            </>
          )}
          <span className={styles.hint}>About 2 minutes per song; the video plays on.</span>
        </span>
      )
    case 'loading':
      return (
        <span className={styles.progress} role="status">
          <span className={styles.note}>Loading stems… {percent(status.progress)}</span>
          <span className={styles.bar}>
            <ProgressBar value={status.progress} label="Loading stems" />
          </span>
        </span>
      )
    case 'failed':
      return (
        <span className={styles.failed} role="alert">
          Stems not available: {status.error}
          <button type="button" className="button button-small" onClick={stems.retry}>
            Try again
          </button>
        </span>
      )
    case 'ready':
      return (
        <ul className={styles.list} aria-label="Stems">
          {status.tracks.map((track) => (
            <StemStrip key={track.name} track={track} {...mixer} />
          ))}
        </ul>
      )
  }
}

function StemStrip({
  track,
  mixer,
  gains,
  onToggleMute,
  onToggleSolo,
  onVolumeChange,
}: MixerProps & { track: StemTrack }) {
  const { name, label } = track
  const muted = mixer?.muted.includes(name) ?? false
  const solo = mixer?.solo.includes(name) ?? false
  const volume = mixer?.volumes[name] ?? 1
  return (
    <li
      className={styles.stem}
      data-quiet={track.quiet}
      data-silent={(gains[name] ?? 1) === 0}
      title={track.quiet ? `${label}: hardly anything in this song` : undefined}
    >
      <span className={styles.stemName}>{label}</span>
      <button
        type="button"
        className={`button button-small ${styles.mute}`}
        aria-pressed={muted}
        onClick={() => onToggleMute(name)}
        aria-label={`Mute ${label}`}
        title={`Mute ${label}`}
      >
        M
      </button>
      <button
        type="button"
        className={`button button-small ${styles.solo}`}
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
        value={volume}
        onChange={(event) => onVolumeChange(name, Number(event.target.value))}
        aria-label={`${label} volume`}
        title={`${label} volume: ${Math.round(volume * 100)} %`}
      />
    </li>
  )
}

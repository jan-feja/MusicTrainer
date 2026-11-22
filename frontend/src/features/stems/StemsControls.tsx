import { ProgressBar } from '../../components/ProgressBar'
import type { Stems } from './useStems'
import styles from './StemsControls.module.css'

interface StemsControlsProps {
  stems: Stems
  enabled: boolean
  onToggle: () => void
}

/** Turns the stems on and off, and shows how far they are; the track lanes mix them. */
export function StemsControls({ stems, enabled, onToggle }: StemsControlsProps) {
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
      <StemsStatusView stems={stems} />
    </div>
  )
}

function percent(value: number): string {
  return `${Math.round(value * 100)} %`
}

function StemsStatusView({ stems }: { stems: Stems }) {
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
    case 'ready': {
      const absent = status.tracks.filter((track) => track.quiet).map((track) => track.label)
      return absent.length > 0 ? (
        <span className={styles.hint}>Not in this song: {absent.join(', ')}</span>
      ) : null
    }
  }
}

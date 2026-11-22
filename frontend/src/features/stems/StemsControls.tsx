import { ProgressBar } from '../../components/ProgressBar'
import type { Stems } from './useStems'
import styles from './StemsControls.module.css'

interface StemsControlsProps {
  stems: Stems
  enabled: boolean
  onToggle: () => void
}

/**
 * The stems' state: progress while the song is separated (it starts by itself),
 * then the On / Off switch; a failure offers to try again.
 */
export function StemsControls({ stems, enabled, onToggle }: StemsControlsProps) {
  const { status } = stems
  const separated =
    status.kind === 'available' ||
    status.kind === 'loading' ||
    status.kind === 'ready' ||
    (status.kind === 'failed' && status.separated === true)
  return (
    <div className={styles.group}>
      <span className={styles.label}>Stems</span>
      {separated && (
        <button
          type="button"
          className="button button-small"
          onClick={onToggle}
          aria-pressed={enabled}
          title="Play the separated instruments, to mute or solo them"
        >
          {enabled ? 'On' : 'Off'}
        </button>
      )}
      <StemsStatusView stems={stems} />
    </div>
  )
}

function percent(value: number): string {
  return `${Math.round(value * 100)} %`
}

function waitingText(songsAhead: number | null): string {
  if (!songsAhead) return 'Waiting to separate…'
  return `Waiting to separate: ${songsAhead} ${songsAhead === 1 ? 'song' : 'songs'} ahead…`
}

function StemsStatusView({ stems }: { stems: Stems }) {
  const { status } = stems
  switch (status.kind) {
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
              {waitingText(status.songsAhead)}
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
          {status.separated ? 'Stems could not be loaded' : 'Stems not available'}: {status.error}
          <button type="button" className="button button-small" onClick={stems.retry}>
            Try again
          </button>
        </span>
      )
    case 'available':
    case 'ready':
      return null
  }
}

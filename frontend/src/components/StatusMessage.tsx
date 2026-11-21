import type { ReactNode } from 'react'
import styles from './StatusMessage.module.css'

interface StatusMessageProps {
  kind: 'loading' | 'error' | 'info'
  children: ReactNode
  onRetry?: () => void
}

/** A centered message for loading, error and empty states. */
export function StatusMessage({ kind, children, onRetry }: StatusMessageProps) {
  return (
    <div className={styles.message} data-kind={kind} role={kind === 'error' ? 'alert' : 'status'}>
      {kind === 'loading' && <span className={styles.spinner} aria-hidden="true" />}
      <p>{children}</p>
      {onRetry && (
        <button type="button" className="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

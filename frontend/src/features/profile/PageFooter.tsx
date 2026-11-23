import { StatusMessage } from '../../components/StatusMessage'
import type { Pages } from './usePages'
import styles from './Profile.module.css'

/** Under a paged list: loading, an error, or "Show more". */
export function PageFooter({
  pages,
}: {
  pages: Pick<Pages<unknown>, 'loading' | 'error' | 'hasMore' | 'loadMore' | 'reload'>
}) {
  if (pages.loading) return <StatusMessage kind="loading">Loading…</StatusMessage>
  if (pages.error) {
    return (
      <StatusMessage kind="error" onRetry={pages.reload}>
        {pages.error}
      </StatusMessage>
    )
  }
  if (!pages.hasMore) return null
  return (
    <button
      type="button"
      className={`button button-small button-ghost ${styles.more}`}
      onClick={pages.loadMore}
    >
      Show more
    </button>
  )
}

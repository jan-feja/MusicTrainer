import { Link, useSearchParams } from 'react-router'
import { api } from '../../api/client'
import type { FeedScope } from '../../api/types'
import { paths } from '../../app/paths'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { useAuth } from '../auth/authContext'
import { PageFooter } from './PageFooter'
import { FeedList } from './PracticeList'
import { usePages } from './usePages'
import styles from './Profile.module.css'

const TABS: { scope: FeedScope; label: string }[] = [
  { scope: 'everyone', label: 'Everyone' },
  { scope: 'following', label: 'Following' },
]

/** What people practiced lately: everyone with a public profile, or the people you follow. */
export function FeedPage() {
  useDocumentTitle('Feed')
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const scope: FeedScope = params.get('scope') === 'following' ? 'following' : 'everyone'

  return (
    <div className={styles.profile}>
      <div className={styles.feedHeader}>
        <h1 className={styles.pageTitle}>Feed</h1>
        <div className={styles.tabs} role="tablist" aria-label="Whose practice">
          {TABS.map((tab) => (
            <button
              key={tab.scope}
              type="button"
              role="tab"
              aria-selected={scope === tab.scope}
              className={styles.tab}
              onClick={() => setParams(tab.scope === 'everyone' ? {} : { scope: tab.scope })}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      {scope === 'following' && !user ? (
        <p className={styles.empty}>
          <Link to={paths.login}>Log in</Link> to see what the people you follow practice.
        </p>
      ) : (
        <Feed key={scope} scope={scope} />
      )}
    </div>
  )
}

function Feed({ scope }: { scope: FeedScope }) {
  const feed = usePages((before, signal) => api.getFeed(scope, before, signal), scope)
  return (
    <>
      {feed.items.length > 0 && <FeedList entries={feed.items} />}
      {!feed.loading && !feed.error && feed.items.length === 0 && (
        <p className={styles.empty}>
          {scope === 'everyone'
            ? 'Nobody has practiced yet. Open a song and play it: it shows up here.'
            : 'Nobody you follow has practiced yet. Find people in the Everyone feed.'}
        </p>
      )}
      <PageFooter pages={feed} />
    </>
  )
}

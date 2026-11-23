import { Link, useParams } from 'react-router'
import { api } from '../../api/client'
import { paths } from '../../app/paths'
import { StatusMessage } from '../../components/StatusMessage'
import { errorMessage } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { UserList } from './UserList'
import styles from './Profile.module.css'

/** Who follows a user, or whom they follow. */
export function FollowListPage({ list }: { list: 'followers' | 'following' }) {
  const { username = '' } = useParams()
  const users = useAsync(
    (signal) =>
      list === 'followers'
        ? api.getFollowers(username, signal)
        : api.getFollowing(username, signal),
    `${list}:${username}`,
  )
  const title = list === 'followers' ? `Followers of ${username}` : `${username} follows`
  useDocumentTitle(title)
  return (
    <div className={styles.profile}>
      <p className={styles.back}>
        <Link to={paths.profile(username)}>← {username}</Link>
      </p>
      <h1 className={styles.pageTitle}>{title}</h1>
      {users.status === 'loading' && <StatusMessage kind="loading">Loading…</StatusMessage>}
      {users.status === 'error' && (
        <StatusMessage kind="error" onRetry={users.reload}>
          {errorMessage(users.error)}
        </StatusMessage>
      )}
      {users.status === 'success' &&
        (users.data.length === 0 ? (
          <p className={styles.empty}>
            {list === 'followers' ? 'No followers yet.' : 'Not following anyone yet.'}
          </p>
        ) : (
          <UserList users={users.data} />
        ))}
    </div>
  )
}

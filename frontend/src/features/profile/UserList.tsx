import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { UserSummary } from '../../api/types'
import { paths } from '../../app/paths'
import { UserAvatar } from './UserAvatar'
import styles from './Profile.module.css'

/** Users with their avatar and description, each linking to the profile. */
export function UserList({
  users,
  actions,
}: {
  users: readonly UserSummary[]
  /** Buttons for one user, e.g. accepting a follow request. */
  actions?: (user: UserSummary) => ReactNode
}) {
  return (
    <ul className={styles.userList}>
      {users.map((user) => (
        <li key={user.username} className={styles.userRow}>
          <Link to={paths.profile(user.username)} className={styles.userLink}>
            <UserAvatar username={user.username} size={36} />
            <span className={styles.userText}>
              <span className={styles.userName}>{user.username}</span>
              {user.description && <span className={styles.userBio}>{user.description}</span>}
            </span>
          </Link>
          {actions && <span className={styles.userActions}>{actions(user)}</span>}
        </li>
      ))}
    </ul>
  )
}

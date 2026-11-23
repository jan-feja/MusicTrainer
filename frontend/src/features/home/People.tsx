import { useState } from 'react'
import { Link } from 'react-router'
import type { FollowState, UserSummary } from '../../api/types'
import { paths } from '../../app/paths'
import { useAuth } from '../auth/authContext'
import { FollowButton } from '../profile/FollowButton'
import { UserAvatar } from '../profile/UserAvatar'
import styles from './HomePage.module.css'

/** Profiles as small cards, each with a Follow (or Following) button for an account. */
export function People({
  users,
  state = 'none',
}: {
  users: readonly UserSummary[]
  /** How the user follows them all at first. */
  state?: FollowState
}) {
  return (
    <ul className={styles.people}>
      {users.map((person) => (
        <li key={person.username}>
          <PersonCard person={person} initialState={state} />
        </li>
      ))}
    </ul>
  )
}

function PersonCard({ person, initialState }: { person: UserSummary; initialState: FollowState }) {
  const { user } = useAuth()
  const [state, setState] = useState(initialState)
  return (
    <article className={styles.person}>
      <Link to={paths.profile(person.username)} className={styles.personLink}>
        <UserAvatar username={person.username} size={48} />
        <span className={styles.personName}>{person.username}</span>
        {person.description && <span className={styles.personBio}>{person.description}</span>}
      </Link>
      {user && (
        <FollowButton
          username={person.username}
          isPrivate={false}
          state={state}
          onChange={setState}
        />
      )}
    </article>
  )
}

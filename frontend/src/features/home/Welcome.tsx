import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api/client'
import type { User } from '../../api/types'
import { paths } from '../../app/paths'
import { formatDuration } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useAuth } from '../auth/authContext'
import { greeting } from './greeting'
import styles from './HomePage.module.css'

/** "Good morning, misho!" and how long they practiced today; a guest is invited to register. */
export function Welcome() {
  const { user } = useAuth()
  // the hour when the page opened
  const [hello] = useState(() => greeting(new Date().getHours()))
  return (
    <div className={styles.welcome}>
      <h1 className={styles.welcomeTitle}>{user ? `${hello}, ${user.username}!` : `${hello}!`}</h1>
      {user ? (
        <PracticedToday user={user} />
      ) : (
        <p className={styles.welcomeText}>
          You are practicing as a guest: your songs and presets stay in this browser.{' '}
          <Link to={paths.register}>Register</Link> or <Link to={paths.login}>log in</Link> to keep
          them, follow other players and see how much you practice.
        </p>
      )}
    </div>
  )
}

function PracticedToday({ user }: { user: User }) {
  const today = useAsync((signal) => api.getPracticeToday(signal), user.username)
  if (today.status !== 'success') return <p className={styles.welcomeText}>&nbsp;</p>
  const { seconds } = today.data
  return (
    <p className={styles.welcomeText}>
      {seconds > 0 ? (
        <>
          You have practiced <strong>{formatDuration(seconds)}</strong> today.
        </>
      ) : (
        'You have not practiced today yet. Pick a song below and play.'
      )}
    </p>
  )
}

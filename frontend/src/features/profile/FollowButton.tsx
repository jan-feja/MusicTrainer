import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api/client'
import type { FollowState } from '../../api/types'
import { paths } from '../../app/paths'
import { errorMessage } from '../../lib/format'
import { useAuth } from '../auth/authContext'

interface FollowButtonProps {
  username: string
  isPrivate: boolean
  state: FollowState
  /** The new state, once the server has it. */
  onChange: (state: FollowState) => void
}

/** Follow / Following / Requested; a guest is asked to log in. */
export function FollowButton({ username, isPrivate, state, onChange }: FollowButtonProps) {
  const { user } = useAuth()
  const [busy, setBusy] = useState(false)
  if (state === 'self') return null
  if (!user) {
    return (
      <Link to={paths.login} className="button button-small button-primary">
        Log in to follow
      </Link>
    )
  }

  const run = (action: () => Promise<FollowState>) => {
    setBusy(true)
    action().then(
      (next) => {
        setBusy(false)
        onChange(next)
      },
      (error: unknown) => {
        setBusy(false)
        window.alert(errorMessage(error))
      },
    )
  }
  const unfollow = () => api.unfollow(username).then((): FollowState => 'none')

  if (state === 'none') {
    return (
      <button
        type="button"
        className="button button-small button-primary"
        disabled={busy}
        onClick={() => run(() => api.follow(username))}
        title={isPrivate ? `${username} decides whether you may follow` : undefined}
      >
        {isPrivate ? 'Ask to follow' : 'Follow'}
      </button>
    )
  }
  if (state === 'requested') {
    return (
      <button
        type="button"
        className="button button-small button-ghost"
        disabled={busy}
        onClick={() => run(unfollow)}
        title="Waiting for an answer. Click to take back the request."
      >
        Requested
      </button>
    )
  }
  return (
    <button
      type="button"
      className="button button-small button-ghost"
      disabled={busy}
      onClick={() => {
        if (window.confirm(`Stop following ${username}?`)) run(unfollow)
      }}
      title="Click to stop following"
    >
      Following
    </button>
  )
}

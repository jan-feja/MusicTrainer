import { type FormEvent, useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { api } from '../../api/client'
import { paths } from '../../app/paths'
import { errorMessage } from '../../lib/format'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { MIN_PASSWORD_LENGTH } from './AuthPages'
import { useAuth } from './authContext'
import styles from './auth.module.css'

export function ProfilePage() {
  useDocumentTitle('Profile')
  const { user } = useAuth()
  if (!user) {
    return <Navigate to={paths.login} replace />
  }
  return (
    <div className={styles.stack}>
      <h1 className={styles.title}>{user.username}</h1>
      <ChangePassword />
      <DeleteAccount />
    </div>
  )
}

function ChangePassword() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [message, setMessage] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setMessage(null)
    setBusy(true)
    try {
      await api.changePassword(current, next)
      setCurrent('')
      setNext('')
      setMessage({ kind: 'success', text: 'Password changed. Other browsers were logged out.' })
    } catch (error) {
      setMessage({ kind: 'error', text: errorMessage(error) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={styles.card} onSubmit={(event) => void submit(event)}>
      <h2>Change password</h2>
      <label className={styles.field}>
        <span>Current password</span>
        <input
          className={styles.input}
          type="password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      <label className={styles.field}>
        <span>New password</span>
        <input
          className={styles.input}
          type="password"
          value={next}
          onChange={(event) => setNext(event.target.value)}
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
        />
        <small className={styles.help}>At least {MIN_PASSWORD_LENGTH} characters</small>
      </label>
      {message && (
        <p
          className={message.kind === 'error' ? styles.error : styles.success}
          role={message.kind === 'error' ? 'alert' : 'status'}
        >
          {message.text}
        </p>
      )}
      <button type="submit" className="button button-primary" disabled={busy}>
        Change password
      </button>
    </form>
  )
}

function DeleteAccount() {
  const { deleteAccount } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!window.confirm('Delete your account, your library and your saved loops for good?')) {
      return
    }
    setError(null)
    setBusy(true)
    try {
      await deleteAccount(password)
      void navigate(paths.library, { replace: true })
    } catch (reason) {
      setError(errorMessage(reason))
      setBusy(false)
    }
  }

  return (
    <form className={styles.card} onSubmit={(event) => void submit(event)}>
      <h2>Delete account</h2>
      <p className={styles.note}>
        Your library and saved loops are deleted. Songs nobody else has are deleted from the server.
      </p>
      <label className={styles.field}>
        <span>Password</span>
        <input
          className={styles.input}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <button type="submit" className="button button-ghost" disabled={busy}>
        Delete account
      </button>
    </form>
  )
}

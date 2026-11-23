import { type FormEvent, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { api } from '../../api/client'
import type { ProfileSettings } from '../../api/types'
import { paths } from '../../app/paths'
import { StatusMessage } from '../../components/StatusMessage'
import { errorMessage } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { MIN_PASSWORD_LENGTH } from './AuthPages'
import { useAuth } from './authContext'
import styles from './auth.module.css'

export const MAX_DESCRIPTION_LENGTH = 300

/** The account's settings: profile description and privacy, password, deleting it. */
export function SettingsPage() {
  useDocumentTitle('Settings')
  const { user } = useAuth()
  if (!user) {
    return <Navigate to={paths.login} replace />
  }
  return (
    <div className={styles.stack}>
      <div className={styles.titleRow}>
        <h1 className={styles.title}>Settings</h1>
        <Link to={paths.profile(user.username)}>Your profile</Link>
      </div>
      <ProfileForm />
      <ChangePassword />
      <DeleteAccount />
    </div>
  )
}

function ProfileForm() {
  const loaded = useAsync((signal) => api.getProfileSettings(signal), 'profile-settings')
  if (loaded.status === 'loading') return <StatusMessage kind="loading">Loading…</StatusMessage>
  if (loaded.status === 'error') {
    return (
      <StatusMessage kind="error" onRetry={loaded.reload}>
        {errorMessage(loaded.error)}
      </StatusMessage>
    )
  }
  return <ProfileFields initial={loaded.data} />
}

function ProfileFields({ initial }: { initial: ProfileSettings }) {
  const [description, setDescription] = useState(initial.description)
  const [isPrivate, setIsPrivate] = useState(initial.isPrivate)
  const [saved, setSaved] = useState(initial)
  const [message, setMessage] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const changed = description.trim() !== saved.description || isPrivate !== saved.isPrivate

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setMessage(null)
    setBusy(true)
    try {
      const next = await api.saveProfileSettings({ description, isPrivate })
      setSaved(next)
      setDescription(next.description)
      setMessage({ kind: 'success', text: 'Profile saved.' })
    } catch (error) {
      setMessage({ kind: 'error', text: errorMessage(error) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className={styles.card} onSubmit={(event) => void submit(event)}>
      <h2>Profile</h2>
      <label className={styles.field}>
        <span>Description</span>
        <textarea
          className={`${styles.input} ${styles.textarea}`}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={MAX_DESCRIPTION_LENGTH}
          rows={3}
          placeholder="What do you play? What are you practicing?"
        />
        <small className={styles.help}>
          {description.length} / {MAX_DESCRIPTION_LENGTH}
        </small>
      </label>
      <label className={styles.check}>
        <input
          type="checkbox"
          checked={isPrivate}
          onChange={(event) => setIsPrivate(event.target.checked)}
        />
        <span>
          <strong>Private profile</strong>
          <small className={styles.help}>
            Only followers you accept see your songs and practice; you are left out of the everyone
            feed. Making it public again accepts the waiting requests.
          </small>
        </span>
      </label>
      {message && (
        <p
          className={message.kind === 'error' ? styles.error : styles.success}
          role={message.kind === 'error' ? 'alert' : 'status'}
        >
          {message.text}
        </p>
      )}
      <button type="submit" className="button button-primary" disabled={busy || !changed}>
        Save profile
      </button>
    </form>
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
    if (!window.confirm('Delete your account, your library and your presets for good?')) {
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
        Your library and presets are deleted. Songs nobody else has are deleted from the server.
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

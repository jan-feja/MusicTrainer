import { type FormEvent, type ReactNode, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { paths } from '../../app/paths'
import { errorMessage } from '../../lib/format'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { useAuth } from './authContext'
import styles from './auth.module.css'

const USERNAME_PATTERN = '[A-Za-z0-9_.\\-]{3,30}'
export const MIN_PASSWORD_LENGTH = 8

export function LoginPage() {
  useDocumentTitle('Log in')
  const { login } = useAuth()
  return (
    <CredentialsForm
      title="Log in"
      submitLabel="Log in"
      onSubmit={login}
      footer={
        <>
          No account yet? <Link to={paths.register}>Register</Link>
        </>
      }
    />
  )
}

export function RegisterPage() {
  useDocumentTitle('Register')
  const { register } = useAuth()
  return (
    <CredentialsForm
      title="Create an account"
      submitLabel="Register"
      onSubmit={register}
      isNewAccount
      footer={
        <>
          Have an account? <Link to={paths.login}>Log in</Link>
        </>
      }
    />
  )
}

interface CredentialsFormProps {
  title: string
  submitLabel: string
  onSubmit: (username: string, password: string) => Promise<void>
  isNewAccount?: boolean
  footer: ReactNode
}

function CredentialsForm({
  title,
  submitLabel,
  onSubmit,
  isNewAccount = false,
  footer,
}: CredentialsFormProps) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user && !busy) {
    return <Navigate to={paths.home} replace />
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await onSubmit(username, password)
      void navigate(paths.home, { replace: true })
    } catch (reason) {
      setError(errorMessage(reason))
      setBusy(false)
    }
  }

  return (
    <form className={styles.card} onSubmit={(event) => void submit(event)}>
      <h1 className={styles.title}>{title}</h1>
      <label className={styles.field}>
        <span>Username</span>
        <input
          className={styles.input}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          autoFocus
          required
          {...(isNewAccount && {
            pattern: USERNAME_PATTERN,
            title: '3–30 letters, digits, dots, dashes or underscores',
          })}
        />
        {isNewAccount && (
          <small className={styles.help}>3–30 letters, digits, “.”, “-” or “_”</small>
        )}
      </label>
      <label className={styles.field}>
        <span>Password</span>
        <input
          className={styles.input}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete={isNewAccount ? 'new-password' : 'current-password'}
          minLength={isNewAccount ? MIN_PASSWORD_LENGTH : undefined}
          required
        />
        {isNewAccount && (
          <small className={styles.help}>At least {MIN_PASSWORD_LENGTH} characters</small>
        )}
      </label>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <button type="submit" className="button button-primary" disabled={busy}>
        {submitLabel}
      </button>
      <p className={styles.note}>
        Songs, presets and settings you saved as a guest in this browser move into the account.
      </p>
      <p className={styles.footer}>{footer}</p>
    </form>
  )
}

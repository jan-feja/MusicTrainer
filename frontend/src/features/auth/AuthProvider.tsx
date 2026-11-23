import { type ReactNode, useCallback, useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { User } from '../../api/types'
import { StatusMessage } from '../../components/StatusMessage'
import { errorMessage } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { guestStorage } from '../library/guestStorage'
import { AuthContext, type AuthContextValue } from './authContext'

/**
 * Knows who is logged in. Nothing else is shown until that is known, so a
 * guest's library is never mixed up with an account's.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const loaded = useAsync((signal) => api.me(signal), 'me')
  // undefined: not changed on this page; the loaded user counts
  const [changedUser, setChangedUser] = useState<User | null | undefined>(undefined)

  const loggedIn = useCallback(async (user: User) => {
    await moveGuestLibraryInto()
    setChangedUser(user)
  }, [])

  const value = useMemo<AuthContextValue | null>(() => {
    if (loaded.status !== 'success') return null
    return {
      user: changedUser === undefined ? loaded.data : changedUser,
      login: async (username, password) => loggedIn(await api.login(username, password)),
      register: async (username, password) => loggedIn(await api.register(username, password)),
      logout: async () => {
        await api.logout()
        setChangedUser(null)
      },
      deleteAccount: async (password) => {
        await api.deleteAccount(password)
        setChangedUser(null)
      },
    }
  }, [loaded, changedUser, loggedIn])

  if (loaded.status === 'error') {
    return (
      <StatusMessage kind="error" onRetry={loaded.reload}>
        Could not reach the server: {errorMessage(loaded.error)}
      </StatusMessage>
    )
  }
  if (value === null) {
    return <StatusMessage kind="loading">Loading…</StatusMessage>
  }
  return <AuthContext value={value}>{children}</AuthContext>
}

/** The guest's songs, loops and settings go to the account; kept here if that fails. */
async function moveGuestLibraryInto(): Promise<void> {
  const entries = guestStorage.importEntries()
  if (entries.length === 0) return
  try {
    await api.importGuestLibrary(entries)
    guestStorage.clear()
  } catch (error) {
    console.warn('The guest library could not be moved into the account:', error)
  }
}

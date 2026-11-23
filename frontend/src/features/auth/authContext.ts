import { createContext, useContext } from 'react'
import type { User } from '../../api/types'

export interface AuthContextValue {
  /** The logged-in user; null for a guest. */
  user: User | null
  /** Log in; the guest's library in this browser moves into the account. */
  login: (username: string, password: string) => Promise<void>
  /** Create an account and log in; the guest's library moves into it. */
  register: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  /** Delete the account; afterwards the browser is a guest again. */
  deleteAccount: (password: string) => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (value === null) {
    throw new Error('useAuth() must be used inside <AuthProvider>')
  }
  return value
}

import { Link, NavLink, useNavigate } from 'react-router'
import { useAuth } from '../features/auth/authContext'
import { useActiveDownloadCount } from '../features/downloads/downloadsContext'
import { NotificationsButton } from '../features/profile/NotificationsButton'
import { SearchBox } from '../features/search/SearchBox'
import { paths } from './paths'
import styles from './Header.module.css'

export function Header() {
  const activeDownloads = useActiveDownloadCount()
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const logOut = () => {
    logout().then(
      () => void navigate(paths.home),
      (error: unknown) => window.alert(`Could not log out: ${String(error)}`),
    )
  }

  return (
    <header className={styles.header}>
      <Link to={paths.home} className={styles.brand}>
        <img src="/favicon.svg" alt="" width={28} height={28} />
        <span>Music Trainer</span>
      </Link>
      <SearchBox />
      <nav className={styles.nav} aria-label="Main">
        <NavLink to={paths.home} end className={styles.navLink}>
          Home
        </NavLink>
        <NavLink to={paths.library} className={styles.navLink}>
          Library
          {activeDownloads > 0 && (
            <span className={styles.badge} title={`${activeDownloads} download(s) running`}>
              {activeDownloads}
            </span>
          )}
        </NavLink>
        <NavLink to={paths.feed} className={styles.navLink}>
          Feed
        </NavLink>
      </nav>
      <nav className={styles.account} aria-label="Account">
        {user ? (
          <>
            <NotificationsButton />
            <NavLink
              to={paths.profile(user.username)}
              className={styles.navLink}
              title="Your profile"
            >
              {user.username}
            </NavLink>
            <button type="button" className="button button-small button-ghost" onClick={logOut}>
              Log out
            </button>
          </>
        ) : (
          <>
            <NavLink to={paths.login} className={styles.navLink}>
              Log in
            </NavLink>
            <Link to={paths.register} className="button button-small button-primary">
              Register
            </Link>
          </>
        )}
      </nav>
    </header>
  )
}

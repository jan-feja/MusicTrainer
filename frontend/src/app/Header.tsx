import { Link, NavLink } from 'react-router'
import { useActiveDownloadCount } from '../features/downloads/downloadsContext'
import { SearchBox } from '../features/search/SearchBox'
import { paths } from './paths'
import styles from './Header.module.css'

export function Header() {
  const activeDownloads = useActiveDownloadCount()

  return (
    <header className={styles.header}>
      <Link to={paths.library} className={styles.brand}>
        <img src="/favicon.svg" alt="" width={28} height={28} />
        <span>Music Trainer</span>
      </Link>
      <SearchBox />
      <nav className={styles.nav} aria-label="Main">
        <NavLink to={paths.library} end className={styles.navLink}>
          Library
          {activeDownloads > 0 && (
            <span className={styles.badge} title={`${activeDownloads} download(s) running`}>
              {activeDownloads}
            </span>
          )}
        </NavLink>
      </nav>
    </header>
  )
}

import { Route, Routes } from 'react-router'
import { useAuth } from '../features/auth/authContext'
import { LoginPage, RegisterPage } from '../features/auth/AuthPages'
import { ProfilePage } from '../features/auth/ProfilePage'
import { DownloadsProvider } from '../features/downloads/DownloadsProvider'
import { LibraryPage } from '../features/library/LibraryPage'
import { WatchPage } from '../features/player/WatchPage'
import { SearchPage } from '../features/search/SearchPage'
import { Header } from './Header'
import { NotFoundPage } from './NotFoundPage'
import { paths } from './paths'
import styles from './App.module.css'

export function App() {
  const { user } = useAuth()
  return (
    // logging in or out starts everything over with the other library
    <DownloadsProvider key={user ? `user:${user.id}` : 'guest'}>
      <div className={styles.app}>
        <Header />
        <main className={styles.main}>
          <Routes>
            <Route path={paths.library} element={<LibraryPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/watch/:videoId" element={<WatchPage />} />
            <Route path={paths.login} element={<LoginPage />} />
            <Route path={paths.register} element={<RegisterPage />} />
            <Route path={paths.profile} element={<ProfilePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
      </div>
    </DownloadsProvider>
  )
}

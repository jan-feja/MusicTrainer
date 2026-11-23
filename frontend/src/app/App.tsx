import { Route, Routes } from 'react-router'
import { useAuth } from '../features/auth/authContext'
import { LoginPage, RegisterPage } from '../features/auth/AuthPages'
import { SettingsPage } from '../features/auth/SettingsPage'
import { DownloadsProvider } from '../features/downloads/DownloadsProvider'
import { LibraryPage } from '../features/library/LibraryPage'
import { FeedPage } from '../features/profile/FeedPage'
import { FollowListPage } from '../features/profile/FollowListPage'
import { ProfilePage } from '../features/profile/ProfilePage'
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
            <Route path={paths.feed} element={<FeedPage />} />
            <Route path={paths.settings} element={<SettingsPage />} />
            <Route path="/u/:username" element={<ProfilePage />} />
            <Route path="/u/:username/followers" element={<FollowListPage list="followers" />} />
            <Route path="/u/:username/following" element={<FollowListPage list="following" />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
      </div>
    </DownloadsProvider>
  )
}

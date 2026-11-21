import { Route, Routes } from 'react-router'
import { LibraryPage } from '../features/library/LibraryPage'
import { WatchPage } from '../features/player/WatchPage'
import { SearchPage } from '../features/search/SearchPage'
import { Header } from './Header'
import { NotFoundPage } from './NotFoundPage'
import styles from './App.module.css'

export function App() {
  return (
    <div className={styles.app}>
      <Header />
      <main className={styles.main}>
        <Routes>
          <Route path="/" element={<LibraryPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/watch/:videoId" element={<WatchPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  )
}

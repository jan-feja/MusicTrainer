import { Link } from 'react-router'
import { api } from '../../api/client'
import type { LibraryVideo } from '../../api/types'
import { DeleteIcon } from '../../components/icons'
import { StatusMessage } from '../../components/StatusMessage'
import { VideoCard } from '../../components/VideoCard'
import { VideoGrid } from '../../components/VideoGrid'
import { errorMessage } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { useOnChange } from '../../lib/useOnChange'
import { DownloadList } from '../downloads/DownloadList'
import { useDownloads } from '../downloads/downloadsContext'
import styles from './LibraryPage.module.css'

export function LibraryPage() {
  const { completedCount, forgetDownload } = useDownloads()
  const videos = useAsync((signal) => api.listVideos(signal), 'library')
  useOnChange(completedCount, videos.reload)
  useDocumentTitle('Library')

  const deleteVideo = async (video: LibraryVideo) => {
    if (!window.confirm(`Delete “${video.title}” from your library?`)) return
    try {
      await api.deleteVideo(video.videoId)
      forgetDownload(video.videoId)
      videos.reload()
    } catch (error) {
      window.alert(`Could not delete the video: ${errorMessage(error)}`)
    }
  }

  return (
    <>
      <DownloadList />
      <h1 className={styles.heading}>Library</h1>
      {videos.status === 'loading' && (
        <StatusMessage kind="loading">Loading your library…</StatusMessage>
      )}
      {videos.status === 'error' && (
        <StatusMessage kind="error" onRetry={videos.reload}>
          {errorMessage(videos.error)}
        </StatusMessage>
      )}
      {videos.status === 'success' && videos.data.length === 0 && (
        <StatusMessage kind="info">
          Your library is empty. Search for a video above and download it; downloaded videos appear
          here. <Link to="/search">Search</Link>
        </StatusMessage>
      )}
      {videos.status === 'success' && videos.data.length > 0 && (
        <VideoGrid>
          {videos.data.map((video) => (
            <VideoCard
              key={video.videoId}
              videoId={video.videoId}
              title={video.title}
              channel={video.channel}
              durationSeconds={video.durationSeconds}
              thumbnailUrl={video.thumbnailUrl}
              actions={
                <button
                  type="button"
                  className="button button-small button-ghost"
                  onClick={() => void deleteVideo(video)}
                  aria-label={`Delete ${video.title}`}
                >
                  <DeleteIcon /> Delete
                </button>
              }
            />
          ))}
        </VideoGrid>
      )}
    </>
  )
}

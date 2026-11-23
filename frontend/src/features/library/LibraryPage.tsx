import { Link } from 'react-router'
import type { DownloadJob } from '../../api/types'
import { paths } from '../../app/paths'
import { DeleteIcon } from '../../components/icons'
import { StatusMessage } from '../../components/StatusMessage'
import { VideoCard } from '../../components/VideoCard'
import { VideoGrid } from '../../components/VideoGrid'
import { errorMessage } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { useOnChange } from '../../lib/useOnChange'
import { useDownloads } from '../downloads/downloadsContext'
import { DownloadingCard } from './DownloadingCard'
import { useMyLibrary } from './myLibrary'
import styles from './LibraryPage.module.css'

export function LibraryPage() {
  const { jobs, completedCount, startDownload, forgetDownload } = useDownloads()
  const library = useMyLibrary()
  const listing = useAsync((signal) => library.list(signal), 'library')
  useOnChange(completedCount, listing.reload)
  useDocumentTitle('Library')

  const removeVideo = async (videoId: string, title: string) => {
    if (!window.confirm(`Remove “${title}” and its saved loops from your library?`)) return
    try {
      await library.remove(videoId)
      forgetDownload(videoId)
      listing.reload()
    } catch (error) {
      window.alert(`Could not remove the video: ${errorMessage(error)}`)
    }
  }
  const retryDownload = (job: DownloadJob) => {
    startDownload(job.videoId, job.title ?? undefined).catch((error: unknown) =>
      window.alert(`Could not start the download: ${errorMessage(error)}`),
    )
  }

  const videos = listing.status === 'success' ? listing.data.videos : null
  // songs not on the server yet, newest first; a finished one stays until the list has it
  const listed = new Set(videos?.map((video) => video.videoId))
  const downloading = videos ? [...jobs.values()].filter((job) => !listed.has(job.videoId)) : []
  downloading.reverse()
  const isEmpty = videos?.length === 0 && downloading.length === 0

  return (
    <>
      <h1 className={styles.heading}>Library</h1>
      {library.isGuest && (
        <p className={styles.guestNote}>
          You are not logged in: your library is saved in this browser only, and songs nobody opens
          for a week are deleted from the server. <Link to={paths.register}>Register</Link> or{' '}
          <Link to={paths.login}>log in</Link> to keep it.
        </p>
      )}
      {listing.status === 'success' && listing.data.removedCount > 0 && (
        <StatusMessage kind="info">
          {listing.data.removedCount === 1
            ? 'A song was'
            : `${listing.data.removedCount} songs were`}{' '}
          deleted from the server because nobody opened them for a while.
        </StatusMessage>
      )}
      {listing.status === 'loading' && (
        <StatusMessage kind="loading">Loading your library…</StatusMessage>
      )}
      {listing.status === 'error' && (
        <StatusMessage kind="error" onRetry={listing.reload}>
          {errorMessage(listing.error)}
        </StatusMessage>
      )}
      {isEmpty && (
        <StatusMessage kind="info">
          Your library is empty. Search for a song above and add it; it appears here.{' '}
          <Link to="/search">Search</Link>
        </StatusMessage>
      )}
      {videos && !isEmpty && (
        <VideoGrid>
          {downloading.map((job) => (
            <DownloadingCard
              key={job.videoId}
              job={job}
              onRetry={() => retryDownload(job)}
              onRemove={() => void removeVideo(job.videoId, job.title ?? job.videoId)}
            />
          ))}
          {videos.map((video) => (
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
                  onClick={() => void removeVideo(video.videoId, video.title)}
                  aria-label={`Remove ${video.title} from your library`}
                >
                  <DeleteIcon /> Remove
                </button>
              }
            />
          ))}
        </VideoGrid>
      )}
    </>
  )
}

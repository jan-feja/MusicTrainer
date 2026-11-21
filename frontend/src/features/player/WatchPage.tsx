import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router'
import { api, isNotFoundError } from '../../api/client'
import type { WatchLocationState } from '../../app/paths'
import { NotFoundPage } from '../../app/NotFoundPage'
import { StatusMessage } from '../../components/StatusMessage'
import { errorMessage } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { useOnChange } from '../../lib/useOnChange'
import { isValidVideoId } from '../../lib/youtube'
import { useDownloadJob, useDownloads } from '../downloads/downloadsContext'
import { DownloadPanel } from './DownloadPanel'
import { VideoDetails } from './VideoDetails'
import { VideoPlayer } from './VideoPlayer'
import styles from './WatchPage.module.css'

export function WatchPage() {
  const { videoId = '' } = useParams()
  if (!isValidVideoId(videoId)) {
    return <NotFoundPage />
  }
  return <WatchVideo key={videoId} videoId={videoId} />
}

/** Plays a video from the library; a video not downloaded yet is downloaded first. */
function WatchVideo({ videoId }: { videoId: string }) {
  const location = useLocation()
  const titleFromLink = (location.state as WatchLocationState | null)?.title
  const { startDownload } = useDownloads()
  const job = useDownloadJob(videoId)
  const video = useAsync((signal) => api.getVideo(videoId, signal), videoId)
  const [startError, setStartError] = useState<string | null>(null)

  const isMissing = video.status === 'error' && isNotFoundError(video.error)
  const title =
    video.status === 'success' ? video.data.title : (job?.title ?? titleFromLink ?? null)
  useDocumentTitle(title)

  // once this video's download finishes, load it from the library
  useOnChange(job?.status === 'completed', video.reload)

  // opening a video that is not in the library starts its download, like pressing play
  useEffect(() => {
    if (isMissing && job === undefined) {
      startDownload(videoId, titleFromLink).catch((error: unknown) =>
        setStartError(errorMessage(error)),
      )
    }
  }, [isMissing, job, videoId, titleFromLink, startDownload])

  if (video.status === 'success') {
    return (
      <article className={styles.page}>
        <VideoPlayer
          key={video.data.videoId}
          src={video.data.mediaUrl}
          poster={video.data.thumbnailUrl ?? undefined}
        />
        <VideoDetails video={video.data} />
      </article>
    )
  }
  if (video.status === 'loading') {
    return <StatusMessage kind="loading">Loading…</StatusMessage>
  }
  if (!isMissing) {
    return (
      <StatusMessage kind="error" onRetry={video.reload}>
        {errorMessage(video.error)}
      </StatusMessage>
    )
  }

  const retry = () => {
    setStartError(null)
    startDownload(videoId, title ?? undefined).catch((error: unknown) =>
      setStartError(errorMessage(error)),
    )
  }
  return (
    <article className={styles.page}>
      <DownloadPanel
        videoId={videoId}
        title={title ?? 'Downloading video…'}
        job={job}
        error={startError}
        onRetry={retry}
      />
    </article>
  )
}

import type { DownloadJob } from '../../api/types'
import { DeleteIcon, DownloadIcon } from '../../components/icons'
import { ProgressBar } from '../../components/ProgressBar'
import { VideoCard } from '../../components/VideoCard'
import { describeJob } from '../downloads/downloadsState'
import styles from './LibraryPage.module.css'

interface DownloadingCardProps {
  job: DownloadJob
  onRetry: () => void
  onRemove: () => void
}

/** A song of the library that is not on the server yet, with its download's progress. */
export function DownloadingCard({ job, onRetry, onRemove }: DownloadingCardProps) {
  const title = job.title ?? job.videoId
  const failed = job.status === 'failed'
  return (
    <VideoCard
      videoId={job.videoId}
      title={title}
      channel={null}
      durationSeconds={null}
      thumbnailUrl={null}
      actions={
        <div className={styles.download} role="status">
          {!failed && <ProgressBar value={job.progress} label={`Downloading ${title}`} />}
          <span className={failed ? styles.downloadError : undefined}>{describeJob(job)}</span>
          {failed && (
            <div className={styles.buttons}>
              <button type="button" className="button button-small" onClick={onRetry}>
                <DownloadIcon /> Retry
              </button>
              <button
                type="button"
                className="button button-small button-ghost"
                onClick={onRemove}
                aria-label={`Remove ${title} from your library`}
              >
                <DeleteIcon /> Remove
              </button>
            </div>
          )}
        </div>
      }
    />
  )
}

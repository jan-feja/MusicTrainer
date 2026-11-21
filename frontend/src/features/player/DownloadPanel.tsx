import type { DownloadJob } from '../../api/types'
import { ProgressBar } from '../../components/ProgressBar'
import { youtubeThumbnailUrl } from '../../lib/youtube'
import { describeJob } from '../downloads/downloadsState'
import styles from './DownloadPanel.module.css'

interface DownloadPanelProps {
  videoId: string
  title: string
  job: DownloadJob | undefined
  /** Error from starting the download (e.g. server unreachable). */
  error: string | null
  onRetry: () => void
}

/** Shown in place of the player while the video is being downloaded. */
export function DownloadPanel({ videoId, title, job, error, onRetry }: DownloadPanelProps) {
  const failure = error ?? (job?.status === 'failed' ? job.error : null)

  return (
    <section className={styles.panel}>
      <div className={styles.poster}>
        <img src={youtubeThumbnailUrl(videoId)} alt="" />
        <div className={styles.overlay} role="status" aria-live="polite">
          {failure !== null ? (
            <>
              <p className={styles.error}>Download failed: {failure}</p>
              <button type="button" className="button button-primary" onClick={onRetry}>
                Try again
              </button>
            </>
          ) : (
            <>
              <p>{job ? describeJob(job) : 'Starting download…'}</p>
              <div className={styles.progress}>
                <ProgressBar value={job?.progress ?? 0} label="Download progress" />
              </div>
            </>
          )}
        </div>
      </div>
      <h1 className={styles.title}>{title}</h1>
      <p className={styles.hint}>
        Videos are saved to your library first and play as soon as the download finishes.
      </p>
    </section>
  )
}

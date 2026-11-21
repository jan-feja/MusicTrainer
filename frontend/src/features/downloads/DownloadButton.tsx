import { useState } from 'react'
import { CheckIcon, DownloadIcon } from '../../components/icons'
import { ProgressBar } from '../../components/ProgressBar'
import { errorMessage } from '../../lib/format'
import { useDownloadJob, useDownloads } from './downloadsContext'
import { describeJob, isActiveStatus } from './downloadsState'
import styles from './DownloadButton.module.css'

interface DownloadButtonProps {
  videoId: string
  title: string
  isDownloaded: boolean
}

/** Download button that turns into a progress bar while the download runs. */
export function DownloadButton({ videoId, title, isDownloaded }: DownloadButtonProps) {
  const { startDownload } = useDownloads()
  const job = useDownloadJob(videoId)
  const [requestError, setRequestError] = useState<string | null>(null)

  if (isDownloaded || job?.status === 'completed') {
    return (
      <span className={styles.done}>
        <CheckIcon /> In library
      </span>
    )
  }

  if (job && isActiveStatus(job.status)) {
    return (
      <div className={styles.progress} role="status">
        <ProgressBar value={job.progress} label={`Downloading ${title}`} />
        <span>{describeJob(job)}</span>
      </div>
    )
  }

  const start = () => {
    setRequestError(null)
    startDownload(videoId, title).catch((error: unknown) => setRequestError(errorMessage(error)))
  }
  const error = requestError ?? (job?.status === 'failed' ? job.error : null)

  return (
    <div>
      <button type="button" className="button" onClick={start}>
        <DownloadIcon /> {error ? 'Retry download' : 'Download'}
      </button>
      {error && <p className={styles.error}>{error}</p>}
    </div>
  )
}

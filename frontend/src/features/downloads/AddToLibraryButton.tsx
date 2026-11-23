import { useState } from 'react'
import { CheckIcon, DownloadIcon } from '../../components/icons'
import { ProgressBar } from '../../components/ProgressBar'
import { errorMessage } from '../../lib/format'
import { useMyLibrary } from '../library/myLibrary'
import { useDownloadJob, useDownloads } from './downloadsContext'
import { describeJob, isActiveStatus } from './downloadsState'
import styles from './AddToLibraryButton.module.css'

interface AddToLibraryButtonProps {
  videoId: string
  title: string
  /** Someone has the song on the server already: adding it is instant. */
  isOnServer: boolean
  /** The server says it is in the logged-in user's library. */
  inAccountLibrary: boolean
}

/**
 * Adds a song to the user's library; one not on the server yet is downloaded
 * first, and the button turns into a progress bar meanwhile.
 */
export function AddToLibraryButton({
  videoId,
  title,
  isOnServer,
  inAccountLibrary,
}: AddToLibraryButtonProps) {
  const { startDownload } = useDownloads()
  const library = useMyLibrary()
  const job = useDownloadJob(videoId)
  const [requestError, setRequestError] = useState<string | null>(null)

  if (job && isActiveStatus(job.status)) {
    return (
      <div className={styles.progress} role="status">
        <ProgressBar value={job.progress} label={`Downloading ${title}`} />
        <span>{describeJob(job)}</span>
      </div>
    )
  }

  // a guest's library has the song as soon as the download starts: show the progress first
  const failed = job?.status === 'failed'
  if (!failed && (library.has(videoId, inAccountLibrary) || job?.status === 'completed')) {
    return (
      <span className={styles.done}>
        <CheckIcon /> In library
      </span>
    )
  }

  const add = () => {
    setRequestError(null)
    startDownload(videoId, title).catch((error: unknown) => setRequestError(errorMessage(error)))
  }
  const error = requestError ?? (failed ? (job.error ?? 'Download failed') : null)

  return (
    <div>
      <button
        type="button"
        className="button"
        onClick={add}
        title={
          isOnServer
            ? 'Add to your library (already on the server: ready at once)'
            : 'Download and add to your library'
        }
      >
        <DownloadIcon /> {error ? 'Retry' : 'Add'}
      </button>
      {error && <p className={styles.error}>{error}</p>}
    </div>
  )
}

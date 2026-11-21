import { Link } from 'react-router'
import { paths } from '../../app/paths'
import { ProgressBar } from '../../components/ProgressBar'
import { useDownloads } from './downloadsContext'
import { describeJob } from './downloadsState'
import styles from './DownloadList.module.css'

/** Downloads that are running or failed. Renders nothing when there are none. */
export function DownloadList() {
  const { jobs } = useDownloads()
  const unfinished = [...jobs.values()].filter((job) => job.status !== 'completed')
  if (unfinished.length === 0) return null

  return (
    <section className={styles.section} aria-labelledby="downloads-heading">
      <h2 id="downloads-heading">Downloads</h2>
      <ul className={styles.list}>
        {unfinished.map((job) => (
          <li key={job.videoId} className={styles.item} data-status={job.status}>
            <Link to={paths.watch(job.videoId)} className={styles.title}>
              {job.title ?? job.videoId}
            </Link>
            {job.status !== 'failed' && <ProgressBar value={job.progress} />}
            <span className={styles.status}>{describeJob(job)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

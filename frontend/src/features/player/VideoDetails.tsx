import type { LibraryVideo } from '../../api/types'
import { formatDate, formatViewCount } from '../../lib/format'
import styles from './VideoDetails.module.css'

export function VideoDetails({ video }: { video: LibraryVideo }) {
  const meta = [
    video.channel,
    video.viewCount !== null ? formatViewCount(video.viewCount) : null,
    video.uploadDate !== null ? formatDate(video.uploadDate) : null,
  ].filter(Boolean)

  return (
    <section className={styles.details}>
      <h1 className={styles.title}>{video.title}</h1>
      <p className={styles.meta}>
        {meta.join(' · ')}
        {meta.length > 0 && ' · '}
        <a href={video.sourceUrl} target="_blank" rel="noreferrer">
          Open on YouTube
        </a>
      </p>
      {video.description && (
        <details className={styles.description}>
          <summary>Description</summary>
          <p>{video.description}</p>
        </details>
      )}
    </section>
  )
}

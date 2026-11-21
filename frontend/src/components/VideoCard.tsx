import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { type WatchLocationState, paths } from '../app/paths'
import { formatTime } from '../lib/format'
import { youtubeThumbnailUrl } from '../lib/youtube'
import styles from './VideoCard.module.css'

interface VideoCardProps {
  videoId: string
  title: string
  channel: string | null
  durationSeconds: number | null
  thumbnailUrl: string | null
  /** Extra text after the channel, e.g. the view count. */
  details?: string
  /** Buttons shown below the text. */
  actions?: ReactNode
}

export function VideoCard({
  videoId,
  title,
  channel,
  durationSeconds,
  thumbnailUrl,
  details,
  actions,
}: VideoCardProps) {
  const watchLink = paths.watch(videoId)
  const linkState: WatchLocationState = { title }
  const meta = [channel, details].filter(Boolean).join(' · ')

  return (
    <article className={styles.card}>
      <Link to={watchLink} state={linkState} className={styles.thumbnail} tabIndex={-1}>
        <img src={thumbnailUrl ?? youtubeThumbnailUrl(videoId)} alt="" loading="lazy" />
        {durationSeconds !== null && (
          <span className={styles.duration}>{formatTime(durationSeconds)}</span>
        )}
      </Link>
      <div className={styles.body}>
        <Link to={watchLink} state={linkState} className={styles.title}>
          {title}
        </Link>
        {meta && <p className={styles.meta}>{meta}</p>}
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </article>
  )
}

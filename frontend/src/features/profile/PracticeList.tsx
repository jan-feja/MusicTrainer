import { Link } from 'react-router'
import type { FeedEntry, PracticeEntry } from '../../api/types'
import { type WatchLocationState, paths } from '../../app/paths'
import { formatDay, formatDuration, formatTimeAgo } from '../../lib/format'
import { describeActivity } from './activity'
import { youtubeThumbnailUrl } from '../../lib/youtube'
import { UserAvatar } from './UserAvatar'
import styles from './Profile.module.css'

/** A user's history: the songs practiced and the presets made, grouped by day, newest first. */
export function PracticeHistory({ entries }: { entries: readonly PracticeEntry[] }) {
  const days: { day: string; entries: PracticeEntry[] }[] = []
  for (const entry of entries) {
    const last = days.at(-1)
    if (last?.day === entry.day) last.entries.push(entry)
    else days.push({ day: entry.day, entries: [entry] })
  }
  return (
    <div className={styles.days}>
      {days.map(({ day, entries: dayEntries }) => {
        const practiced = dayEntries.filter((entry) => entry.kind === 'practice')
        const total = practiced.reduce((sum, entry) => sum + entry.seconds, 0)
        return (
          <section key={day} className={styles.day}>
            <h3 className={styles.dayTitle}>
              {formatDay(day)}
              {practiced.length > 1 && (
                <span className={styles.dayTotal}>{formatDuration(total)}</span>
              )}
            </h3>
            <ul className={styles.practiceList}>
              {dayEntries.map((entry) => (
                <li key={entryKey(entry)} className={styles.practiceRow}>
                  <SongLink entry={entry} />
                  <span className={styles.practiceMeta}>
                    {entry.kind === 'preset'
                      ? `New preset “${entry.preset}”`
                      : formatDuration(entry.seconds)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

/** What people practiced and the presets they made: who, which song, how long, when. */
export function FeedList({ entries }: { entries: readonly FeedEntry[] }) {
  return (
    <ul className={styles.practiceList}>
      {entries.map((entry) => (
        <li key={`${entry.username}:${entryKey(entry)}`} className={styles.feedRow}>
          <Link to={paths.profile(entry.username)} className={styles.feedUser}>
            <UserAvatar username={entry.username} size={36} />
          </Link>
          <div className={styles.feedText}>
            <p className={styles.feedLine}>
              <Link to={paths.profile(entry.username)} className={styles.userName}>
                {entry.username}
              </Link>{' '}
              {describeActivity(entry)}
              <span className={styles.practiceMeta}> · {formatTimeAgo(entry.lastAt)}</span>
            </p>
            <SongLink entry={entry} />
          </div>
        </li>
      ))}
    </ul>
  )
}

function SongLink({ entry }: { entry: PracticeEntry }) {
  const state: WatchLocationState = { title: entry.title }
  return (
    <Link to={paths.watch(entry.videoId)} state={state} className={styles.song}>
      <img src={youtubeThumbnailUrl(entry.videoId)} alt="" loading="lazy" />
      <span className={styles.songTitle}>{entry.title}</span>
    </Link>
  )
}

function entryKey(entry: PracticeEntry): string {
  return `${entry.kind}:${entry.videoId}:${entry.day}:${entry.lastAt}`
}

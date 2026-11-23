import { type ReactNode, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, api } from '../../api/client'
import type { Profile } from '../../api/types'
import { paths } from '../../app/paths'
import { LockIcon } from '../../components/icons'
import { StatusMessage } from '../../components/StatusMessage'
import { VideoCard } from '../../components/VideoCard'
import { VideoGrid } from '../../components/VideoGrid'
import { errorMessage, formatDate, formatDuration } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { FollowButton } from './FollowButton'
import { PracticeHistory } from './PracticeList'
import { UserAvatar } from './UserAvatar'
import { PageFooter } from './PageFooter'
import { usePages } from './usePages'
import styles from './Profile.module.css'

/** Songs of the library shown before "Show all". */
const LIBRARY_PREVIEW = 8
const ALL_SONGS = 1000

/** A user's profile: who they are, their starred songs, library and practice history. */
export function ProfilePage() {
  const { username = '' } = useParams()
  const profile = useAsync((signal) => api.getProfile(username, signal), username)
  useDocumentTitle(profile.status === 'success' ? profile.data.username : username)

  if (profile.status === 'loading') return <StatusMessage kind="loading">Loading…</StatusMessage>
  if (profile.status === 'error') {
    const missing = profile.error instanceof ApiError && profile.error.status === 404
    return (
      <StatusMessage kind="error" onRetry={missing ? undefined : profile.reload}>
        {missing ? `There is no user ${username}.` : errorMessage(profile.error)}
      </StatusMessage>
    )
  }
  return <ProfileView key={profile.data.username} profile={profile.data} reload={profile.reload} />
}

function ProfileView({ profile, reload }: { profile: Profile; reload: () => void }) {
  const self = profile.followState === 'self'
  return (
    <div className={styles.profile}>
      <header className={styles.profileHeader}>
        <UserAvatar username={profile.username} size={72} />
        <div className={styles.profileText}>
          <h1 className={styles.profileName}>
            {profile.username}
            {profile.isPrivate && (
              <span className={styles.privateBadge} title="Only accepted followers see the songs">
                <LockIcon /> Private
              </span>
            )}
          </h1>
          {profile.description && <p className={styles.description}>{profile.description}</p>}
          <Stats profile={profile} />
        </div>
        <div className={styles.profileActions}>
          {self ? (
            <Link to={paths.settings} className="button button-small button-ghost">
              Settings
            </Link>
          ) : (
            <FollowButton
              username={profile.username}
              isPrivate={profile.isPrivate}
              state={profile.followState}
              onChange={reload}
            />
          )}
        </div>
      </header>

      {profile.canView ? (
        <>
          <Starred profile={profile} />
          <Library profile={profile} />
          <History profile={profile} />
        </>
      ) : (
        <div className={styles.locked}>
          <LockIcon />
          <p>
            {profile.username}’s profile is private.{' '}
            {profile.followState === 'requested'
              ? 'You asked to follow; you see the songs and practice once accepted.'
              : `Follow ${profile.username} to see their songs and practice.`}
          </p>
        </div>
      )}
    </div>
  )
}

function Stats({ profile }: { profile: Profile }) {
  const count = (n: number, word: string) => (
    <>
      <strong>{n}</strong> {word}
    </>
  )
  const followers = count(profile.followers, profile.followers === 1 ? 'follower' : 'followers')
  const following = count(profile.following, 'following')
  return (
    <p className={styles.stats}>
      {profile.canView ? (
        <>
          <Link to={paths.followers(profile.username)}>{followers}</Link>
          <Link to={paths.following(profile.username)}>{following}</Link>
        </>
      ) : (
        <>
          <span>{followers}</span>
          <span>{following}</span>
        </>
      )}
      {profile.practiceSeconds !== null && (
        <span>
          <strong>{formatDuration(profile.practiceSeconds)}</strong> practiced
        </span>
      )}
      <span>Joined {formatDate(profile.joinedAt)}</span>
    </p>
  )
}

function Section({
  title,
  aside,
  children,
}: {
  title: string
  aside?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  )
}

function Starred({ profile }: { profile: Profile }) {
  const { username } = profile
  const starred = useAsync((signal) => api.getUserStarred(username, signal), username)
  return (
    <Section title="Starred">
      {starred.status === 'loading' && <StatusMessage kind="loading">Loading…</StatusMessage>}
      {starred.status === 'error' && (
        <StatusMessage kind="error" onRetry={starred.reload}>
          {errorMessage(starred.error)}
        </StatusMessage>
      )}
      {starred.status === 'success' &&
        (starred.data.length === 0 ? (
          <p className={styles.empty}>
            {profile.followState === 'self'
              ? 'Star songs in your library or in the player to show them here.'
              : 'No starred songs yet.'}
          </p>
        ) : (
          <VideoGrid>
            {starred.data.map((video) => (
              <VideoCard
                key={video.videoId}
                videoId={video.videoId}
                title={video.title}
                channel={video.channel}
                durationSeconds={video.durationSeconds}
                thumbnailUrl={video.thumbnailUrl}
              />
            ))}
          </VideoGrid>
        ))}
    </Section>
  )
}

function Library({ profile }: { profile: Profile }) {
  const { username } = profile
  const self = profile.followState === 'self'
  const [all, setAll] = useState(false)
  const limit = all ? ALL_SONGS : LIBRARY_PREVIEW
  const library = useAsync(
    (signal) => api.getUserLibrary(username, limit, signal),
    `${username}:${limit}`,
  )
  const total = library.status === 'success' ? library.data.total : (profile.libraryCount ?? 0)
  const more = total > LIBRARY_PREVIEW && !all
  return (
    <Section
      title={`Library · ${total} ${total === 1 ? 'song' : 'songs'}`}
      aside={
        more &&
        (self ? (
          <Link to={paths.library}>Open your library</Link>
        ) : (
          <button
            type="button"
            className="button button-small button-ghost"
            onClick={() => setAll(true)}
          >
            Show all
          </button>
        ))
      }
    >
      {library.status === 'loading' && <StatusMessage kind="loading">Loading…</StatusMessage>}
      {library.status === 'error' && (
        <StatusMessage kind="error" onRetry={library.reload}>
          {errorMessage(library.error)}
        </StatusMessage>
      )}
      {library.status === 'success' &&
        (library.data.videos.length === 0 ? (
          <p className={styles.empty}>No songs yet.</p>
        ) : (
          <VideoGrid>
            {library.data.videos.map((video) => (
              <VideoCard
                key={video.videoId}
                videoId={video.videoId}
                title={video.title}
                channel={video.channel}
                durationSeconds={video.durationSeconds}
                thumbnailUrl={video.thumbnailUrl}
              />
            ))}
          </VideoGrid>
        ))}
    </Section>
  )
}

function History({ profile }: { profile: Profile }) {
  const { username } = profile
  const history = usePages(
    (before, signal) => api.getUserHistory(username, before, signal),
    username,
  )
  return (
    <Section title="History">
      {history.items.length > 0 && <PracticeHistory entries={history.items} />}
      {!history.loading && !history.error && history.items.length === 0 && (
        <p className={styles.empty}>
          {profile.followState === 'self'
            ? 'Songs you practice show up here, one entry per song and day.'
            : 'Nothing practiced yet.'}
        </p>
      )}
      <PageFooter pages={history} />
    </Section>
  )
}

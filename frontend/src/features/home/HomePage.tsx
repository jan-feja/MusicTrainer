import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { api } from '../../api/client'
import type { LibraryVideo } from '../../api/types'
import { paths } from '../../app/paths'
import { StatusMessage } from '../../components/StatusMessage'
import { VideoCard } from '../../components/VideoCard'
import { VideoGrid } from '../../components/VideoGrid'
import { errorMessage } from '../../lib/format'
import { type AsyncResult, useAsync } from '../../lib/useAsync'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { useAuth } from '../auth/authContext'
import { useMyLibrary } from '../library/myLibrary'
import { FeedList } from '../profile/PracticeList'
import { People } from './People'
import { shownCount, songRows, useColumnCount } from './grid'
import { Welcome } from './Welcome'
import styles from './HomePage.module.css'

const FEED_COUNT = 5
/** Enough for the rows on a wide screen; a row shows as many as fit. */
const SONG_COUNT = 16
const PEOPLE_COUNT = 12
/** The card widths and gaps of the grids (VideoGrid.module.css, .people in HomePage.module.css). */
const SONG_GRID = { minWidth: 260, gap: 16 }
const PEOPLE_GRID = { minWidth: 160, gap: 12 }

/** A bit of everything: a greeting, the latest of the feed, some of your songs, some of
 * everyone's, some of the people you follow and some to discover. */
export function HomePage() {
  useDocumentTitle('Home')
  const library = useMyLibrary()
  const feed = useAsync((signal) => api.getFeed('everyone', undefined, signal, FEED_COUNT), 'feed')
  const mine = useAsync((signal) => library.sample(SONG_COUNT, signal), 'mine')
  const others = useAsync((signal) => api.randomVideos(SONG_COUNT, signal), 'others')
  const people = useAsync((signal) => api.randomUsers(PEOPLE_COUNT, signal), 'people')
  const { user } = useAuth()
  const following = useAsync(
    (signal) => (user ? api.randomFollowing(PEOPLE_COUNT, signal) : Promise.resolve([])),
    'following',
  )

  return (
    <div className={styles.home}>
      <Welcome />

      <Section title="Lately" link={{ to: paths.feed, label: 'See the feed' }}>
        <Loaded
          result={feed}
          empty="Nobody has practiced yet. Open a song and play it: it shows up here."
        >
          {(entries) => <FeedList entries={entries} />}
        </Loaded>
      </Section>

      <Section title="From your library" link={{ to: paths.library, label: 'Open your library' }}>
        <Loaded
          result={mine}
          empty="Your library is empty. Search for a song above, or open one below: it appears here."
        >
          {(videos) => (
            <FullRows grid={SONG_GRID} items={videos} rows={songRows}>
              {(shown) => <Songs videos={shown} />}
            </FullRows>
          )}
        </Loaded>
      </Section>

      <Section title="Discover songs">
        <Loaded
          result={others}
          empty="No other songs yet. Search for one above: whatever people add shows up here."
        >
          {(videos) => (
            <FullRows grid={SONG_GRID} items={videos} rows={songRows}>
              {(shown) => <Songs videos={shown} />}
            </FullRows>
          )}
        </Loaded>
      </Section>

      {user && (
        <Section
          title="People you follow"
          link={{ to: paths.following(user.username), label: 'See everyone you follow' }}
        >
          <Loaded
            result={following}
            empty="You do not follow anyone yet. Find someone below or in the feed."
          >
            {(users) => (
              <FullRows grid={PEOPLE_GRID} items={users} rows={() => 1}>
                {(shown) => <People users={shown} state="following" />}
              </FullRows>
            )}
          </Loaded>
        </Section>
      )}

      <Section title="Discover people">
        <Loaded result={people} empty="Nobody new to discover right now.">
          {(users) => (
            <FullRows grid={PEOPLE_GRID} items={users} rows={() => 1}>
              {(shown) => <People users={shown} />}
            </FullRows>
          )}
        </Loaded>
      </Section>
    </div>
  )
}

interface SectionProps {
  title: string
  link?: { to: string; label: string }
  children: ReactNode
}

function Section({ title, link, children }: SectionProps) {
  return (
    <section className={styles.section} aria-label={title}>
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>{title}</h2>
        {link && (
          <Link to={link.to} className={styles.sectionLink}>
            {link.label} →
          </Link>
        )}
      </div>
      {children}
    </section>
  )
}

function Loaded<T>({
  result,
  empty,
  children,
}: {
  result: AsyncResult<readonly T[]>
  empty: ReactNode
  children: (items: readonly T[]) => ReactNode
}) {
  if (result.status === 'loading') return <StatusMessage kind="loading">Loading…</StatusMessage>
  if (result.status === 'error') {
    return (
      <StatusMessage kind="error" onRetry={result.reload}>
        {errorMessage(result.error)}
      </StatusMessage>
    )
  }
  if (result.data.length === 0) return <p className={styles.empty}>{empty}</p>
  return children(result.data)
}

/** As many of the items as fill `rows(columns)` rows of the grid, without a part row. */
function FullRows<T>({
  grid,
  items,
  rows,
  children,
}: {
  grid: { minWidth: number; gap: number }
  items: readonly T[]
  rows: (columns: number) => number
  children: (shown: readonly T[]) => ReactNode
}) {
  const [ref, columns] = useColumnCount(grid.minWidth, grid.gap)
  return (
    <div ref={ref}>
      {columns > 0 && children(items.slice(0, shownCount(items.length, columns, rows(columns))))}
    </div>
  )
}

function Songs({ videos }: { videos: readonly LibraryVideo[] }) {
  return (
    <VideoGrid>
      {videos.map((video) => (
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
  )
}

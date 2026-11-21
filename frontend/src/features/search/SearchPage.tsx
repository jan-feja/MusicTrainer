import { useSearchParams } from 'react-router'
import { api } from '../../api/client'
import type { SearchResult } from '../../api/types'
import { StatusMessage } from '../../components/StatusMessage'
import { VideoCard } from '../../components/VideoCard'
import { VideoGrid } from '../../components/VideoGrid'
import { errorMessage, formatViewCount } from '../../lib/format'
import { useAsync } from '../../lib/useAsync'
import { useDocumentTitle } from '../../lib/useDocumentTitle'
import { DownloadButton } from '../downloads/DownloadButton'

const noResults = (): Promise<SearchResult[]> => Promise.resolve([])

export function SearchPage() {
  const [searchParams] = useSearchParams()
  const query = (searchParams.get('q') ?? '').trim()
  const results = useAsync((signal) => (query ? api.search(query, signal) : noResults()), query)
  useDocumentTitle(query ? `${query} – Search` : 'Search')

  if (!query) {
    return (
      <StatusMessage kind="info">
        Type in the search box to find videos on YouTube, or paste a video link.
      </StatusMessage>
    )
  }
  if (results.status === 'loading') {
    return <StatusMessage kind="loading">Searching YouTube…</StatusMessage>
  }
  if (results.status === 'error') {
    return (
      <StatusMessage kind="error" onRetry={results.reload}>
        {errorMessage(results.error)}
      </StatusMessage>
    )
  }
  if (results.data.length === 0) {
    return <StatusMessage kind="info">No videos found for “{query}”.</StatusMessage>
  }

  return (
    <section aria-label={`Search results for ${query}`}>
      <VideoGrid>
        {results.data.map((result) => (
          <VideoCard
            key={result.videoId}
            videoId={result.videoId}
            title={result.title}
            channel={result.channel}
            durationSeconds={result.durationSeconds}
            thumbnailUrl={result.thumbnailUrl}
            details={result.viewCount !== null ? formatViewCount(result.viewCount) : undefined}
            actions={
              <DownloadButton
                videoId={result.videoId}
                title={result.title}
                isDownloaded={result.isDownloaded}
              />
            }
          />
        ))}
      </VideoGrid>
    </section>
  )
}

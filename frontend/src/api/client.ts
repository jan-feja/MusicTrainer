import type { DownloadJob, LibraryVideo, SearchResult } from './types'

const API_BASE = '/api'

/** The backend answered with an error status. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

/** FastAPI puts a readable message into `detail`. */
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof body.detail === 'string'
    ) {
      return body.detail
    }
  } catch {
    // the body is not JSON
  }
  return `Request failed (${response.status} ${response.statusText})`
}

function videoPath(videoId: string): string {
  return `/library/${encodeURIComponent(videoId)}`
}

export const api = {
  search(query: string, signal?: AbortSignal): Promise<SearchResult[]> {
    return request(`/search?${new URLSearchParams({ q: query })}`, { signal })
  },

  listVideos(signal?: AbortSignal): Promise<LibraryVideo[]> {
    return request('/library', { signal })
  },

  getVideo(videoId: string, signal?: AbortSignal): Promise<LibraryVideo> {
    return request(videoPath(videoId), { signal })
  },

  deleteVideo(videoId: string): Promise<void> {
    return request(videoPath(videoId), { method: 'DELETE' })
  },

  startDownload(videoId: string, title?: string): Promise<DownloadJob> {
    return request('/downloads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ videoId, title }),
    })
  },

  listDownloads(signal?: AbortSignal): Promise<DownloadJob[]> {
    return request('/downloads', { signal })
  },
}

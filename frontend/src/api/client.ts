import type {
  BeatGridHints,
  BeatTrackingState,
  ChordDetectionState,
  DownloadJob,
  LibraryVideo,
  PlayerSettings,
  SavedLoop,
  SearchResult,
  StemSeparationState,
} from './types'

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

  getBeats(videoId: string, signal?: AbortSignal): Promise<BeatTrackingState> {
    return request(`${videoPath(videoId)}/beats`, { signal })
  },

  /**
   * Start beat detection. `force` runs the beat network again even if a result
   * exists; `hints` only decodes the grid again with them (a few seconds).
   */
  detectBeats(
    videoId: string,
    options: { force?: boolean; hints?: BeatGridHints } = {},
  ): Promise<BeatTrackingState> {
    const query = options.force ? '?force=true' : ''
    return request(`${videoPath(videoId)}/beats${query}`, {
      method: 'POST',
      ...(options.hints && {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options.hints),
      }),
    })
  },

  getStems(videoId: string, signal?: AbortSignal): Promise<StemSeparationState> {
    return request(`${videoPath(videoId)}/stems`, { signal })
  },

  /** Start separating the video into stems; `force` separates again even if stems exist. */
  separateStems(videoId: string, options: { force?: boolean } = {}): Promise<StemSeparationState> {
    const query = options.force ? '?force=true' : ''
    return request(`${videoPath(videoId)}/stems${query}`, { method: 'POST' })
  },

  /** Where one stem's audio (FLAC) is served. */
  stemUrl(videoId: string, name: string): string {
    return `${API_BASE}${videoPath(videoId)}/stems/${encodeURIComponent(name)}`
  },

  getChords(videoId: string, signal?: AbortSignal): Promise<ChordDetectionState> {
    return request(`${videoPath(videoId)}/chords`, { signal })
  },

  /** Start chord detection (needs the beat grid: 409 before it is there). */
  detectChords(videoId: string, options: { force?: boolean } = {}): Promise<ChordDetectionState> {
    const query = options.force ? '?force=true' : ''
    return request(`${videoPath(videoId)}/chords${query}`, { method: 'POST' })
  },

  getLoops(videoId: string, signal?: AbortSignal): Promise<SavedLoop[]> {
    return request(`${videoPath(videoId)}/loops`, { signal })
  },

  /** `keepalive` lets the request finish while the page is being closed. */
  saveLoops(videoId: string, loops: SavedLoop[], keepalive = false): Promise<SavedLoop[]> {
    return request(`${videoPath(videoId)}/loops`, putJson(loops, keepalive))
  },

  getPlayerSettings(videoId: string, signal?: AbortSignal): Promise<PlayerSettings> {
    return request(`${videoPath(videoId)}/settings`, { signal })
  },

  savePlayerSettings(
    videoId: string,
    settings: PlayerSettings,
    keepalive = false,
  ): Promise<PlayerSettings> {
    return request(`${videoPath(videoId)}/settings`, putJson(settings, keepalive))
  },
}

function putJson(body: unknown, keepalive: boolean): RequestInit {
  return {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    keepalive,
  }
}

import type {
  BeatAnalysis,
  BeatGridHints,
  BeatTrackingState,
  ChordDetectionState,
  DownloadJob,
  GuestImportEntry,
  LibraryVideo,
  PlayerSettings,
  Preset,
  SearchResult,
  StemSeparationState,
  User,
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

/** The request needs an account (the user is a guest, or the login has expired). */
export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
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

/** A song in the logged-in user's own library. */
function myVideoPath(videoId: string): string {
  return `/me/library/${encodeURIComponent(videoId)}`
}

export const api = {
  search(query: string, signal?: AbortSignal): Promise<SearchResult[]> {
    return request(`/search?${new URLSearchParams({ q: query })}`, { signal })
  },

  /** The logged-in user; null for a guest. */
  me(signal?: AbortSignal): Promise<User | null> {
    return request('/auth/me', { signal })
  },

  /** Create an account and log in to it (409: the username is taken). */
  register(username: string, password: string): Promise<User> {
    return request('/auth/register', sendJson('POST', { username, password }))
  },

  /** 401: wrong username or password. */
  login(username: string, password: string): Promise<User> {
    return request('/auth/login', sendJson('POST', { username, password }))
  },

  logout(): Promise<void> {
    return request('/auth/logout', { method: 'POST' })
  },

  /** 403: the current password is wrong. Other browsers are logged out. */
  changePassword(currentPassword: string, newPassword: string): Promise<void> {
    return request('/auth/password', sendJson('POST', { currentPassword, newPassword }))
  },

  /** 403: the password is wrong. */
  deleteAccount(password: string): Promise<void> {
    return request('/auth/account', sendJson('DELETE', { password }))
  },

  /** A song on the server, whoever has it. */
  getVideo(videoId: string, signal?: AbortSignal): Promise<LibraryVideo> {
    return request(videoPath(videoId), { signal })
  },

  /** The logged-in user's library, most recently added first. */
  listMyVideos(signal?: AbortSignal): Promise<LibraryVideo[]> {
    return request('/me/library', { signal })
  },

  addToMyLibrary(videoId: string): Promise<void> {
    return request(myVideoPath(videoId), { method: 'PUT' })
  },

  /** The song is deleted from the server if nobody else has it. */
  removeFromMyLibrary(videoId: string): Promise<void> {
    return request(myVideoPath(videoId), { method: 'DELETE' })
  },

  /** Move a guest's library from the browser into the account. */
  importGuestLibrary(entries: GuestImportEntry[]): Promise<void> {
    return request('/me/library/import', sendJson('POST', entries))
  },

  startDownload(videoId: string, title?: string): Promise<DownloadJob> {
    return request('/downloads', sendJson('POST', { videoId, title }))
  },

  /** The downloads of the user's songs; a guest names theirs in `ids`. */
  listDownloads(ids?: readonly string[], signal?: AbortSignal): Promise<DownloadJob[]> {
    const query = ids ? `?${new URLSearchParams(ids.map((id) => ['ids', id]))}` : ''
    return request(`/downloads${query}`, { signal })
  },

  getBeats(videoId: string, signal?: AbortSignal): Promise<BeatTrackingState> {
    return request(`${videoPath(videoId)}/beats`, { signal })
  },

  /** Start beat detection; `force` runs the beat network again even if a result exists. */
  detectBeats(videoId: string, options: { force?: boolean } = {}): Promise<BeatTrackingState> {
    const query = options.force ? '?force=true' : ''
    return request(`${videoPath(videoId)}/beats${query}`, { method: 'POST' })
  },

  /** The user's own beat grid: the detected one with their fixes (a moment for new ones). */
  getBeatGrid(videoId: string, hints: BeatGridHints, signal?: AbortSignal): Promise<BeatAnalysis> {
    return request(`${videoPath(videoId)}/beats/grid`, { ...sendJson('POST', hints), signal })
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

  /** The chords on the beat grid `grid` (from a state detectChords returned). */
  getChords(videoId: string, grid: string, signal?: AbortSignal): Promise<ChordDetectionState> {
    const query = new URLSearchParams({ grid })
    return request(`${videoPath(videoId)}/chords?${query}`, { signal })
  },

  /**
   * Start chord detection on the user's beat grid, or get the chords if they
   * are there (needs the beats: 409 before they are detected).
   */
  detectChords(
    videoId: string,
    hints: BeatGridHints | null,
    signal?: AbortSignal,
  ): Promise<ChordDetectionState> {
    return request(`${videoPath(videoId)}/chords`, { ...sendJson('POST', hints), signal })
  },

  /** The user's presets for a song in their library. */
  getPresets(videoId: string, signal?: AbortSignal): Promise<Preset[]> {
    return request(`${myVideoPath(videoId)}/presets`, { signal })
  },

  /** `keepalive` lets the request finish while the page is being closed. */
  savePresets(videoId: string, presets: Preset[], keepalive = false): Promise<Preset[]> {
    return request(`${myVideoPath(videoId)}/presets`, putJson(presets, keepalive))
  },

  getPlayerSettings(videoId: string, signal?: AbortSignal): Promise<PlayerSettings> {
    return request(`${myVideoPath(videoId)}/settings`, { signal })
  },

  savePlayerSettings(
    videoId: string,
    settings: PlayerSettings,
    keepalive = false,
  ): Promise<PlayerSettings> {
    return request(`${myVideoPath(videoId)}/settings`, putJson(settings, keepalive))
  },
}

function sendJson(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

function putJson(body: unknown, keepalive: boolean): RequestInit {
  return { ...sendJson('PUT', body), keepalive }
}

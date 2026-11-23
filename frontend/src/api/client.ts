import type {
  FollowedPresets,
  BeatAnalysis,
  BeatGridHints,
  BeatTrackingState,
  ChordDetectionState,
  DownloadJob,
  FeedEntry,
  FeedScope,
  FollowState,
  GuestImportEntry,
  LibraryVideo,
  MyLibraryEntry,
  MyLibraryVideo,
  Notifications,
  PlayerSettings,
  PracticeEntry,
  Profile,
  ProfileLibrary,
  ProfileSettings,
  Preset,
  SearchResult,
  StemSeparationState,
  User,
  PracticeToday,
  UserSummary,
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
function userPath(username: string): string {
  return `/users/${encodeURIComponent(username)}`
}

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

  /** A few songs on the server, picked at random; for an account, ones not in its library. */
  randomVideos(count: number, signal?: AbortSignal): Promise<LibraryVideo[]> {
    return request(`/library/random?count=${count}`, { signal })
  },

  /** A few songs of the logged-in user's library, picked at random. */
  randomMyVideos(count: number, signal?: AbortSignal): Promise<MyLibraryVideo[]> {
    return request(`/me/library/random?count=${count}`, { signal })
  },

  /** The logged-in user's library, most recently added first. */
  listMyVideos(signal?: AbortSignal): Promise<MyLibraryVideo[]> {
    return request('/me/library', { signal })
  },

  /** A song's place in the user's library (404: not in it). */
  getMyEntry(videoId: string, signal?: AbortSignal): Promise<MyLibraryEntry> {
    return request(myVideoPath(videoId), { signal })
  },

  setStarred(videoId: string, starred: boolean): Promise<void> {
    return request(`${myVideoPath(videoId)}/star`, sendJson('PUT', { starred }))
  },

  /** The music of a song in the library played `seconds` more (the practice history). */
  reportPractice(videoId: string, seconds: number, keepalive = false): Promise<void> {
    return request('/me/practice', { ...sendJson('POST', { videoId, seconds }), keepalive })
  },

  /** How long the logged-in user practiced today (the day in UTC). */
  getPracticeToday(signal?: AbortSignal): Promise<PracticeToday> {
    return request('/me/practice/today', { signal })
  },

  getProfileSettings(signal?: AbortSignal): Promise<ProfileSettings> {
    return request('/me/profile', { signal })
  },

  saveProfileSettings(settings: ProfileSettings): Promise<ProfileSettings> {
    return request('/me/profile', sendJson('PUT', settings))
  },

  getNotifications(signal?: AbortSignal): Promise<Notifications> {
    return request('/me/notifications', { signal })
  },

  /** The user opened the notifications: none of them is unread any more. */
  markNotificationsSeen(): Promise<void> {
    return request('/me/notifications/seen', { method: 'POST' })
  },

  acceptFollower(username: string): Promise<void> {
    return request(`/me/followers/${encodeURIComponent(username)}`, { method: 'PUT' })
  },

  /** Decline a follow request, or remove a follower. */
  removeFollower(username: string): Promise<void> {
    return request(`/me/followers/${encodeURIComponent(username)}`, { method: 'DELETE' })
  },

  getProfile(username: string, signal?: AbortSignal): Promise<Profile> {
    return request(userPath(username), { signal })
  },

  /** 403 for a private profile the viewer may not see (also below). */
  getUserStarred(username: string, signal?: AbortSignal): Promise<LibraryVideo[]> {
    return request(`${userPath(username)}/starred`, { signal })
  },

  getUserLibrary(username: string, limit: number, signal?: AbortSignal): Promise<ProfileLibrary> {
    return request(`${userPath(username)}/library?limit=${limit}`, { signal })
  },

  /** `before`: the `lastAt` of the last entry of the previous page. */
  getUserHistory(
    username: string,
    before?: string,
    signal?: AbortSignal,
  ): Promise<PracticeEntry[]> {
    const query = before ? `?${new URLSearchParams({ before })}` : ''
    return request(`${userPath(username)}/history${query}`, { signal })
  },

  /** A few public profiles picked at random, leaving out the user and whom they follow. */
  randomUsers(count: number, signal?: AbortSignal): Promise<UserSummary[]> {
    return request(`/users?count=${count}`, { signal })
  },

  /** A few of the users the logged-in user follows, picked at random. */
  randomFollowing(count: number, signal?: AbortSignal): Promise<UserSummary[]> {
    return request(`/me/following/random?count=${count}`, { signal })
  },

  getFollowers(username: string, signal?: AbortSignal): Promise<UserSummary[]> {
    return request(`${userPath(username)}/followers`, { signal })
  },

  getFollowing(username: string, signal?: AbortSignal): Promise<UserSummary[]> {
    return request(`${userPath(username)}/following`, { signal })
  },

  /** Follow, or ask to follow a private profile ('requested'). */
  follow(username: string): Promise<FollowState> {
    return request(`${userPath(username)}/follow`, { method: 'PUT' })
  },

  /** Stop following, or take back the request. */
  unfollow(username: string): Promise<void> {
    return request(`${userPath(username)}/follow`, { method: 'DELETE' })
  },

  /** `before`: the `lastAt` of the last entry of the previous page. */
  getFeed(
    scope: FeedScope,
    before?: string,
    signal?: AbortSignal,
    limit?: number,
  ): Promise<FeedEntry[]> {
    const query = new URLSearchParams({
      scope,
      ...(before && { before }),
      ...(limit && { limit: String(limit) }),
    })
    return request(`/feed?${query}`, { signal })
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

  /** The presets of a song made by the users the user follows. */
  getFollowedPresets(videoId: string, signal?: AbortSignal): Promise<FollowedPresets[]> {
    return request(`${myVideoPath(videoId)}/followed-presets`, { signal })
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

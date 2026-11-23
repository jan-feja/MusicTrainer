/** URLs of the app's pages, in one place. */
export const paths = {
  library: '/',
  login: '/login',
  register: '/register',
  feed: '/feed',
  settings: '/settings',
  profile: (username: string) => `/u/${encodeURIComponent(username)}`,
  followers: (username: string) => `/u/${encodeURIComponent(username)}/followers`,
  following: (username: string) => `/u/${encodeURIComponent(username)}/following`,
  search: (query: string) => `/search?${new URLSearchParams({ q: query })}`,
  watch: (videoId: string) => `/watch/${encodeURIComponent(videoId)}`,
}

/** Sent along when opening a video, so its title shows before it is downloaded. */
export interface WatchLocationState {
  title?: string
}

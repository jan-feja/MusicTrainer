/** URLs of the app's pages, in one place. */
export const paths = {
  library: '/',
  search: (query: string) => `/search?${new URLSearchParams({ q: query })}`,
  watch: (videoId: string) => `/watch/${encodeURIComponent(videoId)}`,
}

/** Sent along when opening a video, so its title shows before it is downloaded. */
export interface WatchLocationState {
  title?: string
}

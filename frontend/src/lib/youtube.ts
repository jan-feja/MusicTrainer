const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/

export function isValidVideoId(value: string): boolean {
  return VIDEO_ID_PATTERN.test(value)
}

/** YouTube's own thumbnail, available before a video is downloaded. */
export function youtubeThumbnailUrl(videoId: string): string {
  return `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`
}

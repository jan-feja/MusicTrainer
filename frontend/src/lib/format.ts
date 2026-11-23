/** "3:07", or "1:02:03" from one hour on. */
export function formatTime(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secondsPart = String(seconds % 60).padStart(2, '0')
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${secondsPart}`
    : `${minutes}:${secondsPart}`
}

/** Like formatTime, with tenths of a second: "3:07.4". Used for loop points. */
export function formatTimePrecise(totalSeconds: number): string {
  const tenths = Math.max(0, Math.round(totalSeconds * 10))
  return `${formatTime(Math.floor(tenths / 10))}.${tenths % 10}`
}

const compactNumber = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })

/** "1 view", "950 views", "1.2M views" */
export function formatViewCount(views: number): string {
  return views === 1 ? '1 view' : `${compactNumber.format(views)} views`
}

const dateFormat = new Intl.DateTimeFormat('en', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
})

/** "2024-01-31" -> "Jan 31, 2024" */
export function formatDate(isoDate: string): string {
  return dateFormat.format(new Date(isoDate))
}

/** Practice time: "45 s", "12 min", "1 h 5 min". */
export function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.round(totalSeconds))
  if (seconds < 60) return `${seconds} s`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`
}

const MINUTE_MS = 60_000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

/** "just now", "5 min ago", "3 h ago", "yesterday", "Jan 31" (with the year if not this one). */
export function formatTimeAgo(iso: string, now = Date.now()): string {
  const time = new Date(iso).getTime()
  const ago = now - time
  if (ago < MINUTE_MS) return 'just now'
  if (ago < HOUR_MS) return `${Math.floor(ago / MINUTE_MS)} min ago`
  if (ago < DAY_MS) return `${Math.floor(ago / HOUR_MS)} h ago`
  if (ago < 2 * DAY_MS) return 'yesterday'
  return shortDate(time, now)
}

/** A practice day ("2024-01-31", UTC): "Today", "Yesterday", or "Wed, Jan 31". */
export function formatDay(day: string, now = Date.now()): string {
  const time = Date.parse(`${day}T00:00:00Z`)
  const today = Date.parse(`${new Date(now).toISOString().slice(0, 10)}T00:00:00Z`)
  const days = Math.round((today - time) / DAY_MS)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  const weekday = new Intl.DateTimeFormat('en', { weekday: 'short', timeZone: 'UTC' }).format(time)
  return `${weekday}, ${shortDate(time, now)}`
}

function shortDate(time: number, now: number): string {
  const sameYear = new Date(time).getUTCFullYear() === new Date(now).getUTCFullYear()
  return new Intl.DateTimeFormat('en', {
    month: 'short',
    day: 'numeric',
    ...(!sameYear && { year: 'numeric' }),
    timeZone: 'UTC',
  }).format(time)
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

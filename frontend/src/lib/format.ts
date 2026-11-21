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

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

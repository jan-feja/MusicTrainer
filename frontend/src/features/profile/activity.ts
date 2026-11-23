import type { PracticeEntry } from '../../api/types'
import { formatDuration } from '../../lib/format'

/** "practiced for 5 min", or "created new preset “Verse”". */
export function describeActivity(entry: PracticeEntry): string {
  return entry.kind === 'preset'
    ? `created new preset “${entry.preset}”`
    : `practiced for ${formatDuration(entry.seconds)}`
}

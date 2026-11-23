import type { PracticeEntry } from '../../api/types'
import { formatDuration } from '../../lib/format'

/** "practiced for 5 min", "created new preset “Verse”", or "commented “Nice groove”". */
export function describeActivity(entry: PracticeEntry): string {
  switch (entry.kind) {
    case 'preset':
      return `created new preset “${entry.preset}”`
    case 'comment':
      return `commented “${entry.comment}”`
    case 'practice':
      return `practiced for ${formatDuration(entry.seconds)}`
  }
}

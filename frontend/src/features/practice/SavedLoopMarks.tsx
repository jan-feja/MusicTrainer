import { memo } from 'react'
import type { SavedLoop } from '../../api/types'
import type { TimeView } from '../player/timelineView'
import styles from './SavedLoops.module.css'

interface SavedLoopMarksProps {
  view: TimeView
  loops: readonly SavedLoop[]
  /** Not marked: the timeline shows it as the current loop. */
  activeId: string | null
}

/** Thin marks above the timeline where the other saved loops are. */
export const SavedLoopMarks = memo(function SavedLoopMarks({
  view,
  loops,
  activeId,
}: SavedLoopMarksProps) {
  const length = view.end - view.start
  if (length <= 0) return null
  const percent = (time: number) => ((time - view.start) / length) * 100
  return (
    <div className={styles.marks} aria-hidden="true">
      {loops.map((loop) => {
        const start = Math.max(loop.start, view.start)
        const end = Math.min(loop.end, view.end)
        if (loop.id === activeId || end <= start) return null
        return (
          <span
            key={loop.id}
            className={styles.mark}
            style={{ left: `${percent(start)}%`, width: `${percent(end) - percent(start)}%` }}
          />
        )
      })}
    </div>
  )
})

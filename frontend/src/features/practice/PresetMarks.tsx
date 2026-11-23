import { memo } from 'react'
import type { Preset } from '../../api/types'
import type { TimeView } from '../player/timelineView'
import { presetLoop } from './presets'
import styles from './PresetMarks.module.css'

interface PresetMarksProps {
  view: TimeView
  presets: readonly Preset[]
  /** Not marked: the timeline shows it as the current loop. */
  activeId: string | null
}

/** Thin marks above the timeline where the loops of the other presets are. */
export const PresetMarks = memo(function PresetMarks({
  view,
  presets,
  activeId,
}: PresetMarksProps) {
  const length = view.end - view.start
  if (length <= 0) return null
  const percent = (time: number) => ((time - view.start) / length) * 100
  return (
    <div className={styles.marks} aria-hidden="true">
      {presets.map((preset) => {
        const loop = presetLoop(preset)
        if (!loop || preset.id === activeId) return null
        const start = Math.max(loop.start, view.start)
        const end = Math.min(loop.end, view.end)
        if (end <= start) return null
        return (
          <span
            key={preset.id}
            className={styles.mark}
            style={{ left: `${percent(start)}%`, width: `${percent(end) - percent(start)}%` }}
          />
        )
      })}
    </div>
  )
})

import { type CSSProperties, type PointerEvent, useRef, useState } from 'react'
import type { BeatAnalysis } from '../../api/types'
import { formatTimePrecise } from '../../lib/format'
import type { TimeView } from '../player/timelineView'
import { meanColor } from './drawMusic'
import { type SectionSpan, spanLabel } from './gridHints'
import type { MusicPicture } from './musicVisual'
import styles from './GridEditor.module.css'

interface SectionLaneProps {
  spans: SectionSpan[]
  view: TimeView
  /** Start of the selected span. */
  selected: number | null
  analysis: BeatAnalysis
  picture: MusicPicture | null
  /** Bar starts the user tapped or set. */
  barStarts: readonly number[]
  onSelect: (span: SectionSpan) => void
  /** A section start was dragged to `time` (and let go). */
  onMoveSection: (start: number, time: number) => void
  onRemoveBarStart: (time: number) => void
}

/**
 * The song's sections as blocks over the timeline: click one to edit it, drag its left edge
 * to move its start. Bar starts the user set show as yellow marks (click one to remove it).
 */
export function SectionLane({
  spans,
  view,
  selected,
  analysis,
  picture,
  barStarts,
  onSelect,
  onMoveSection,
  onRemoveBarStart,
}: SectionLaneProps) {
  const laneRef = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<{ start: number; time: number } | null>(null)
  const length = view.end - view.start
  const percent = (time: number) => ((time - view.start) / length) * 100
  const timeAt = (clientX: number) => {
    const rect = laneRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return view.start
    return view.start + ((clientX - rect.left) / rect.width) * length
  }

  const handlers = (start: number) => ({
    onPointerDown(event: PointerEvent<HTMLElement>) {
      if (event.button !== 0) return
      event.preventDefault()
      event.stopPropagation()
      event.currentTarget.setPointerCapture(event.pointerId)
      setDrag({ start, time: start })
    },
    onPointerMove(event: PointerEvent<HTMLElement>) {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        setDrag({ start, time: timeAt(event.clientX) })
      }
    },
    onPointerUp(event: PointerEvent<HTMLElement>) {
      event.currentTarget.releasePointerCapture(event.pointerId)
      if (drag && Math.abs(drag.time - start) > 0.02) onMoveSection(start, drag.time)
      setDrag(null)
    },
  })

  if (length <= 0) return null
  return (
    <div ref={laneRef} className={styles.sectionLane} role="list" aria-label="Sections">
      {spans.map((span) => {
        if (span.end <= view.start || span.start >= view.end) return null
        const moving = drag && span.section && drag.start === span.section.start
        const from = Math.max(view.start, moving ? drag.time : span.start)
        const to = Math.min(view.end, span.end)
        const label = spanLabel(span, analysis)
        const color = picture ? meanColor(picture, span.start, span.end) : null
        const isSelected = selected !== null && Math.abs(selected - span.start) < 1e-6
        return (
          <div
            key={span.start}
            role="listitem"
            className={styles.section}
            data-selected={isSelected}
            data-auto={label.auto}
            style={
              {
                left: `${percent(from)}%`,
                width: `${Math.max(0, percent(to) - percent(from))}%`,
                ...(color && { '--section-color': color }),
              } as CSSProperties
            }
          >
            <button
              type="button"
              className={styles.sectionBody}
              onClick={() => onSelect(span)}
              aria-pressed={isSelected}
              title={
                span.section
                  ? `Section from ${formatTimePrecise(span.start)}: ${label.text}`
                  : `Start of the song: ${label.text}`
              }
            >
              {label.text}
            </button>
            {span.section && span.start >= view.start && (
              <span
                className={styles.sectionEdge}
                {...handlers(span.section.start)}
                role="slider"
                aria-label={`Start of the section at ${formatTimePrecise(span.start)}`}
                aria-valuenow={span.start}
                title="Drag to move where the section starts"
              />
            )}
          </div>
        )
      })}
      {barStarts
        .filter((time) => time >= view.start && time <= view.end)
        .map((time) => (
          <button
            key={time}
            type="button"
            className={styles.barStartMark}
            style={{ left: `${percent(time)}%` }}
            onClick={() => onRemoveBarStart(time)}
            aria-label={`Bar start you set at ${formatTimePrecise(time)}; remove it`}
            title="A bar start you set: click to remove it"
          />
        ))}
    </div>
  )
}

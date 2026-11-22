import { type KeyboardEvent, type PointerEvent, useRef } from 'react'
import type { SavedLoop } from '../../api/types'
import { formatTimePrecise } from '../../lib/format'
import { clamp } from '../../lib/math'
import { type LoopState, getLoopRegion } from './loop'
import { type TimeView, clampView } from './timelineView'
import styles from './SeekBar.module.css'

/** Arrow keys on the overview move the view by this share of its length. */
const KEY_PAN_SHARE = 0.25

interface TimelineOverviewProps {
  duration: number
  view: TimeView
  currentTime: number
  loop: LoopState
  savedLoops: readonly SavedLoop[]
  onViewChange: (view: TimeView) => void
}

/**
 * The whole song under a zoomed timeline, with the shown part as a window:
 * drag the window to move it, click elsewhere to bring the window there.
 */
export function TimelineOverview({
  duration,
  view,
  currentTime,
  loop,
  savedLoops,
  onViewChange,
}: TimelineOverviewProps) {
  const ref = useRef<HTMLDivElement>(null)
  // where in the window it was grabbed, in seconds from its start
  const grab = useRef(0)
  const length = view.end - view.start
  const percent = (time: number) => (duration > 0 ? (time / duration) * 100 : 0)

  const timeAt = (clientX: number) => {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return 0
    return clamp((clientX - rect.left) / rect.width, 0, 1) * duration
  }
  const moveTo = (clientX: number) => {
    const start = timeAt(clientX) - grab.current
    onViewChange(clampView({ start, end: start + length }, duration))
  }

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    event.preventDefault()
    const time = timeAt(event.clientX)
    grab.current = time >= view.start && time <= view.end ? time - view.start : length / 2
    event.currentTarget.setPointerCapture(event.pointerId)
    moveTo(event.clientX)
  }
  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) moveTo(event.clientX)
  }
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    event.stopPropagation() // do not also seek the video
    const shift = (event.key === 'ArrowLeft' ? -1 : 1) * length * KEY_PAN_SHARE
    onViewChange(clampView({ start: view.start + shift, end: view.end + shift }, duration))
  }

  const region = getLoopRegion(loop)
  return (
    <div
      ref={ref}
      className={styles.overview}
      role="slider"
      tabIndex={0}
      aria-label="Shown part of the song"
      aria-valuemin={0}
      aria-valuemax={duration}
      aria-valuenow={view.start}
      aria-valuetext={`${formatTimePrecise(view.start)} to ${formatTimePrecise(view.end)}`}
      title="Drag to move the zoomed view; click to show that part"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={(event) => event.currentTarget.releasePointerCapture(event.pointerId)}
      onKeyDown={handleKeyDown}
    >
      {savedLoops.map((saved) => (
        <span
          key={saved.id}
          className={styles.overviewSaved}
          style={{
            left: `${percent(saved.start)}%`,
            width: `${percent(saved.end - saved.start)}%`,
          }}
        />
      ))}
      {region && (
        <span
          className={styles.overviewLoop}
          data-enabled={loop.enabled}
          style={{
            left: `${percent(region.start)}%`,
            width: `${percent(region.end - region.start)}%`,
          }}
        />
      )}
      <span className={styles.overviewPlayhead} style={{ left: `${percent(currentTime)}%` }} />
      <span
        className={styles.overviewWindow}
        style={{ left: `${percent(view.start)}%`, width: `${percent(length)}%` }}
      />
    </div>
  )
}

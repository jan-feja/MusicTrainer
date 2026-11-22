import { type KeyboardEvent, type ReactNode, useRef } from 'react'
import { formatTime, formatTimePrecise } from '../../lib/format'
import { clamp } from '../../lib/math'
import { type LoopState, getLoopRegion } from './loop'
import type { TimeView } from './timelineView'
import { usePointerDrag } from './usePointerDrag'
import { useWheelZoom } from './useWheelZoom'
import styles from './SeekBar.module.css'

interface SeekBarProps {
  currentTime: number
  duration: number
  /** The part of the song shown; the whole song unless zoomed. */
  view: TimeView
  loop: LoopState
  onSeek: (time: number) => void
  onMoveLoopStart: (time: number) => void
  onMoveLoopEnd: (time: number) => void
  /** Arrow keys on a focused handle: one step earlier (-1) or later (+1); Shift = bigger steps. */
  onNudgeLoopStart: (direction: -1 | 1, coarse: boolean) => void
  onNudgeLoopEnd: (direction: -1 | 1, coarse: boolean) => void
  /** Ctrl + wheel (or pinch): zoom by `factor` around the time under the pointer. */
  onZoom?: (factor: number, anchor: number) => void
  /** Shift + wheel (or sideways scrolling): move the view by `seconds`. */
  onPan?: (seconds: number) => void
  /** Drawn on the track, e.g. bar marks. */
  markers?: ReactNode
}

/** Timeline: click or drag to seek; drag the A / B handles to adjust the loop. */
export function SeekBar({
  currentTime,
  duration,
  view,
  loop,
  onSeek,
  onMoveLoopStart,
  onMoveLoopEnd,
  onNudgeLoopStart,
  onNudgeLoopEnd,
  onZoom,
  onPan,
  markers,
}: SeekBarProps) {
  const barRef = useRef<HTMLDivElement>(null)
  const length = view.end - view.start

  const timeAt = (clientX: number) => {
    const rect = barRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return view.start
    return view.start + clamp((clientX - rect.left) / rect.width, 0, 1) * length
  }
  const percent = (time: number) => (length > 0 ? ((time - view.start) / length) * 100 : 0)
  const inView = (time: number) => time >= view.start && time <= view.end

  const seekDrag = usePointerDrag((clientX) => onSeek(timeAt(clientX)))
  const startDrag = usePointerDrag((clientX) => onMoveLoopStart(timeAt(clientX)))
  const endDrag = usePointerDrag((clientX) => onMoveLoopEnd(timeAt(clientX)))
  useWheelZoom(barRef, view, duration, onZoom, onPan)

  const region = getLoopRegion(loop)
  const shownRegion = region && {
    start: Math.max(region.start, view.start),
    end: Math.min(region.end, view.end),
  }

  return (
    <div ref={barRef} className={styles.bar}>
      <div
        className={styles.track}
        role="slider"
        aria-label="Seek"
        aria-valuemin={0}
        aria-valuemax={duration}
        aria-valuenow={currentTime}
        aria-valuetext={formatTime(currentTime)}
        {...seekDrag}
      >
        {shownRegion && shownRegion.end > shownRegion.start && (
          <div
            className={styles.loopRegion}
            data-enabled={loop.enabled}
            style={{
              left: `${percent(shownRegion.start)}%`,
              width: `${percent(shownRegion.end) - percent(shownRegion.start)}%`,
            }}
          />
        )}
        <div
          className={styles.played}
          style={{ width: `${clamp(percent(currentTime), 0, 100)}%` }}
        />
        {markers}
        {inView(currentTime) && (
          <div className={styles.playhead} style={{ left: `${percent(currentTime)}%` }} />
        )}
      </div>
      {loop.start !== null && inView(loop.start) && (
        <LoopHandle
          label="A"
          description="Loop start"
          time={loop.start}
          duration={duration}
          position={percent(loop.start)}
          drag={startDrag}
          onNudge={onNudgeLoopStart}
        />
      )}
      {loop.end !== null && inView(loop.end) && (
        <LoopHandle
          label="B"
          description="Loop end"
          time={loop.end}
          duration={duration}
          position={percent(loop.end)}
          drag={endDrag}
          onNudge={onNudgeLoopEnd}
        />
      )}
    </div>
  )
}

interface LoopHandleProps {
  label: string
  description: string
  time: number
  duration: number
  /** Horizontal position in percent of the bar. */
  position: number
  drag: ReturnType<typeof usePointerDrag>
  onNudge: (direction: -1 | 1, coarse: boolean) => void
}

function LoopHandle({
  label,
  description,
  time,
  duration,
  position,
  drag,
  onNudge,
}: LoopHandleProps) {
  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      event.stopPropagation() // do not also seek the video
      onNudge(event.key === 'ArrowLeft' ? -1 : 1, event.shiftKey)
    }
  }

  return (
    <div
      className={styles.handle}
      style={{ left: `${position}%` }}
      role="slider"
      tabIndex={0}
      aria-label={description}
      aria-valuemin={0}
      aria-valuemax={duration}
      aria-valuenow={time}
      aria-valuetext={formatTimePrecise(time)}
      title={`${description}: ${formatTimePrecise(time)} (drag, or focus and use ← →)`}
      onKeyDown={handleKeyDown}
      {...drag}
    >
      {label}
    </div>
  )
}

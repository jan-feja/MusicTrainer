import { type KeyboardEvent, type ReactNode, type RefObject, useEffect, useRef } from 'react'
import { formatTime, formatTimePrecise } from '../../lib/format'
import { clamp } from '../../lib/math'
import { useLatest } from '../../lib/useLatest'
import { type LoopState, getLoopRegion } from './loop'
import type { TimeView } from './timelineView'
import { usePointerDrag } from './usePointerDrag'
import styles from './SeekBar.module.css'

/** Wheel sensitivity of the zoom: e^(0.002 per pixel scrolled). */
const WHEEL_ZOOM_RATE = 0.002

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

/**
 * Ctrl / Cmd + wheel (a pinch on a touchpad) zooms around the pointer; Shift +
 * wheel or sideways scrolling pans. A native listener, since React's wheel
 * listeners cannot stop the browser from zooming the page.
 */
function useWheelZoom(
  barRef: RefObject<HTMLDivElement | null>,
  view: TimeView,
  duration: number,
  onZoom?: (factor: number, anchor: number) => void,
  onPan?: (seconds: number) => void,
) {
  const latest = useLatest({ view, duration, onZoom, onPan })
  useEffect(() => {
    const bar = barRef.current
    if (!bar) return
    const handleWheel = (event: WheelEvent) => {
      const { view, duration, onZoom, onPan } = latest.current
      const rect = bar.getBoundingClientRect()
      if (rect.width === 0) return
      // Firefox scrolls in lines or pages
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.width : 1
      const length = view.end - view.start
      if ((event.ctrlKey || event.metaKey) && onZoom) {
        event.preventDefault()
        const anchor = view.start + clamp((event.clientX - rect.left) / rect.width, 0, 1) * length
        onZoom(Math.exp(event.deltaY * unit * WHEEL_ZOOM_RATE), anchor)
        return
      }
      const sideways = event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)
      if (sideways && onPan && length < duration) {
        event.preventDefault()
        const delta = (event.deltaX !== 0 ? event.deltaX : event.deltaY) * unit
        onPan((delta / rect.width) * length)
      }
    }
    bar.addEventListener('wheel', handleWheel, { passive: false })
    return () => bar.removeEventListener('wheel', handleWheel)
  }, [barRef, latest])
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

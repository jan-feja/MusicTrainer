import { type KeyboardEvent, useRef } from 'react'
import { formatTime, formatTimePrecise } from '../../lib/format'
import { clamp } from '../../lib/math'
import { LOOP_NUDGE_SECONDS, type LoopState, getLoopRegion } from './loop'
import { usePointerDrag } from './usePointerDrag'
import styles from './SeekBar.module.css'

interface SeekBarProps {
  currentTime: number
  duration: number
  loop: LoopState
  onSeek: (time: number) => void
  onMoveLoopStart: (time: number) => void
  onMoveLoopEnd: (time: number) => void
}

/** Timeline: click or drag to seek; drag the A / B handles to adjust the loop. */
export function SeekBar({
  currentTime,
  duration,
  loop,
  onSeek,
  onMoveLoopStart,
  onMoveLoopEnd,
}: SeekBarProps) {
  const barRef = useRef<HTMLDivElement>(null)

  const timeAt = (clientX: number) => {
    const rect = barRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return 0
    return clamp((clientX - rect.left) / rect.width, 0, 1) * duration
  }
  const percent = (time: number) => (duration > 0 ? (time / duration) * 100 : 0)

  const seekDrag = usePointerDrag((clientX) => onSeek(timeAt(clientX)))
  const startDrag = usePointerDrag((clientX) => onMoveLoopStart(timeAt(clientX)))
  const endDrag = usePointerDrag((clientX) => onMoveLoopEnd(timeAt(clientX)))
  const region = getLoopRegion(loop)

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
        {region && (
          <div
            className={styles.loopRegion}
            data-enabled={loop.enabled}
            style={{
              left: `${percent(region.start)}%`,
              width: `${percent(region.end - region.start)}%`,
            }}
          />
        )}
        <div className={styles.played} style={{ width: `${percent(currentTime)}%` }} />
        <div className={styles.playhead} style={{ left: `${percent(currentTime)}%` }} />
      </div>
      {loop.start !== null && (
        <LoopHandle
          label="A"
          description="Loop start"
          time={loop.start}
          duration={duration}
          position={percent(loop.start)}
          drag={startDrag}
          onMove={onMoveLoopStart}
        />
      )}
      {loop.end !== null && (
        <LoopHandle
          label="B"
          description="Loop end"
          time={loop.end}
          duration={duration}
          position={percent(loop.end)}
          drag={endDrag}
          onMove={onMoveLoopEnd}
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
  onMove: (time: number) => void
}

function LoopHandle({
  label,
  description,
  time,
  duration,
  position,
  drag,
  onMove,
}: LoopHandleProps) {
  const handleKeyDown = (event: KeyboardEvent) => {
    const step = event.shiftKey ? 1 : LOOP_NUDGE_SECONDS
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      event.stopPropagation() // do not also seek the video
      onMove(time + (event.key === 'ArrowLeft' ? -step : step))
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

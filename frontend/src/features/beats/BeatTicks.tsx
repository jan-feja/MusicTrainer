import { memo } from 'react'
import { type TimeView, visibleRange } from '../player/timelineView'
import styles from './BeatTicks.module.css'

interface BeatTicksProps {
  /** The part of the song the timeline shows. */
  view: TimeView
  bars: readonly number[]
  /** Beat marks are optional: on long stretches they are dense. */
  beats?: readonly number[]
  /** Number the bars (when they are far enough apart). */
  barNumbers?: boolean
}

/**
 * Bar (and beat) marks on the timeline, only those in view. Memoised: the seek
 * bar re-renders on every animation frame, these marks when the grid or the
 * view changes.
 */
export const BeatTicks = memo(function BeatTicks({
  view,
  bars,
  beats,
  barNumbers,
}: BeatTicksProps) {
  const length = view.end - view.start
  if (length <= 0) return null
  const position = (time: number) => ({ left: `${((time - view.start) / length) * 100}%` })
  const [firstBeat, lastBeat] = beats ? visibleRange(beats, view) : [0, 0]
  const [firstBar, lastBar] = visibleRange(bars, view)
  return (
    <div className={styles.ticks} aria-hidden="true">
      {beats?.slice(firstBeat, lastBeat).map((time) => (
        <span key={`beat-${time}`} className={styles.beat} style={position(time)} />
      ))}
      {bars.slice(firstBar, lastBar).map((time, index) => (
        <span key={`bar-${time}`} className={styles.bar} style={position(time)}>
          {barNumbers && <span className={styles.barNumber}>{firstBar + index + 1}</span>}
        </span>
      ))}
    </div>
  )
})

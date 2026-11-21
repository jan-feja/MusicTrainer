import { memo } from 'react'
import styles from './BeatTicks.module.css'

interface BeatTicksProps {
  duration: number
  bars: readonly number[]
  /** Beat marks are optional: on long songs they are dense. */
  beats?: readonly number[]
}

/**
 * Bar (and beat) marks on the timeline. Memoised: the seek bar re-renders on
 * every animation frame, these marks only when the grid changes.
 */
export const BeatTicks = memo(function BeatTicks({ duration, bars, beats }: BeatTicksProps) {
  if (duration <= 0) return null
  const position = (time: number) => ({ left: `${(time / duration) * 100}%` })
  return (
    <div className={styles.ticks} aria-hidden="true">
      {beats?.map((time) => (
        <span key={`beat-${time}`} className={styles.beat} style={position(time)} />
      ))}
      {bars.map((time) => (
        <span key={`bar-${time}`} className={styles.bar} style={position(time)} />
      ))}
    </div>
  )
})

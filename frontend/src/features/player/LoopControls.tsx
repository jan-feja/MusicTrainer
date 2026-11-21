import { LoopIcon } from '../../components/icons'
import { formatTimePrecise } from '../../lib/format'
import { LOOP_NUDGE_SECONDS, type LoopState, getLoopRegion } from './loop'
import styles from './PlayerControls.module.css'

interface LoopControlsProps {
  loop: LoopState
  onSetStart: () => void
  onSetEnd: () => void
  onMoveStart: (time: number) => void
  onMoveEnd: (time: number) => void
  onToggle: () => void
  onClear: () => void
}

export function LoopControls({
  loop,
  onSetStart,
  onSetEnd,
  onMoveStart,
  onMoveEnd,
  onToggle,
  onClear,
}: LoopControlsProps) {
  const region = getLoopRegion(loop)

  return (
    <div className={styles.group} role="group" aria-label="Loop">
      <span className={styles.groupLabel}>Loop</span>
      <button
        type="button"
        className="button button-small"
        onClick={onSetStart}
        title="Set loop start at the current position (A)"
      >
        Set A
      </button>
      <LoopPoint name="A" time={loop.start} onMove={onMoveStart} />
      <button
        type="button"
        className="button button-small"
        onClick={onSetEnd}
        title="Set loop end at the current position (B)"
      >
        Set B
      </button>
      <LoopPoint name="B" time={loop.end} onMove={onMoveEnd} />
      <button
        type="button"
        className="button button-small"
        onClick={onToggle}
        disabled={!region}
        aria-pressed={loop.enabled}
        title="Loop on / off (L)"
      >
        <LoopIcon /> {loop.enabled ? 'On' : 'Off'}
      </button>
      <button
        type="button"
        className="button button-small button-ghost"
        onClick={onClear}
        disabled={loop.start === null && loop.end === null}
        title="Clear loop (C)"
      >
        Clear
      </button>
      {region && (
        <span className={styles.loopLength}>{(region.end - region.start).toFixed(1)} s</span>
      )}
    </div>
  )
}

interface LoopPointProps {
  name: string
  time: number | null
  onMove: (time: number) => void
}

/** A loop point's time with buttons to nudge it earlier or later. */
function LoopPoint({ name, time, onMove }: LoopPointProps) {
  const nudge = `${LOOP_NUDGE_SECONDS * 1000} ms`
  return (
    <span className={styles.loopPoint}>
      <button
        type="button"
        className="icon-button icon-button-small"
        onClick={() => time !== null && onMove(time - LOOP_NUDGE_SECONDS)}
        disabled={time === null}
        aria-label={`Move ${name} ${nudge} earlier`}
      >
        ‹
      </button>
      <output className={styles.time} aria-label={`Loop point ${name}`}>
        {time === null ? '–:––.–' : formatTimePrecise(time)}
      </output>
      <button
        type="button"
        className="icon-button icon-button-small"
        onClick={() => time !== null && onMove(time + LOOP_NUDGE_SECONDS)}
        disabled={time === null}
        aria-label={`Move ${name} ${nudge} later`}
      >
        ›
      </button>
    </span>
  )
}

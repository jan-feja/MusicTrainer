import { LoopIcon } from '../../components/icons'
import { formatTimePrecise } from '../../lib/format'
import { type LoopState, getLoopRegion } from './loop'
import styles from './PlayerControls.module.css'

interface LoopControlsProps {
  loop: LoopState
  onSetStart: () => void
  onSetEnd: () => void
  /** Move a point one step earlier (-1) or later (+1). */
  onNudgeStart: (direction: -1 | 1) => void
  onNudgeEnd: (direction: -1 | 1) => void
  onToggle: () => void
  onClear: () => void
  /** Size of one nudge step, e.g. "50 ms" or "1 beat". */
  stepLabel: string
  /** Loop length, e.g. "7.5 s" or "4 bars"; null without a loop. */
  lengthLabel: string | null
}

export function LoopControls({
  loop,
  onSetStart,
  onSetEnd,
  onNudgeStart,
  onNudgeEnd,
  onToggle,
  onClear,
  stepLabel,
  lengthLabel,
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
      <LoopPoint name="A" time={loop.start} stepLabel={stepLabel} onNudge={onNudgeStart} />
      <button
        type="button"
        className="button button-small"
        onClick={onSetEnd}
        title="Set loop end at the current position (B)"
      >
        Set B
      </button>
      <LoopPoint name="B" time={loop.end} stepLabel={stepLabel} onNudge={onNudgeEnd} />
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
      {region && lengthLabel && <span className={styles.loopLength}>{lengthLabel}</span>}
    </div>
  )
}

interface LoopPointProps {
  name: string
  time: number | null
  stepLabel: string
  onNudge: (direction: -1 | 1) => void
}

/** A loop point's time with buttons to nudge it earlier or later. */
function LoopPoint({ name, time, stepLabel, onNudge }: LoopPointProps) {
  return (
    <span className={styles.loopPoint}>
      <button
        type="button"
        className="icon-button icon-button-small"
        onClick={() => onNudge(-1)}
        disabled={time === null}
        aria-label={`Move ${name} ${stepLabel} earlier`}
      >
        ‹
      </button>
      <output className={styles.time} aria-label={`Loop point ${name}`}>
        {time === null ? '–:––.–' : formatTimePrecise(time)}
      </output>
      <button
        type="button"
        className="icon-button icon-button-small"
        onClick={() => onNudge(1)}
        disabled={time === null}
        aria-label={`Move ${name} ${stepLabel} later`}
      >
        ›
      </button>
    </span>
  )
}

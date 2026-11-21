/**
 * A–B loop: the state and its rules, free of React so they are easy to test.
 *
 * Rules:
 * - A loop exists once both points are set; setting a point turns the loop on.
 * - Setting a point on the wrong side of the other point clears the other one.
 * - Dragging or nudging a point never crosses the other point.
 */
import { clamp } from '../../lib/math'

export interface LoopState {
  start: number | null
  end: number | null
  enabled: boolean
}

export interface LoopRegion {
  start: number
  end: number
}

export const EMPTY_LOOP: LoopState = { start: null, end: null, enabled: false }

/** Shortest loop, in seconds. */
export const MIN_LOOP_LENGTH = 0.1

/** How far the nudge buttons and arrow keys move a loop point, in seconds. */
export const LOOP_NUDGE_SECONDS = 0.05

export type LoopAction =
  | { type: 'setStart' | 'setEnd' | 'moveStart' | 'moveEnd'; time: number; duration: number }
  | { type: 'toggle' }
  | { type: 'clear' }

export function loopReducer(state: LoopState, action: LoopAction): LoopState {
  switch (action.type) {
    case 'setStart': {
      const start = clamp(action.time, 0, action.duration)
      const end = state.end !== null && state.end - start >= MIN_LOOP_LENGTH ? state.end : null
      return { start, end, enabled: end !== null }
    }
    case 'setEnd': {
      const end = clamp(action.time, 0, action.duration)
      const start =
        state.start !== null && end - state.start >= MIN_LOOP_LENGTH ? state.start : null
      return { start, end, enabled: start !== null }
    }
    case 'moveStart': {
      if (state.start === null) return state
      const latest = state.end !== null ? state.end - MIN_LOOP_LENGTH : action.duration
      return { ...state, start: clamp(action.time, 0, latest) }
    }
    case 'moveEnd': {
      if (state.end === null) return state
      const earliest = state.start !== null ? state.start + MIN_LOOP_LENGTH : 0
      return { ...state, end: clamp(action.time, earliest, action.duration) }
    }
    case 'toggle':
      return getLoopRegion(state) ? { ...state, enabled: !state.enabled } : state
    case 'clear':
      return EMPTY_LOOP
  }
}

export function getLoopRegion(state: LoopState): LoopRegion | null {
  return state.start !== null && state.end !== null ? { start: state.start, end: state.end } : null
}

/** The time playback should jump back to, or null to keep playing. */
export function loopJumpTarget(state: LoopState, currentTime: number): number | null {
  const region = getLoopRegion(state)
  return state.enabled && region && currentTime >= region.end ? region.start : null
}

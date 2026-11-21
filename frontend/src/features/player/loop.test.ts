import { describe, expect, it } from 'vitest'
import {
  EMPTY_LOOP,
  type LoopAction,
  type LoopState,
  MIN_LOOP_LENGTH,
  getLoopRegion,
  loopJumpTarget,
  loopReducer,
} from './loop'

const DURATION = 60

function apply(...actions: LoopAction[]): LoopState {
  return actions.reduce(loopReducer, EMPTY_LOOP)
}

const setStart = (time: number): LoopAction => ({ type: 'setStart', time, duration: DURATION })
const setEnd = (time: number): LoopAction => ({ type: 'setEnd', time, duration: DURATION })
const moveStart = (time: number): LoopAction => ({ type: 'moveStart', time, duration: DURATION })
const moveEnd = (time: number): LoopAction => ({ type: 'moveEnd', time, duration: DURATION })

describe('setting loop points', () => {
  it('turns the loop on once both points are set', () => {
    expect(apply(setStart(10))).toEqual({ start: 10, end: null, enabled: false })
    expect(apply(setStart(10), setEnd(20))).toEqual({ start: 10, end: 20, enabled: true })
  })

  it('works in either order', () => {
    expect(apply(setEnd(20), setStart(10))).toEqual({ start: 10, end: 20, enabled: true })
  })

  it('clears the other point when a point lands on its wrong side', () => {
    expect(apply(setStart(10), setEnd(20), setStart(25))).toEqual({
      start: 25,
      end: null,
      enabled: false,
    })
    expect(apply(setStart(10), setEnd(5))).toEqual({ start: null, end: 5, enabled: false })
  })

  it('rejects loops shorter than the minimum', () => {
    expect(apply(setStart(10), setEnd(10 + MIN_LOOP_LENGTH / 2)).start).toBeNull()
  })

  it('keeps points inside the video', () => {
    expect(apply(setStart(-3), setEnd(999))).toEqual({ start: 0, end: DURATION, enabled: true })
  })
})

describe('moving loop points', () => {
  it('never lets a point cross the other one', () => {
    const loop = apply(setStart(10), setEnd(20))
    expect(loopReducer(loop, moveStart(30)).start).toBeCloseTo(20 - MIN_LOOP_LENGTH)
    expect(loopReducer(loop, moveEnd(0)).end).toBeCloseTo(10 + MIN_LOOP_LENGTH)
  })

  it('moves freely inside the allowed range', () => {
    const loop = apply(setStart(10), setEnd(20))
    expect(loopReducer(loop, moveStart(12.5))).toEqual({ start: 12.5, end: 20, enabled: true })
  })

  it('ignores points that are not set', () => {
    expect(loopReducer(EMPTY_LOOP, moveStart(5))).toBe(EMPTY_LOOP)
  })
})

describe('toggle and clear', () => {
  it('toggles only an existing loop', () => {
    expect(loopReducer(apply(setStart(10)), { type: 'toggle' }).enabled).toBe(false)
    const off = loopReducer(apply(setStart(10), setEnd(20)), { type: 'toggle' })
    expect(off.enabled).toBe(false)
    expect(loopReducer(off, { type: 'toggle' }).enabled).toBe(true)
  })

  it('clears everything', () => {
    expect(loopReducer(apply(setStart(10), setEnd(20)), { type: 'clear' })).toEqual(EMPTY_LOOP)
  })
})

describe('loopJumpTarget', () => {
  const loop = apply(setStart(10), setEnd(20))

  it('jumps back to the start at the end of the loop', () => {
    expect(loopJumpTarget(loop, 20)).toBe(10)
    expect(loopJumpTarget(loop, 25)).toBe(10)
  })

  it('keeps playing inside or before the loop', () => {
    expect(loopJumpTarget(loop, 15)).toBeNull()
    expect(loopJumpTarget(loop, 3)).toBeNull()
  })

  it('does nothing when the loop is off or incomplete', () => {
    expect(loopJumpTarget({ ...loop, enabled: false }, 25)).toBeNull()
    expect(loopJumpTarget(apply(setStart(10)), 25)).toBeNull()
    expect(getLoopRegion(apply(setEnd(5)))).toBeNull()
  })
})

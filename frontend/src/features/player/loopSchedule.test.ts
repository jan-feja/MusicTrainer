import { describe, expect, it } from 'vitest'
import {
  type LoopSchedule,
  audioWindowFor,
  handoverTime,
  rescheduled,
  scheduledPosition,
  windowCovers,
} from './loopSchedule'

const LOOP: LoopSchedule = { at: 100, from: 10, rate: 1, start: 10, end: 14 }

describe('scheduledPosition', () => {
  it('plays from the start at the scheduled time', () => {
    expect(scheduledPosition(LOOP, 100)).toBe(10)
    expect(scheduledPosition(LOOP, 101.5)).toBe(11.5)
  })

  it('wraps at the loop end, pass after pass', () => {
    expect(scheduledPosition(LOOP, 104)).toBe(10)
    expect(scheduledPosition(LOOP, 105)).toBe(11)
    expect(scheduledPosition(LOOP, 100 + 4 * 25 + 3)).toBeCloseTo(13)
  })

  it('follows the rate', () => {
    const slow = { ...LOOP, rate: 0.5 }
    expect(scheduledPosition(slow, 102)).toBe(11)
    expect(scheduledPosition(slow, 108)).toBe(10)
  })

  it('reports the first position before the scheduled time', () => {
    expect(scheduledPosition(LOOP, 99)).toBe(10)
  })

  it('plays into the loop from a point before it', () => {
    const early = { ...LOOP, from: 8 }
    expect(scheduledPosition(early, 101)).toBe(9)
    expect(scheduledPosition(early, 106)).toBe(10)
  })
})

describe('rescheduled', () => {
  it('keeps the position when the rate changes', () => {
    const next = rescheduled(LOOP, 101, { rate: 0.5 })
    expect(next).toEqual({ at: 101, from: 11, rate: 0.5, start: 10, end: 14 })
    expect(scheduledPosition(next, 103)).toBe(12)
  })

  it('moves to a given position', () => {
    expect(rescheduled(LOOP, 101, {}, 13).from).toBe(13)
  })

  it('starts the loop over when the position falls outside it', () => {
    // the end moved before the playhead
    expect(rescheduled(LOOP, 103, { end: 12 }).from).toBe(10)
    // the start moved after the playhead
    expect(rescheduled(LOOP, 101, { start: 12 }).from).toBe(12)
  })
})

describe('audio windows', () => {
  it('adds margins within the media, on whole milliseconds', () => {
    expect(audioWindowFor({ start: 30.12345, end: 40 }, 300)).toEqual({ start: 20.123, end: 50 })
    expect(audioWindowFor({ start: 2, end: 295.0004 }, 300)).toEqual({ start: 0, end: 300 })
  })

  it('covers loops with room for the stretcher on both sides', () => {
    const window = { start: 20, end: 50 }
    expect(windowCovers(window, { start: 25, end: 45 }, 300)).toBe(true)
    expect(windowCovers(window, { start: 20.2, end: 45 }, 300)).toBe(false)
    expect(windowCovers(window, { start: 25, end: 49.8 }, 300)).toBe(false)
  })

  it('counts the start and end of the media as covered', () => {
    expect(windowCovers({ start: 0, end: 30 }, { start: 0, end: 10 }, 300)).toBe(true)
    // the audio track may end a little before the video
    expect(windowCovers({ start: 280, end: 299.8 }, { start: 290, end: 300 }, 300)).toBe(true)
  })
})

describe('handoverTime', () => {
  it('waits until the loop end is near', () => {
    expect(handoverTime(50, 10, 1, 14, 0.15, 0.3)).toBeNull()
  })

  it('schedules the takeover for when the video reaches the loop end', () => {
    expect(handoverTime(50, 13.8, 1, 14, 0.15, 0.3)).toBeCloseTo(50.2)
    // half speed: 0.1 s of song takes 0.2 s
    expect(handoverTime(50, 13.9, 0.5, 14, 0.15, 0.3)).toBeCloseTo(50.2)
  })

  it('takes over as soon as it can when the end is closer or passed', () => {
    expect(handoverTime(50, 13.95, 1, 14, 0.15, 0.3)).toBeCloseTo(50.15)
    expect(handoverTime(50, 20, 1, 14, 0.15, 0.3)).toBeCloseTo(50.15)
  })
})

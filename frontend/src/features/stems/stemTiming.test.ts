import { describe, expect, it } from 'vitest'
import { scheduledPosition } from '../player/loopSchedule'
import { semitonesFor, stemSchedule } from './stemTiming'

describe('stem timing', () => {
  it('plays on without a loop', () => {
    const schedule = stemSchedule(10, 30, 0.5, null)
    expect(scheduledPosition(schedule, 14)).toBeCloseTo(32)
  })

  it('loops the region and wraps like the audio source does', () => {
    const schedule = stemSchedule(0, 8, 1, { start: 10, end: 14 })
    expect(scheduledPosition(schedule, 5)).toBeCloseTo(13)
    expect(scheduledPosition(schedule, 7)).toBeCloseTo(11) // 15 wrapped into the loop
  })

  it('starts the loop over from at or after its end', () => {
    expect(stemSchedule(0, 14, 1, { start: 10, end: 14 }).from).toBe(10)
    expect(stemSchedule(0, 20, 1, { start: 10, end: 14 }).from).toBe(10)
  })

  it('shifts the pitch back after a speed change', () => {
    expect(semitonesFor(1)).toBeCloseTo(0)
    expect(semitonesFor(0.5)).toBeCloseTo(12)
    expect(semitonesFor(2)).toBeCloseTo(-12)
  })
})

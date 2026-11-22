import { describe, expect, it } from 'vitest'
import { dueClicks, firstBeatFrom, timeKey } from './clickTrack'

const BEATS = [1, 1.5, 2, 2.5, 3, 3.5]
const BARS = new Set([1, 3].map(timeKey))

describe('firstBeatFrom', () => {
  it.each([
    [0, 0],
    [1, 0],
    [1.2, 1],
    [3.5, 5],
    [4, 6],
  ])('time %s -> beat %s', (time, index) => {
    expect(firstBeatFrom(BEATS, time)).toBe(index)
  })
})

describe('dueClicks', () => {
  it('schedules the beats heard within the lookahead, accenting bar starts', () => {
    const { clicks, next } = dueClicks(BEATS, BARS, 0, 0.95, 1, 0.12)
    expect(clicks).toEqual([{ delay: expect.closeTo(0.05, 6), accent: true }])
    expect(next).toBe(1)
  })

  it('looks further in the song when it plays faster', () => {
    const { clicks } = dueClicks(BEATS, BARS, 1, 1.3, 2, 0.12)
    expect(clicks).toEqual([{ delay: expect.closeTo(0.1, 6), accent: false }])
  })

  it('does not schedule a beat twice, and skips beats already gone by', () => {
    const first = dueClicks(BEATS, BARS, 0, 0.95, 1, 0.12)
    expect(dueClicks(BEATS, BARS, first.next, 1.0, 1, 0.12).clicks).toEqual([])
    const late = dueClicks(BEATS, BARS, 2, 2.6, 1, 0.12)
    expect(late.clicks).toEqual([])
    expect(late.next).toBe(4)
  })
})

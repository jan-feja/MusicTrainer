import { describe, expect, it } from 'vitest'
import { stackRows } from './barRows'

const BARS = Array.from({ length: 101 }, (_, i) => i * 2) // 100 bars of 2 s

describe('stackRows', () => {
  it('lists the bars that start in the range, numbered from 1', () => {
    expect(stackRows(BARS, 10, 16, 0)).toEqual([
      { number: 6, start: 10, end: 12 },
      { number: 7, start: 12, end: 14 },
      { number: 8, start: 14, end: 16 },
    ])
  })

  it('shows at most `max` rows, around the focus', () => {
    const rows = stackRows(BARS, 0, 200, 100, 10)
    expect(rows).toHaveLength(10)
    expect(rows[0].number).toBe(46)
    expect(stackRows(BARS, 0, 200, 0, 10)[0].number).toBe(1)
    expect(stackRows(BARS, 0, 200, 1000, 10).at(-1)?.number).toBe(100)
  })
})

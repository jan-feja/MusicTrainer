import { describe, expect, it } from 'vitest'
import { shownCount, songRows } from './grid'

describe('songRows', () => {
  it('is two, more when the columns are few', () => {
    expect(songRows(5)).toBe(2)
    expect(songRows(3)).toBe(2)
    expect(songRows(2)).toBe(3)
    expect(songRows(1)).toBe(6)
  })
})

describe('shownCount', () => {
  it('shows only full rows', () => {
    expect(shownCount(16, 5, 2)).toBe(10)
    expect(shownCount(7, 5, 2)).toBe(5)
    expect(shownCount(12, 4, 2)).toBe(8)
  })

  it('shows what there is when it does not fill a row', () => {
    expect(shownCount(3, 5, 2)).toBe(3)
    expect(shownCount(0, 5, 2)).toBe(0)
  })
})

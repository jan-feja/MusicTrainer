import { describe, expect, it } from 'vitest'
import { formatPlaybackRate, normalizePlaybackRate, stepPlaybackRate } from './playbackRate'

describe('normalizePlaybackRate', () => {
  it.each([
    [1, 1],
    [0.8500000001, 0.85],
    [0.87, 0.85],
    [0.1, 0.25],
    [5, 2],
  ])('%s -> %s', (rate, expected) => {
    expect(normalizePlaybackRate(rate)).toBe(expected)
  })
})

describe('stepPlaybackRate', () => {
  it('moves in steps of 0.05 within the allowed range', () => {
    expect(stepPlaybackRate(1, -1)).toBe(0.95)
    expect(stepPlaybackRate(0.7, 3)).toBe(0.85)
    expect(stepPlaybackRate(0.25, -1)).toBe(0.25)
    expect(stepPlaybackRate(2, 1)).toBe(2)
  })
})

describe('formatPlaybackRate', () => {
  it('drops unneeded zeros', () => {
    expect(formatPlaybackRate(1)).toBe('1×')
    expect(formatPlaybackRate(0.5)).toBe('0.5×')
    expect(formatPlaybackRate(0.85)).toBe('0.85×')
  })
})

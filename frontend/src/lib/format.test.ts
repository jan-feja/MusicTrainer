import { describe, expect, it } from 'vitest'
import { formatDate, formatTime, formatTimePrecise, formatViewCount } from './format'

describe('formatTime', () => {
  it.each([
    [0, '0:00'],
    [7.9, '0:07'],
    [187, '3:07'],
    [3723, '1:02:03'],
    [-5, '0:00'],
  ])('%s s -> %s', (seconds, expected) => {
    expect(formatTime(seconds)).toBe(expected)
  })
})

describe('formatTimePrecise', () => {
  it.each([
    [0, '0:00.0'],
    [187.44, '3:07.4'],
    [59.96, '1:00.0'],
  ])('%s s -> %s', (seconds, expected) => {
    expect(formatTimePrecise(seconds)).toBe(expected)
  })
})

describe('formatViewCount', () => {
  it.each([
    [1, '1 view'],
    [950, '950 views'],
    [1234567, '1.2M views'],
  ])('%s -> %s', (views, expected) => {
    expect(formatViewCount(views)).toBe(expected)
  })
})

describe('formatDate', () => {
  it('formats ISO dates without shifting the day', () => {
    expect(formatDate('2005-04-24')).toBe('Apr 24, 2005')
  })
})

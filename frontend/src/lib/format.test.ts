import { describe, expect, it } from 'vitest'
import {
  formatDate,
  formatDay,
  formatDuration,
  formatTime,
  formatTimeAgo,
  formatTimePrecise,
  formatViewCount,
} from './format'

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

describe('formatDuration', () => {
  it.each([
    [45, '45 s'],
    [60, '1 min'],
    [749, '12 min'],
    [3600, '1 h'],
    [3900, '1 h 5 min'],
  ])('%s s -> %s', (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected)
  })
})

describe('formatTimeAgo / formatDay', () => {
  const now = Date.parse('2026-03-10T12:00:00Z')

  it.each([
    ['2026-03-10T11:59:30Z', 'just now'],
    ['2026-03-10T11:55:00Z', '5 min ago'],
    ['2026-03-10T09:00:00Z', '3 h ago'],
    ['2026-03-09T09:00:00Z', 'yesterday'],
    ['2026-03-01T09:00:00Z', 'Mar 1'],
    ['2025-12-24T09:00:00Z', 'Dec 24, 2025'],
  ])('%s -> %s', (iso, expected) => {
    expect(formatTimeAgo(iso, now)).toBe(expected)
  })

  it('names the days', () => {
    expect(formatDay('2026-03-10', now)).toBe('Today')
    expect(formatDay('2026-03-09', now)).toBe('Yesterday')
    expect(formatDay('2026-03-04', now)).toBe('Wed, Mar 4')
  })
})

import { describe, expect, it } from 'vitest'
import type { BeatAnalysis } from '../../api/types'
import {
  createBeatGrid,
  shiftedBarStarts,
  describeGridLength,
  gridPoints,
  isSnapMode,
  nearestIndex,
  nextSnapMode,
  snapRegion,
  snapToGrid,
  stepOnGrid,
  stepsBetween,
} from './beatGrid'

// 120 BPM, 4/4: beats every 0.5 s from 1.0 s, bars every 2 s
const BEATS = Array.from({ length: 16 }, (_, i) => 1 + i * 0.5)
const ANALYSIS: BeatAnalysis = {
  bpm: 120,
  beatsPerBar: 4,
  beats: BEATS,
  downbeats: [1, 3, 5, 7],
  analyzer: 'test',
  hints: { beatsPerBar: null, tempoBpm: null, barStarts: [] },
}

describe('nearestIndex', () => {
  it.each([
    [0, 0],
    [1.0, 0],
    [1.24, 0],
    [1.26, 1],
    [8.4, 15],
    [100, 15],
  ])('time %s -> index %s', (time, index) => {
    expect(nearestIndex(BEATS, time)).toBe(index)
  })

  it('returns -1 for an empty grid', () => {
    expect(nearestIndex([], 3)).toBe(-1)
  })
})

describe('snapping and stepping', () => {
  it('snaps to the nearest point', () => {
    expect(snapToGrid(BEATS, 2.2)).toBe(2)
    expect(snapToGrid([], 2.2)).toBe(2.2)
  })

  it('steps along the grid and stops at its ends', () => {
    expect(stepOnGrid(BEATS, 2.1, 1)).toBe(2.5)
    expect(stepOnGrid(BEATS, 2.1, -2)).toBe(1)
    expect(stepOnGrid(BEATS, 2.1, -10)).toBe(1)
    expect(stepOnGrid(BEATS, 8.4, 3)).toBe(8.5)
  })

  it('counts steps between two times', () => {
    expect(stepsBetween(BEATS, 1.0, 3.0)).toBe(4)
    expect(stepsBetween([1, 3, 5, 7], 1.1, 6.9)).toBe(3)
  })
})

describe('createBeatGrid', () => {
  it('uses the detected bar starts', () => {
    const grid = createBeatGrid(ANALYSIS)
    expect(grid.bars).toEqual([1, 3, 5, 7])
    expect(gridPoints(grid, 'beat')).toBe(BEATS)
    expect(gridPoints(grid, 'bar')).toEqual([1, 3, 5, 7])
  })
})

describe('shiftedBarStarts', () => {
  it('moves the bars from the one at the playhead on', () => {
    expect(shiftedBarStarts(ANALYSIS, 3.4, 1)).toEqual([3.5])
    expect(shiftedBarStarts(ANALYSIS, 5.0, -1)).toEqual([4.5])
  })

  it('wraps around at the first beat', () => {
    // a bar start one beat before the first beat: the next one comes a beat early
    expect(shiftedBarStarts(ANALYSIS, 0, -1)).toEqual([2.5])
  })

  it("keeps the user's other bar starts", () => {
    const fixed = { ...ANALYSIS, hints: { ...ANALYSIS.hints, barStarts: [1.5, 6.5] } }
    // the bar at 3.4 s starts at 3: bar starts before it and from the next bar (5 s) on stay
    expect(shiftedBarStarts(fixed, 3.4, 1)).toEqual([1.5, 3.5, 6.5])
  })
})

describe('snapRegion', () => {
  it('snaps both ends', () => {
    expect(snapRegion(BEATS, 1.9, 4.2)).toEqual({ start: 2, end: 4 })
  })

  it('keeps at least one step between the ends', () => {
    expect(snapRegion(BEATS, 2.1, 2.2)).toEqual({ start: 2, end: 2.5 })
    expect(snapRegion(BEATS, 8.4, 8.5)).toEqual({ start: 8, end: 8.5 })
  })

  it('needs at least two points', () => {
    expect(snapRegion([1], 0, 2)).toBeNull()
  })
})

describe('snap modes', () => {
  it('cycles off -> beat -> bar -> off', () => {
    expect(nextSnapMode('off')).toBe('beat')
    expect(nextSnapMode('beat')).toBe('bar')
    expect(nextSnapMode('bar')).toBe('off')
  })

  it('recognises stored values', () => {
    expect(isSnapMode('bar')).toBe(true)
    expect(isSnapMode('bars')).toBe(false)
    expect(isSnapMode(null)).toBe(false)
  })
})

describe('describeGridLength', () => {
  it.each([
    [1, 'bar', 4, '1 bar'],
    [4, 'bar', 4, '4 bars'],
    [1, 'beat', 4, '1 beat'],
    [6, 'beat', 4, '6 beats'],
    [16, 'beat', 4, '16 beats (4 bars)'],
    [16, 'beat', null, '16 beats'],
  ] as const)('%s %s (%s per bar) -> %s', (steps, unit, beatsPerBar, expected) => {
    expect(describeGridLength(steps, unit, beatsPerBar)).toBe(expected)
  })
})

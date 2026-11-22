import { describe, expect, it } from 'vitest'
import type { BeatAnalysis, BeatGridHints } from '../../api/types'
import {
  addBarStart,
  addSection,
  barLengthsBetween,
  describeBars,
  localBpm,
  moveSection,
  parsePattern,
  removeBarStart,
  removeSection,
  sameHints,
  sectionSpans,
  shiftSection,
  snapToBeat,
  spanAt,
  updateSection,
} from './gridHints'

const BEATS = Array.from({ length: 40 }, (_, i) => i * 0.5) // 120 BPM from 0 s
const HINTS: BeatGridHints = {
  beatsPerBar: null,
  tempoBpm: null,
  barStarts: [],
  steadyTempo: false,
  sections: [],
}

describe('sections', () => {
  it('start on the nearest beat and stay sorted', () => {
    let hints = addSection(HINTS, 10.2, BEATS)
    hints = addSection(hints, 3.9, BEATS)
    expect(hints.sections.map((s) => s.start)).toEqual([4, 10])
    expect(hints.sections[0]).toEqual({ start: 4, beatsPerBar: null, pattern: [], tempoBpm: null })
  })

  it('are not added twice at the same place', () => {
    const hints = addSection(HINTS, 10, BEATS)
    expect(addSection(hints, 10.1, BEATS)).toBe(hints)
  })

  it('can be changed and removed', () => {
    let hints = addSection(HINTS, 10, BEATS)
    hints = updateSection(hints, 10, { pattern: [6, 6, 5] })
    expect(hints.sections[0].pattern).toEqual([6, 6, 5])
    expect(removeSection(hints, 10).sections).toEqual([])
  })

  it('move by beats, but not past a neighbour', () => {
    let hints = addSection(addSection(HINTS, 4, BEATS), 10, BEATS)
    hints = shiftSection(hints, 10, -1, BEATS)
    expect(hints.sections.map((s) => s.start)).toEqual([4, 9.5])
    expect(moveSection(hints, 9.5, 3, BEATS)).toBe(hints)
    expect(moveSection(hints, 9.5, 6.1, BEATS).sections.map((s) => s.start)).toEqual([4, 6])
  })

  it('cover the song in spans', () => {
    const hints = addSection(addSection(HINTS, 4, BEATS), 10, BEATS)
    const spans = sectionSpans(hints, 20)
    expect(spans.map((s) => [s.start, s.end, s.section?.start ?? null])).toEqual([
      [0, 4, null],
      [4, 10, 4],
      [10, 20, 10],
    ])
    expect(spanAt(spans, 5)?.start).toBe(4)
    expect(spanAt(spans, 25)?.start).toBe(10)
    expect(sectionSpans(addSection(HINTS, 0, BEATS), 20)).toHaveLength(1)
  })
})

describe('bar starts', () => {
  it('snap to beats, sorted, once', () => {
    let hints = addBarStart(HINTS, 7.1, BEATS)
    hints = addBarStart(hints, 2.4, BEATS)
    expect(hints.barStarts).toEqual([2.5, 7])
    expect(addBarStart(hints, 7.02, BEATS)).toBe(hints)
    expect(removeBarStart(hints, 7.01).barStarts).toEqual([2.5])
  })

  it('stay where they are without beats', () => {
    expect(snapToBeat([], 3.3)).toBe(3.3)
  })
})

describe('parsePattern', () => {
  it.each([
    ['6+6+5+6+5+5', [6, 6, 5, 6, 5, 5]],
    ['3 3 2', [3, 3, 2]],
    [' 7 ', [7]],
    ['4,4,4,3', [4, 4, 4, 3]],
  ])('%s', (text, pattern) => {
    expect(parsePattern(text)).toEqual(pattern)
  })

  it.each(['', 'six', '6+0', '6+2.5', '17', Array(17).fill('3').join('+')])(
    'refuses %j',
    (text) => {
      expect(parsePattern(text)).toBeNull()
    },
  )
})

describe('describeBars', () => {
  it('shows what the user set', () => {
    const section = { start: 0, beatsPerBar: null, pattern: [], tempoBpm: null }
    expect(describeBars(null)).toBeNull()
    expect(describeBars(section)).toBeNull()
    expect(describeBars({ ...section, beatsPerBar: 7 })).toBe('7')
    expect(describeBars({ ...section, pattern: [6, 6, 5] })).toBe('6+6+5')
  })
})

describe('the grid in a range', () => {
  // bars of 4 beats until 8 s, then of 3
  const analysis: BeatAnalysis = {
    bpm: 120,
    beatsPerBar: 4,
    beats: BEATS,
    downbeats: [0, 2, 4, 6, 8, 9.5, 11, 12.5, 14],
    analyzer: 'test',
    hints: HINTS,
  }

  it('bar lengths, most common first', () => {
    expect(barLengthsBetween(analysis, 0, 8)).toEqual([4])
    expect(barLengthsBetween(analysis, 8, 20)).toEqual([3])
    expect(barLengthsBetween(analysis, 4, 20)).toEqual([3, 4])
  })

  it('tempo', () => {
    expect(localBpm(analysis, 0, 10)).toBeCloseTo(120)
    expect(localBpm(analysis, 0, 0.6)).toBeNull()
  })
})

describe('sameHints', () => {
  it('ignores sub-millisecond differences and section order', () => {
    const a = addSection(addSection(HINTS, 4, BEATS), 10, BEATS)
    const b = {
      ...a,
      sections: [...a.sections].reverse().map((s) => ({ ...s, start: s.start + 1e-5 })),
    }
    expect(sameHints(a, b)).toBe(true)
    expect(sameHints(a, HINTS)).toBe(false)
  })
})

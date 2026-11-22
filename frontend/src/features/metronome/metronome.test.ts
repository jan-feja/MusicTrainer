import { describe, expect, it } from 'vitest'
import type { BeatGrid } from '../beats/beatGrid'
import { metronomeDrift, metronomePosition, planMetronomeClicks } from './metronome'

const grid: BeatGrid = {
  beats: [1, 1.5, 2, 2.5, 3, 3.5, 4],
  bars: [1, 3],
  beatsPerBar: 4,
  bpm: 120,
}

describe('metronome click planning', () => {
  it('uses the detected beats and accents only bar starts', () => {
    expect(planMetronomeClicks(grid, 0.9, 1, 0, 1.2, null)).toEqual([
      { offset: expect.closeTo(0.1), accent: true },
      { offset: expect.closeTo(0.6), accent: false },
      { offset: expect.closeTo(1.1), accent: false },
    ])
  })

  it('follows playback speed and excludes the end of each scheduling window', () => {
    const first = planMetronomeClicks(grid, 1, 0.5, 0, 1, null)
    const next = planMetronomeClicks(grid, 1, 0.5, 1, 2, null)
    expect(first).toEqual([{ offset: 0, accent: true }])
    expect(next).toEqual([{ offset: 1, accent: false }])
    expect(planMetronomeClicks(grid, 1, 2, 0, 0.5, null)).toEqual([
      { offset: 0, accent: true },
      { offset: 0.25, accent: false },
    ])
  })

  it('repeats beats inside the actual loop, excluding the end, even on multiple wraps', () => {
    const loop = { start: 1, end: 2 }
    expect(planMetronomeClicks(grid, 1.75, 1, 0, 2.3, loop)).toEqual([
      { offset: 0.25, accent: true },
      { offset: 0.75, accent: false },
      { offset: 1.25, accent: true },
      { offset: 1.75, accent: false },
      { offset: 2.25, accent: true },
    ])
  })

  it('handles loops shifted before snapped beats, and the approach from before the loop', () => {
    const loop = { start: 0.97, end: 1.97 }
    const clicks = planMetronomeClicks(grid, 0.9, 1, 0, 2.2, loop)
    expect(clicks.map((click) => click.offset)).toEqual([
      expect.closeTo(0.1),
      expect.closeTo(0.6),
      expect.closeTo(1.07 + 0.03),
      expect.closeTo(1.6),
      expect.closeTo(2.1),
    ])
    expect(clicks.map((click) => click.accent)).toEqual([true, false, true, false, true])
  })

  it('does not drop or duplicate clicks when short scheduling windows cross loop boundaries', () => {
    const loop = { start: 0.97, end: 1.97 }
    const clicks = Array.from({ length: 160 }, (_, index) =>
      planMetronomeClicks(grid, 0.9, 1, index * 0.025, (index + 1) * 0.025, loop),
    ).flat()
    expect(clicks).toHaveLength(8)
    clicks.forEach((click, index) => {
      expect(click.offset).toBeCloseTo(0.1 + index * 0.5)
      expect(click.accent).toBe(index % 2 === 0)
    })
  })

  it('does not wrap when playback is already beyond the loop', () => {
    expect(planMetronomeClicks(grid, 3, 1, 0, 0.6, { start: 1, end: 2 })).toEqual([
      { offset: 0, accent: true },
      { offset: 0.5, accent: false },
    ])
  })

  it('compares positions across a loop boundary without treating a wrap as a large seek', () => {
    const loop = { start: 1, end: 2 }
    expect(metronomePosition(1.95, 0.1, loop)).toBeCloseTo(1.05)
    expect(metronomeDrift(1.01, 1.99, loop)).toBeCloseTo(0.02)
    expect(metronomeDrift(3, 1.99, loop)).toBeCloseTo(1.01)
  })
})

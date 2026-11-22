import { describe, expect, it } from 'vitest'
import type { SavedLoop } from '../../api/types'
import type { BeatGrid } from '../beats/beatGrid'
import {
  changedLoop,
  cleanLoopName,
  createLoop,
  describeLoop,
  newLoopId,
  nextLoopName,
  sortLoops,
} from './loopList'

const loop = (overrides: Partial<SavedLoop> = {}): SavedLoop => ({
  id: 'a',
  name: 'Loop 1',
  start: 10,
  end: 20,
  snapMode: 'off',
  playbackRate: 1,
  ...overrides,
})

describe('saved loops', () => {
  it('sorts loops in playing order', () => {
    const loops = [loop({ id: 'c', start: 30 }), loop({ id: 'b', start: 10, end: 15 }), loop()]
    expect(sortLoops(loops).map((l) => l.id)).toEqual(['b', 'a', 'c'])
  })

  it('makes ids the backend accepts', () => {
    const id = newLoopId()
    expect(id).toMatch(/^[A-Za-z0-9_-]{1,40}$/)
    expect(newLoopId()).not.toBe(id)
  })

  it('numbers new loops after the highest number', () => {
    expect(nextLoopName([])).toBe('Loop 1')
    expect(nextLoopName([loop({ name: 'Loop 3' }), loop({ name: 'Solo' })])).toBe('Loop 4')
    expect(nextLoopName([loop({ name: 'Intro' })])).toBe('Loop 1')
  })

  it('creates a loop from the current one', () => {
    const created = createLoop([loop()], { start: 5, end: 9 }, 'bar', 0.8)
    expect(created).toMatchObject({
      name: 'Loop 2',
      start: 5,
      end: 9,
      snapMode: 'bar',
      playbackRate: 0.8,
    })
  })

  it('reports only real changes', () => {
    expect(changedLoop(loop(), { start: 10, end: 20 })).toBeNull()
    expect(changedLoop(loop(), { end: 21 })).toEqual(loop({ end: 21 }))
  })

  it('cleans typed names', () => {
    expect(cleanLoopName('  Solo  ')).toBe('Solo')
    expect(cleanLoopName('   ')).toBeNull()
    expect(cleanLoopName('x'.repeat(150))).toHaveLength(100)
  })
})

describe('describeLoop', () => {
  const grid: BeatGrid = {
    beats: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    bars: [0, 4, 8, 12],
    beatsPerBar: 4,
    bpm: 60,
  }

  it('gives start, length and speed', () => {
    expect(describeLoop(loop({ start: 60.6, end: 66.95, playbackRate: 0.75 }), null)).toBe(
      '1:00.6 · 6.4 s · 0.75×',
    )
  })

  it('counts bars or beats on the grid', () => {
    expect(describeLoop(loop({ start: 4, end: 12, snapMode: 'bar' }), grid)).toBe('0:04.0 · 2 bars')
    expect(describeLoop(loop({ start: 4, end: 7, snapMode: 'beat' }), grid)).toBe(
      '0:04.0 · 3 beats',
    )
  })
})

import { describe, expect, it } from 'vitest'
import {
  MIN_VIEW_SECONDS,
  clampView,
  fitView,
  followPlayhead,
  isZoomed,
  panView,
  visibleRange,
  wholeView,
  zoomFactor,
  zoomView,
} from './timelineView'

const SONG = 200

describe('clampView', () => {
  it('keeps the view inside the song', () => {
    expect(clampView({ start: -5, end: 15 }, SONG)).toEqual({ start: 0, end: 20 })
    expect(clampView({ start: 190, end: 210 }, SONG)).toEqual({ start: 180, end: 200 })
  })

  it('never shows less than the minimum or more than the song', () => {
    expect(clampView({ start: 50, end: 50.2 }, SONG)).toEqual({
      start: 50,
      end: 50 + MIN_VIEW_SECONDS,
    })
    expect(clampView({ start: -100, end: 400 }, SONG)).toEqual({ start: 0, end: SONG })
  })

  it('handles songs shorter than the minimum and unknown durations', () => {
    expect(clampView({ start: 0, end: 5 }, 0.5)).toEqual({ start: 0, end: 0.5 })
    expect(clampView({ start: 0, end: 5 }, 0)).toEqual({ start: 0, end: 0 })
  })
})

describe('zooming', () => {
  it('zooms around the anchor, which stays at the same place', () => {
    const view = zoomView(wholeView(SONG), 0.5, 50, SONG)
    expect(view).toEqual({ start: 25, end: 125 })
    // 50 s was a quarter into the view before and still is
    expect((50 - view.start) / (view.end - view.start)).toBeCloseTo(0.25)
  })

  it('zooms out to the whole song at most', () => {
    expect(zoomView({ start: 20, end: 120 }, 4, 70, SONG)).toEqual({ start: 0, end: SONG })
  })

  it('knows whether and how far it is zoomed', () => {
    expect(isZoomed(wholeView(SONG), SONG)).toBe(false)
    expect(isZoomed({ start: 0, end: 50 }, SONG)).toBe(true)
    expect(zoomFactor({ start: 0, end: 50 }, SONG)).toBe(4)
  })

  it('pans within the song', () => {
    expect(panView({ start: 20, end: 40 }, 10, SONG)).toEqual({ start: 30, end: 50 })
    expect(panView({ start: 20, end: 40 }, -50, SONG)).toEqual({ start: 0, end: 20 })
  })
})

describe('fitView', () => {
  it('shows the loop over most of the timeline', () => {
    const view = fitView({ start: 60, end: 70 }, SONG)
    expect(view).toEqual({ start: 59, end: 71 })
    expect(10 / (view.end - view.start)).toBeCloseTo(0.83, 2)
  })

  it('shows short loops in at least the minimum view', () => {
    expect(fitView({ start: 60, end: 60.2 }, SONG)).toEqual({ start: 59.6, end: 60.6 })
  })

  it('stays inside the song', () => {
    expect(fitView({ start: 0, end: 10 }, SONG)).toEqual({ start: 0, end: 12 })
  })
})

describe('followPlayhead', () => {
  const view = { start: 40, end: 60 }

  it('moves on when the playhead runs off the right edge', () => {
    expect(followPlayhead(view, 59.9, 60.1, SONG)).toEqual({ start: 59.1, end: 79.1 })
  })

  it('stays while the playhead is in view or jumps back (a loop)', () => {
    expect(followPlayhead(view, 50, 50.1, SONG)).toBeNull()
    expect(followPlayhead(view, 59.9, 41, SONG)).toBeNull()
  })

  it('stays when the user moved the view away from the playhead', () => {
    expect(followPlayhead(view, 70, 70.1, SONG)).toBeNull()
  })
})

describe('visibleRange', () => {
  it('finds the times inside the view', () => {
    const times = [1, 2, 3, 4, 5, 6]
    expect(visibleRange(times, { start: 2.5, end: 5 })).toEqual([2, 5])
    expect(visibleRange(times, { start: 10, end: 20 })).toEqual([6, 6])
  })
})

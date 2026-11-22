import { describe, expect, it } from 'vitest'
import type { PlayerSettings, SavedLoop } from '../../api/types'
import { EMPTY_LOOP } from '../player/loop'
import { initialLoopState, storedPosition } from './playerSettings'

const SETTINGS: PlayerSettings = {
  volume: 1,
  muted: false,
  playbackRate: 1,
  snapMode: null,
  position: 0,
  loopStart: null,
  loopEnd: null,
  loopEnabled: false,
  activeLoopId: null,
}

const SAVED: SavedLoop = {
  id: 'a',
  name: 'Solo',
  start: 60,
  end: 66,
  snapMode: 'bar',
  playbackRate: 0.75,
}

describe('initialLoopState', () => {
  it('starts empty without settings', () => {
    expect(initialLoopState(null, null)).toEqual(EMPTY_LOOP)
  })

  it('takes the active saved loop', () => {
    expect(initialLoopState({ ...SETTINGS, loopEnabled: true }, SAVED)).toEqual({
      start: 60,
      end: 66,
      enabled: true,
    })
  })

  it('takes the loop that was set, on or off', () => {
    const settings = { ...SETTINGS, loopStart: 10, loopEnd: 20, loopEnabled: false }
    expect(initialLoopState(settings, null)).toEqual({ start: 10, end: 20, enabled: false })
    expect(initialLoopState({ ...settings, loopEnd: null, loopEnabled: true }, null)).toEqual({
      start: 10,
      end: null,
      enabled: false,
    })
  })

  it('drops an end that is not after the start', () => {
    const settings = { ...SETTINGS, loopStart: 10, loopEnd: 10, loopEnabled: true }
    expect(initialLoopState(settings, null)).toEqual({ start: 10, end: null, enabled: false })
  })
})

describe('storedPosition', () => {
  it('is the loop start while looping', () => {
    expect(storedPosition({ start: 60, end: 66, enabled: true }, 63.2, true)).toBe(60)
  })

  it('moves in coarse steps while playing', () => {
    expect(storedPosition(EMPTY_LOOP, 63.2, true)).toBe(60)
    expect(storedPosition({ start: 60, end: 66, enabled: false }, 4.9, true)).toBe(0)
  })

  it('is the paused position to the tenth of a second', () => {
    expect(storedPosition(EMPTY_LOOP, 47.3, false)).toBe(47.3)
    expect(storedPosition(EMPTY_LOOP, 47.36, false)).toBe(47.4)
  })
})

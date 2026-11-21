import { describe, expect, it } from 'vitest'
import { PLAYER_SHORTCUTS, findShortcut } from './shortcuts'

describe('findShortcut', () => {
  it.each([
    [' ', 'togglePlay'],
    ['K', 'togglePlay'],
    ['ArrowLeft', 'seekBackward'],
    ['>', 'faster'],
    ['A', 'setLoopStart'],
    ['l', 'toggleLoop'],
  ])('%j -> %s', (key, id) => {
    expect(findShortcut(key)).toBe(id)
  })

  it('ignores other keys', () => {
    expect(findShortcut('x')).toBeUndefined()
    expect(findShortcut('Enter')).toBeUndefined()
  })

  it('assigns every key only once', () => {
    const keys = PLAYER_SHORTCUTS.flatMap((s) => [...s.keys])
    expect(new Set(keys).size).toBe(keys.length)
  })
})

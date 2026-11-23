import { describe, expect, it } from 'vitest'
import { PracticeCounter } from './usePracticeTime'

describe('PracticeCounter', () => {
  it('counts only while playing and hands out whole seconds once', () => {
    let now = 0
    const counter = new PracticeCounter(() => now)
    counter.start()
    now = 12_500
    expect(counter.take(30)).toBeNull() // not enough yet
    counter.stop()
    now = 60_000 // paused: not counted
    counter.start()
    now = 80_000
    expect(counter.take(30)).toBe(32)
    now = 80_900
    expect(counter.take(1)).toBe(1) // 0.5 left over + 0.9
    expect(counter.take(1)).toBeNull()
  })
})

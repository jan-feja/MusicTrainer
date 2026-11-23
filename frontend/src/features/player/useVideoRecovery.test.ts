import { describe, expect, it } from 'vitest'
import { reloadPosition } from './useVideoRecovery'

describe('reloadPosition', () => {
  it('reloads where the video was on a first failure', () => {
    expect(reloadPosition(8.7, [], 1000)).toBe(8.7)
  })

  it('starts a little later after each recent failure', () => {
    expect(reloadPosition(8.7, [500], 1000)).toBe(9.2)
    expect(reloadPosition(8.7, [400, 500], 1000)).toBeCloseTo(9.7)
  })

  it('gives up after three recent failures', () => {
    expect(reloadPosition(8.7, [300, 400, 500], 1000)).toBeNull()
  })

  it('forgets failures older than 30 s', () => {
    expect(reloadPosition(8.7, [0, 1, 2], 40_000)).toBe(8.7)
  })
})

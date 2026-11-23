import { describe, expect, it } from 'vitest'
import type { PracticeEntry } from '../../api/types'
import { describeActivity } from './activity'

const entry = (kind: PracticeEntry['kind'], seconds: number, preset: string | null) => ({
  kind,
  videoId: 'abcdefghijk',
  title: 'Song',
  day: '2026-11-23',
  lastAt: '2026-11-23T10:00:00Z',
  seconds,
  preset,
})

describe('describeActivity', () => {
  it('names the practice time or the new preset', () => {
    expect(describeActivity(entry('practice', 300, null))).toBe('practiced for 5 min')
    expect(describeActivity(entry('preset', 0, 'Verse'))).toBe('created new preset “Verse”')
  })
})

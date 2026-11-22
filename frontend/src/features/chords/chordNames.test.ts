import { describe, expect, it } from 'vitest'
import { chordAt, chordName } from './chordNames'

describe('chord names', () => {
  it('shows minor chords with m and sharps as ♯', () => {
    expect(chordName('A:min')).toBe('Am')
    expect(chordName('C:maj')).toBe('C')
    expect(chordName('F#:maj')).toBe('F♯')
    expect(chordName('N')).toBeNull()
  })

  it('finds the chord at a time', () => {
    const chords = [
      { start: 0, end: 2, label: 'C:maj' },
      { start: 2, end: 4, label: 'G:maj' },
    ]
    expect(chordAt(chords, 0)?.label).toBe('C:maj')
    expect(chordAt(chords, 2)?.label).toBe('G:maj')
    expect(chordAt(chords, 3.9)?.label).toBe('G:maj')
    expect(chordAt(chords, 4)).toBeNull()
    expect(chordAt([], 1)).toBeNull()
  })
})

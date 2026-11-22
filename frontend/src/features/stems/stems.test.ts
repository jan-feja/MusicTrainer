import { describe, expect, it } from 'vitest'
import { loadingProgress, orderStems, quietStems, stemLabel } from './stems'

const stem = (name: string, rms = 0.1) => ({ name, file: `${name}.flac`, rms })

describe('stems', () => {
  it('orders instruments drums first, unknown ones last', () => {
    const names = orderStems(
      ['other', 'piano', 'zither', 'vocals', 'drums', 'bass'].map((n) => stem(n)),
    )
    expect(names.map((s) => s.name)).toEqual([
      'drums',
      'bass',
      'vocals',
      'piano',
      'other',
      'zither',
    ])
  })

  it('labels stems for display', () => {
    expect(stemLabel('drums')).toBe('Drums')
  })

  it('finds stems much quieter than the loudest one', () => {
    // a real instrumental song: no vocals, no piano
    const stems = [
      stem('drums', 0.05),
      stem('bass', 0.123),
      stem('other', 0.0064),
      stem('vocals', 0.0045),
      stem('guitar', 0.025),
      stem('piano', 0.0014),
    ]
    expect(quietStems(stems)).toEqual(new Set(['vocals', 'piano']))
    expect(quietStems([stem('drums', 0), stem('bass', 0)])).toEqual(new Set())
  })

  it('counts downloading as most of the loading progress', () => {
    expect(loadingProgress([])).toBe(0)
    const half = { loaded: 50, total: 100, decoded: false }
    expect(loadingProgress([half, half])).toBeCloseTo(0.45)
    const done = { loaded: 100, total: 100, decoded: true }
    expect(loadingProgress([done, done])).toBeCloseTo(1)
    expect(loadingProgress([done, { loaded: 10, total: null, decoded: false }])).toBeCloseTo(0.5)
  })
})

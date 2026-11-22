import { describe, expect, it } from 'vitest'
import { mixerGains, withMuteToggled, withSoloToggled, withStemsEnabled, withVolume } from './mixer'

const NAMES = ['drums', 'bass', 'vocals']

describe('mixer', () => {
  it('plays every stem at full volume by default', () => {
    expect(mixerGains(NAMES, null)).toEqual({ drums: 1, bass: 1, vocals: 1 })
  })

  it('mutes stems and sets their volume', () => {
    let mixer = withStemsEnabled(null, true)
    mixer = withMuteToggled(mixer, 'vocals')
    mixer = withVolume(mixer, 'bass', 0.456)
    expect(mixerGains(NAMES, mixer)).toEqual({ drums: 1, bass: 0.46, vocals: 0 })
    expect(mixerGains(NAMES, withMuteToggled(mixer, 'vocals')).vocals).toBe(1)
  })

  it('plays only the soloed stems, even muted ones', () => {
    let mixer = withMuteToggled(null, 'drums')
    mixer = withSoloToggled(mixer, 'drums')
    mixer = withSoloToggled(mixer, 'bass')
    expect(mixerGains(NAMES, mixer)).toEqual({ drums: 1, bass: 1, vocals: 0 })
    mixer = withSoloToggled(withSoloToggled(mixer, 'drums'), 'bass')
    expect(mixerGains(NAMES, mixer)).toEqual({ drums: 0, bass: 1, vocals: 1 })
  })

  it('keeps volumes within 0 to 1', () => {
    expect(withVolume(null, 'bass', 1.5).volumes.bass).toBe(1)
    expect(withVolume(null, 'bass', -1).volumes.bass).toBe(0)
  })

  it('stores fields in the order the server sends them', () => {
    const stored = { enabled: true, volumes: { bass: 0.5 }, muted: ['vocals'], solo: [] }
    const reordered = { solo: [], muted: ['vocals'], volumes: { bass: 0.5 }, enabled: false }
    expect(JSON.stringify(withStemsEnabled(reordered, true))).toBe(JSON.stringify(stored))
  })
})

import { describe, expect, it } from 'vitest'
import {
  mixerGains,
  stemLevel,
  withLevel,
  withMuteSwitched,
  withMuteToggled,
  withSoloToggled,
  withStemsEnabled,
  withVolume,
} from './mixer'

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

  it('plays only the soloed stems, and never muted ones', () => {
    let mixer = withSoloToggled(null, 'drums')
    mixer = withSoloToggled(mixer, 'bass')
    expect(mixerGains(NAMES, mixer)).toEqual({ drums: 1, bass: 1, vocals: 0 })
    mixer = withMuteToggled(mixer, 'drums')
    expect(mixerGains(NAMES, mixer)).toEqual({ drums: 0, bass: 1, vocals: 0 })
    mixer = withSoloToggled(withSoloToggled(mixer, 'drums'), 'bass')
    expect(mixerGains(NAMES, mixer)).toEqual({ drums: 0, bass: 1, vocals: 1 })
  })

  it('a soloed stem at 0 is silent', () => {
    const mixer = withLevel(withSoloToggled(null, 'bass'), 'bass', 0)
    expect(mixerGains(NAMES, mixer)).toEqual({ drums: 0, bass: 0, vocals: 0 })
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

  it('shows the level a stem is heard at on its slider', () => {
    let mixer = withVolume(null, 'bass', 0.6)
    expect(stemLevel(mixer, 'bass')).toBe(0.6)
    mixer = withMuteToggled(mixer, 'bass')
    expect(stemLevel(mixer, 'bass')).toBe(0)
    mixer = withSoloToggled(withMuteToggled(mixer, 'bass'), 'drums')
    expect(stemLevel(mixer, 'bass')).toBe(0)
    expect(stemLevel(mixer, 'drums')).toBe(1)
  })

  it('mutes at 0 and keeps the volume for unmuting', () => {
    let mixer = withLevel(withVolume(null, 'bass', 0.6), 'bass', 0)
    expect(mixer.muted).toEqual(['bass'])
    expect(mixer.volumes.bass).toBe(0.6)
    mixer = withMuteSwitched(mixer, 'bass')
    expect(stemLevel(mixer, 'bass')).toBe(0.6)
  })

  it('unmutes at full volume when the volume was 0', () => {
    const mixer = withMuteSwitched(withMuteToggled(withVolume(null, 'bass', 0), 'bass'), 'bass')
    expect(stemLevel(mixer, 'bass')).toBe(1)
  })

  it('moving the slider of a muted stem unmutes it', () => {
    const mixer = withLevel(withMuteToggled(null, 'bass'), 'bass', 0.3)
    expect(mixer.muted).toEqual([])
    expect(stemLevel(mixer, 'bass')).toBe(0.3)
  })

  it('moving the slider of a stem left out of the solo adds it to the solo', () => {
    const mixer = withLevel(withSoloToggled(null, 'drums'), 'bass', 0.5)
    expect(mixer.solo).toEqual(['drums', 'bass'])
    expect(mixerGains(NAMES, mixer)).toEqual({ drums: 1, bass: 0.5, vocals: 0 })
  })
})

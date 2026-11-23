import { describe, expect, it } from 'vitest'
import type { MixerSettings, Preset } from '../../api/types'
import type { BeatGrid } from '../beats/beatGrid'
import {
  type PracticeState,
  cleanPresetName,
  createPreset,
  defaultState,
  isDefaultState,
  nextPresetName,
  describeMix,
  matchesPreset,
  newPresetId,
  presetTags,
  sortPresets,
} from './presets'

const GRID: BeatGrid = {
  beats: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
  bars: [0, 4, 8, 12, 16],
  beatsPerBar: 4,
  bpm: 60,
}

const MIX: MixerSettings = { enabled: true, volumes: {}, muted: ['vocals'], solo: [] }

const state = (overrides: Partial<PracticeState> = {}): PracticeState => ({
  loop: { start: 4, end: 12 },
  snapMode: 'bar',
  playbackRate: 1,
  mixer: null,
  metronome: { enabled: false, volume: 0.3 },
  ...overrides,
})

const preset = (overrides: Partial<Preset> = {}): Preset => ({
  id: 'a',
  name: 'Verse',
  start: 10,
  end: 20,
  snapMode: 'off',
  playbackRate: 1,
  ...overrides,
})

describe('presets', () => {
  it('lists whole-song presets first, then loops in playing order', () => {
    const presets = [
      preset({ id: 'c', start: 30, end: 40 }),
      preset({ id: 'b', start: 10, end: 15 }),
      preset({ id: 'w', start: null, end: null }),
      preset(),
    ]
    expect(sortPresets(presets).map((p) => p.id)).toEqual(['w', 'b', 'a', 'c'])
  })

  it('makes ids the backend accepts', () => {
    const id = newPresetId()
    expect(id).toMatch(/^[A-Za-z0-9_-]{1,40}$/)
    expect(newPresetId()).not.toBe(id)
  })

  it('numbers new presets after the highest number', () => {
    expect(nextPresetName([])).toBe('Preset 1')
    expect(nextPresetName([preset({ name: 'Preset 3' }), preset({ name: 'Solo' })])).toBe(
      'Preset 4',
    )
    expect(nextPresetName([preset({ name: 'Verse' })])).toBe('Preset 1')
  })

  it('knows the player as the song first opens', () => {
    const opened = state({ loop: null, snapMode: 'off' })
    expect(isDefaultState(opened)).toBe(true)
    expect(isDefaultState({ ...opened, mixer: { ...MIX, enabled: false } })).toBe(true)
    expect(isDefaultState({ ...opened, mixer: MIX })).toBe(false)
    expect(isDefaultState({ ...opened, playbackRate: 0.8 })).toBe(false)
    expect(isDefaultState(state())).toBe(false)
    expect(defaultState(state({ mixer: MIX })).mixer?.enabled).toBe(false)
  })

  it('creates a preset from the player', () => {
    expect(createPreset([], state({ playbackRate: 0.8, mixer: MIX }), 'Solo')).toMatchObject({
      name: 'Solo',
      start: 4,
      end: 12,
      snapMode: 'bar',
      playbackRate: 0.8,
      mixer: MIX,
    })
  })

  it('tells whether the player is set as the preset says', () => {
    const saved = createPreset([], state({ mixer: MIX }))
    expect(matchesPreset(saved, state({ mixer: MIX }))).toBe(true)
    expect(matchesPreset(saved, state({ mixer: { ...MIX, volumes: { bass: 1 } } }))).toBe(true)
    expect(matchesPreset(saved, state({ mixer: { ...MIX, muted: [] } }))).toBe(false)
    expect(matchesPreset(saved, state({ mixer: MIX, playbackRate: 0.9 }))).toBe(false)
    expect(matchesPreset(saved, state({ mixer: MIX, loop: null }))).toBe(false)
    const clicking = state({ mixer: MIX, metronome: { enabled: true, volume: 0.3 } })
    expect(matchesPreset(saved, clicking)).toBe(false)
    // what a preset leaves alone does not count
    expect(matchesPreset({ ...saved, mixer: null, metronome: null }, clicking)).toBe(true)
  })

  it('describes the stem mix', () => {
    expect(describeMix(null)).toBeNull()
    expect(describeMix({ ...MIX, enabled: false })).toBeNull()
    expect(describeMix({ ...MIX, muted: ['vocals', 'drums'] })).toBe('No vocals, drums')
    expect(describeMix({ ...MIX, solo: ['bass'] })).toBe('Bass only')
    expect(describeMix({ ...MIX, muted: [], volumes: { bass: 0.5 } })).toBe('Custom mix')
    expect(describeMix({ ...MIX, muted: [] })).toBe('Stems')
  })

  it('tags the loop length, speed, mix and metronome', () => {
    const tags = presetTags(
      preset({
        start: 4,
        end: 12,
        snapMode: 'bar',
        playbackRate: 0.75,
        mixer: MIX,
        metronome: { enabled: true, volume: 0.3 },
      }),
      GRID,
    )
    expect(tags.map((tag) => tag.label)).toEqual(['0:04 · 2 bars', '0.75×', 'No vocals', 'Click'])
    expect(presetTags(preset({ start: 60.5, end: 66.9 }), null)[0].label).toBe('1:00 · 6.4 s')
    expect(presetTags(preset({ start: null, end: null }), GRID)[0].label).toBe('Whole song')
  })

  it('cleans typed names', () => {
    expect(cleanPresetName('  Solo  ')).toBe('Solo')
    expect(cleanPresetName('   ')).toBeNull()
    expect(cleanPresetName('x'.repeat(150))).toHaveLength(100)
  })
})

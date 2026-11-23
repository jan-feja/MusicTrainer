/**
 * Presets: named ways to practice a song (loop, speed, snap, stem mix,
 * metronome). Pure functions, no React.
 */
import type { LoopSnapMode, MetronomeSettings, MixerSettings, Preset } from '../../api/types'
import { formatTime } from '../../lib/format'
import { type BeatGrid, describeGridLength, gridPoints, stepsBetween } from '../beats/beatGrid'
import type { LoopRegion } from '../player/loop'
import { formatPlaybackRate } from '../player/playbackRate'

export const MAX_PRESET_NAME_LENGTH = 100
/** Loop points this close count as the same (the player rounds nothing, the server might). */
const SAME_TIME_SECONDS = 0.001

/** How the player is set right now: what a preset would keep. */
export interface PracticeState {
  loop: LoopRegion | null
  snapMode: LoopSnapMode
  playbackRate: number
  /** null: the song has no stems (yet); a preset then leaves the stems alone. */
  mixer: MixerSettings | null
  metronome: MetronomeSettings
}

/** One fact about a preset, shown as a tag. */
export interface PresetTag {
  kind: 'loop' | 'speed' | 'mix' | 'metronome'
  label: string
}

/** The whole-song presets first, then the loops in playing order. */
export function sortPresets(presets: readonly Preset[]): Preset[] {
  const start = (preset: Preset) => preset.start ?? -1
  const end = (preset: Preset) => preset.end ?? -1
  return [...presets].sort((a, b) => start(a) - start(b) || end(a) - end(b))
}

/** An id unique enough within one video (also where crypto.randomUUID is missing: plain http). */
export function newPresetId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
}

export function presetFromState(id: string, name: string, state: PracticeState): Preset {
  return {
    id,
    name,
    start: state.loop?.start ?? null,
    end: state.loop?.end ?? null,
    snapMode: state.snapMode,
    playbackRate: state.playbackRate,
    mixer: state.mixer,
    metronome: state.metronome,
  }
}

export function createPreset(
  presets: readonly Preset[],
  state: PracticeState,
  name?: string,
): Preset {
  return presetFromState(newPresetId(), name ?? nextPresetName(presets), state)
}

/** The player is set as the preset says (what the preset leaves alone does not count). */
export function matchesPreset(preset: Preset, state: PracticeState): boolean {
  const sameTime = (a: number | null, b: number | null) =>
    a === null || b === null ? a === b : Math.abs(a - b) < SAME_TIME_SECONDS
  if (!sameTime(preset.start, state.loop?.start ?? null)) return false
  if (!sameTime(preset.end, state.loop?.end ?? null)) return false
  if (preset.snapMode !== state.snapMode || preset.playbackRate !== state.playbackRate) return false
  if (preset.mixer && state.mixer && !sameMixer(preset.mixer, state.mixer)) return false
  const { metronome } = preset
  return (
    !metronome ||
    (metronome.enabled === state.metronome.enabled && metronome.volume === state.metronome.volume)
  )
}

function sameMixer(a: MixerSettings, b: MixerSettings): boolean {
  const sorted = (list: readonly string[]) => [...list].sort().join(',')
  const volumes = new Set([...Object.keys(a.volumes), ...Object.keys(b.volumes)])
  return (
    a.enabled === b.enabled &&
    sorted(a.muted) === sorted(b.muted) &&
    sorted(a.solo) === sorted(b.solo) &&
    [...volumes].every((name) => (a.volumes[name] ?? 1) === (b.volumes[name] ?? 1))
  )
}

/** "Preset 1", "Preset 2", ...: one more than the highest number used so far. */
export function nextPresetName(presets: readonly Preset[]): string {
  const numbers = presets.map((preset) => /^Preset (\d+)$/.exec(preset.name)?.[1]).map(Number)
  const highest = Math.max(0, ...numbers.filter(Number.isFinite))
  return `Preset ${highest + 1}`
}

/**
 * The player as a song first opens: the whole song, normal speed, no snap,
 * the video's own sound (stems off), no metronome (its volume stays).
 */
export function defaultState(current: PracticeState): PracticeState {
  return {
    loop: null,
    snapMode: 'off',
    playbackRate: 1,
    mixer: current.mixer && { enabled: false, volumes: {}, muted: [], solo: [] },
    metronome: { ...current.metronome, enabled: false },
  }
}

/** The player is as a song first opens (with the stems off, their mix does not matter). */
export function isDefaultState(state: PracticeState): boolean {
  const reset = presetFromState('default', 'Default', { ...defaultState(state), mixer: null })
  return matchesPreset(reset, state) && !state.mixer?.enabled
}

/** "No vocals", "Bass only", "Stems"; null when the stems are off (or there are none). */
export function describeMix(mixer: MixerSettings | null | undefined): string | null {
  if (!mixer) return null
  if (!mixer.enabled) return null
  const names = (list: readonly string[]) => list.map(stemTitle).join(', ')
  if (mixer.solo.length > 0) return `${names(mixer.solo)} only`
  if (mixer.muted.length > 0) return `No ${names(mixer.muted).toLowerCase()}`
  const quieter = Object.entries(mixer.volumes).filter(([, volume]) => volume < 1)
  return quieter.length > 0 ? 'Custom mix' : 'Stems'
}

function stemTitle(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/** What the preset holds, as tags: loop with its length, speed, mix and metronome. */
export function presetTags(preset: Preset, grid: BeatGrid | null): PresetTag[] {
  const loop = presetLoop(preset)
  const tags: PresetTag[] = [{ kind: 'loop', label: describeLoop(loop, preset.snapMode, grid) }]
  if (preset.playbackRate !== 1) {
    tags.push({ kind: 'speed', label: formatPlaybackRate(preset.playbackRate) })
  }
  const mix = describeMix(preset.mixer)
  if (mix) tags.push({ kind: 'mix', label: mix })
  if (preset.metronome?.enabled) tags.push({ kind: 'metronome', label: 'Click' })
  return tags
}

/** "0:42 · 2 bars", "1:00 · 6.4 s", or "Whole song". */
function describeLoop(loop: LoopRegion | null, snapMode: LoopSnapMode, grid: BeatGrid | null) {
  if (!loop) return 'Whole song'
  const unit = snapMode === 'off' ? null : snapMode
  const length =
    grid && unit
      ? describeGridLength(
          stepsBetween(gridPoints(grid, unit), loop.start, loop.end),
          unit,
          grid.beatsPerBar,
        )
      : `${(loop.end - loop.start).toFixed(1)} s`
  return `${formatTime(loop.start)} · ${length}`
}

/** A name as typed: trimmed and not too long; null if nothing is left. */
export function cleanPresetName(name: string): string | null {
  const trimmed = name.trim().slice(0, MAX_PRESET_NAME_LENGTH)
  return trimmed === '' ? null : trimmed
}

/** The loop of a preset, if it has one. */
export function presetLoop(preset: Preset): LoopRegion | null {
  return preset.start !== null && preset.end !== null
    ? { start: preset.start, end: preset.end }
    : null
}

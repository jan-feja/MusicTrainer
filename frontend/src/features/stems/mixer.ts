/** The stem mixer's rules: volume, mute and solo per stem, and how they are stored. */
import type { MixerSettings } from '../../api/types'

const EMPTY_MIXER: MixerSettings = { enabled: false, volumes: {}, muted: [], solo: [] }

/** In the order the server sends the fields, so an unchanged mixer is not stored again. */
function mixer(m: MixerSettings): MixerSettings {
  return { enabled: m.enabled, volumes: m.volumes, muted: m.muted, solo: m.solo }
}

/**
 * The gain of each stem: its volume; 0 when muted; and when any stem is soloed,
 * 0 for the others. Mute wins over solo, so a slider at 0 always silences.
 */
export function mixerGains(names: readonly string[], settings: MixerSettings | null) {
  const { volumes, muted, solo } = settings ?? EMPTY_MIXER
  return Object.fromEntries(
    names.map((name) => {
      const heard = !muted.includes(name) && (solo.length === 0 || solo.includes(name))
      return [name, heard ? (volumes[name] ?? 1) : 0]
    }),
  )
}

/** Stems turned on or off (a mixer is created the first time). */
export function withStemsEnabled(settings: MixerSettings | null, enabled: boolean) {
  return mixer({ ...(settings ?? EMPTY_MIXER), enabled })
}

function toggled(list: readonly string[], name: string): string[] {
  return list.includes(name) ? list.filter((n) => n !== name) : [...list, name]
}

export function withMuteToggled(settings: MixerSettings | null, name: string) {
  const current = settings ?? EMPTY_MIXER
  return mixer({ ...current, muted: toggled(current.muted, name) })
}

/** Solo one stem at most: S on the soloed stem ends the solo, on another moves it there. */
export function withSoloToggled(settings: MixerSettings | null, name: string) {
  const current = settings ?? EMPTY_MIXER
  return mixer({ ...current, solo: current.solo.includes(name) ? [] : [name] })
}

export function withVolume(settings: MixerSettings | null, name: string, volume: number) {
  const current = settings ?? EMPTY_MIXER
  const clamped = Math.min(1, Math.max(0, Math.round(volume * 100) / 100))
  return mixer({ ...current, volumes: { ...current.volumes, [name]: clamped } })
}

/** The volume a stem comes back at when unmuted: its own, or full if that was 0. */
function restoredVolume(settings: MixerSettings, name: string): number {
  const volume = settings.volumes[name] ?? 1
  return volume > 0 ? volume : 1
}

/**
 * What a stem's slider shows: the level it is heard at, so 0 while it is muted
 * or another stem is soloed.
 */
export function stemLevel(settings: MixerSettings | null, name: string): number {
  return mixerGains([name], settings)[name] ?? 1
}

/**
 * Move a stem's slider. Like the player's volume: 0 mutes the stem (keeping its
 * volume for unmuting), anything else sets the volume and makes the stem heard
 * again: unmuted, and if another stem is soloed, the solo ends.
 */
export function withLevel(settings: MixerSettings | null, name: string, level: number) {
  const current = settings ?? EMPTY_MIXER
  if (level <= 0) {
    return current.muted.includes(name) ? mixer(current) : withMuteToggled(current, name)
  }
  const next = withVolume(current, name, level)
  const muted = next.muted.filter((n) => n !== name)
  const solo = next.solo.length > 0 && !next.solo.includes(name) ? [] : next.solo
  return mixer({ ...next, muted, solo })
}

/** Mute or unmute a stem; unmuting brings back its volume (full if it was 0). */
export function withMuteSwitched(settings: MixerSettings | null, name: string) {
  const current = settings ?? EMPTY_MIXER
  const next = withMuteToggled(current, name)
  if (next.muted.includes(name)) return next
  return withVolume(next, name, restoredVolume(next, name))
}

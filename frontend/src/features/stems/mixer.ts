/** The stem mixer's rules: volume, mute and solo per stem, and how they are stored. */
import type { MixerSettings } from '../../api/types'

const EMPTY_MIXER: MixerSettings = { enabled: false, volumes: {}, muted: [], solo: [] }

/** In the order the server sends the fields, so an unchanged mixer is not stored again. */
function mixer(m: MixerSettings): MixerSettings {
  return { enabled: m.enabled, volumes: m.volumes, muted: m.muted, solo: m.solo }
}

/** The gain of each stem: its volume, 0 when muted, and when any stem is soloed only those. */
export function mixerGains(names: readonly string[], settings: MixerSettings | null) {
  const { volumes, muted, solo } = settings ?? EMPTY_MIXER
  return Object.fromEntries(
    names.map((name) => {
      const heard = solo.length > 0 ? solo.includes(name) : !muted.includes(name)
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

export function withSoloToggled(settings: MixerSettings | null, name: string) {
  const current = settings ?? EMPTY_MIXER
  return mixer({ ...current, solo: toggled(current.solo, name) })
}

export function withVolume(settings: MixerSettings | null, name: string, volume: number) {
  const current = settings ?? EMPTY_MIXER
  const clamped = Math.min(1, Math.max(0, Math.round(volume * 100) / 100))
  return mixer({ ...current, volumes: { ...current.volumes, [name]: clamped } })
}

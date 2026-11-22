/**
 * Stems: a song separated into instruments on the server (Demucs), loaded into
 * the browser as decoded audio for the mixer.
 */
import type { StemInfo } from '../../api/types'

/** A stem this much quieter than the loudest one is taken as not in the song. */
export const QUIET_SHARE = 0.05

/** Instruments in the order they are shown; unknown names go after them. */
const STEM_ORDER = ['drums', 'bass', 'vocals', 'guitar', 'piano', 'other']

/** Waveform resolution: loudest sample per this many seconds is kept (zoomed in to ~1 s, 1 per pixel). */
export const PEAKS_PER_SECOND = 400

/** Share of the loading progress taken by downloading; the rest is decoding. */
const DOWNLOAD_SHARE = 0.9

export interface StemTrack {
  name: string
  label: string
  /** Hardly anything in it, e.g. piano in a song without piano. */
  quiet: boolean
  buffer: AudioBuffer
  /** Loudest sample (of any channel) in each 1 / PEAKS_PER_SECOND s, for the waveform. */
  peaks: Float32Array
}

export type StemsStatus =
  | { kind: 'off' }
  /** Asking the server. */
  | { kind: 'checking' }
  /** The server separates the song; `progress` is 0–1 or null while waiting its turn. */
  | { kind: 'separating'; progress: number | null }
  /** Downloading and decoding the stems, 0–1. */
  | { kind: 'loading'; progress: number }
  | { kind: 'ready'; tracks: StemTrack[] }
  | { kind: 'failed'; error: string }

export function stemLabel(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/** The stems in display order. */
export function orderStems<T extends { name: string }>(stems: readonly T[]): T[] {
  const rank = (name: string) => {
    const index = STEM_ORDER.indexOf(name)
    return index === -1 ? STEM_ORDER.length : index
  }
  return [...stems].sort((a, b) => rank(a.name) - rank(b.name) || a.name.localeCompare(b.name))
}

/** Names of the stems that are hardly heard next to the loudest one. */
export function quietStems(stems: readonly StemInfo[]): Set<string> {
  const loudest = Math.max(0, ...stems.map((stem) => stem.rms))
  return new Set(
    stems.filter((stem) => loudest > 0 && stem.rms < loudest * QUIET_SHARE).map((s) => s.name),
  )
}

export interface FileProgress {
  loaded: number
  /** From Content-Length; null if the server did not say. */
  total: number | null
  decoded: boolean
}

/** Overall loading progress, 0–1: downloading counts 90 %, decoding the rest. */
export function loadingProgress(files: readonly FileProgress[]): number {
  if (files.length === 0) return 0
  const download =
    files.reduce((sum, file) => {
      if (file.decoded) return sum + 1
      if (!file.total) return sum
      return sum + Math.min(1, file.loaded / file.total)
    }, 0) / files.length
  const decode = files.filter((file) => file.decoded).length / files.length
  return DOWNLOAD_SHARE * download + (1 - DOWNLOAD_SHARE) * decode
}

/** The loudest sample of any channel in each stretch of `sampleRate / peaksPerSecond` samples. */
export function computePeaks(
  channels: readonly Float32Array[],
  sampleRate: number,
  peaksPerSecond = PEAKS_PER_SECOND,
): Float32Array {
  const length = channels[0]?.length ?? 0
  const step = sampleRate / peaksPerSecond
  const peaks = new Float32Array(Math.ceil(length / step))
  for (const samples of channels) {
    for (let i = 0; i < peaks.length; i++) {
      const end = Math.min(length, Math.round((i + 1) * step))
      let peak = peaks[i]
      for (let j = Math.round(i * step); j < end; j++) {
        const value = Math.abs(samples[j])
        if (value > peak) peak = value
      }
      peaks[i] = peak
    }
  }
  return peaks
}

/** The loudest of `peaks` between two song times (at least the one peak at `start`). */
export function peakBetween(
  peaks: Float32Array,
  start: number,
  end: number,
  peaksPerSecond = PEAKS_PER_SECOND,
): number {
  const first = Math.max(0, Math.floor(start * peaksPerSecond))
  const last = Math.min(peaks.length, Math.max(first + 1, Math.ceil(end * peaksPerSecond)))
  let peak = 0
  for (let i = first; i < last; i++) if (peaks[i] > peak) peak = peaks[i]
  return peak
}

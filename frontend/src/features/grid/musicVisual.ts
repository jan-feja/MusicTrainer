import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { MusicVisual } from '../../api/types'
import { errorMessage } from '../../lib/format'

/** The pictures of a song, decoded for drawing. */
export interface MusicPicture {
  fps: number
  bands: number
  frames: number
  /** frames x bands, low frequencies first. */
  spectrogram: Uint8Array
  colorStep: number
  /** RGB per color step. */
  colors: Uint8Array
  beatFps: number
  /** Per frame, 0-255: how likely the network hears a beat / a bar start. */
  beat: Uint8Array | null
  downbeat: Uint8Array | null
}

function bytes(base64: string): Uint8Array {
  const text = atob(base64)
  const out = new Uint8Array(text.length)
  for (let i = 0; i < text.length; i += 1) out[i] = text.charCodeAt(i)
  return out
}

export function decodeVisual(visual: MusicVisual): MusicPicture {
  return {
    fps: visual.fps,
    bands: visual.bands,
    frames: visual.frames,
    spectrogram: bytes(visual.spectrogram),
    colorStep: visual.colorStep,
    colors: bytes(visual.colors),
    beatFps: visual.beatFps ?? visual.fps,
    beat: visual.beat ? bytes(visual.beat) : null,
    downbeat: visual.downbeat ? bytes(visual.downbeat) : null,
  }
}

export type PictureState =
  | { status: 'loading' }
  | { status: 'ready'; picture: MusicPicture }
  | { status: 'failed'; error: string }

/** Loads the pictures of a video once `enabled` (the first time takes a few seconds). */
export function useMusicPicture(videoId: string, enabled: boolean): PictureState {
  const [state, setState] = useState<{ videoId: string; state: PictureState } | null>(null)
  const loaded = state?.videoId === videoId && state.state.status === 'ready'

  useEffect(() => {
    if (!enabled || loaded) return
    const controller = new AbortController()
    api.getVisual(videoId, controller.signal).then(
      (visual) => setState({ videoId, state: { status: 'ready', picture: decodeVisual(visual) } }),
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ videoId, state: { status: 'failed', error: errorMessage(error) } })
        }
      },
    )
    return () => controller.abort()
  }, [videoId, enabled, loaded])

  return state?.videoId === videoId ? state.state : { status: 'loading' }
}

/** Spectrogram colors: dark blue to orange to pale yellow (like 'magma'), 256 entries. */
export const SPECTROGRAM_COLORS: Uint8Array = (() => {
  const stops = [
    [0, 8, 8, 20],
    [0.25, 60, 15, 100],
    [0.5, 160, 40, 110],
    [0.75, 245, 110, 70],
    [1, 252, 245, 180],
  ]
  const lut = new Uint8Array(256 * 3)
  for (let i = 0; i < 256; i += 1) {
    const x = i / 255
    const k = Math.min(stops.length - 2, Math.floor(x * (stops.length - 1)))
    const [x0, ...a] = stops[k]
    const [x1, ...b] = stops[k + 1]
    const f = (x - x0) / (x1 - x0)
    for (let c = 0; c < 3; c += 1) lut[i * 3 + c] = Math.round(a[c] + (b[c] - a[c]) * f)
  }
  return lut
})()

import { api } from '../../api/client'
import type { StemSet } from '../../api/types'
import { type FileProgress, type StemTrack, orderStems, quietStems, stemLabel } from './stems'

async function download(
  url: string,
  signal: AbortSignal,
  onProgress: (loaded: number, total: number | null) => void,
): Promise<ArrayBuffer> {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`Could not load ${url} (${response.status})`)
  const total = Number(response.headers.get('Content-Length')) || null
  if (!response.body) return response.arrayBuffer()
  const reader = response.body.getReader()
  const chunks: Uint8Array[] = []
  let loaded = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    loaded += value.byteLength
    onProgress(loaded, total)
  }
  const bytes = new Uint8Array(loaded)
  let offset = 0
  for (const chunk of chunks) {
    bytes.set(chunk, offset)
    offset += chunk.byteLength
  }
  return bytes.buffer
}

/**
 * Download and decode all stems of a video. They are decoded at their own
 * sample rate; playing them in an AudioContext at another rate resamples.
 */
export async function loadStems(
  videoId: string,
  stems: StemSet,
  signal: AbortSignal,
  onProgress: (files: readonly FileProgress[]) => void,
): Promise<StemTrack[]> {
  const ordered = orderStems(stems.stems)
  const quiet = quietStems(stems.stems)
  const files: FileProgress[] = ordered.map(() => ({ loaded: 0, total: null, decoded: false }))
  const report = () => onProgress(files.map((file) => ({ ...file })))
  // decodeAudioData needs a context; an offline one plays nothing and needs no user gesture
  const decoder = new OfflineAudioContext(2, 1, stems.sampleRate)

  const buffers = await Promise.all(
    ordered.map(async (stem, index) => {
      const data = await download(api.stemUrl(videoId, stem.name), signal, (loaded, total) => {
        files[index] = { ...files[index], loaded, total }
        report()
      })
      const buffer = await decoder.decodeAudioData(data)
      files[index] = { ...files[index], decoded: true }
      report()
      return buffer
    }),
  )
  return ordered.map((stem, index) => ({
    name: stem.name,
    label: stemLabel(stem.name),
    quiet: quiet.has(stem.name),
    buffer: buffers[index],
  }))
}

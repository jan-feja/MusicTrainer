import { afterEach, expect, it, vi } from 'vitest'
import { GaplessLoop } from './gaplessLoop'

const stretch = vi.hoisted(() => ({
  connect: vi.fn(),
  disconnect: vi.fn(),
  latency: vi.fn(async () => 0.1),
  dropBuffers: vi.fn(async () => {}),
  addBuffers: vi.fn(async () => {}),
}))

vi.mock('signalsmith-stretch', () => ({ default: async () => stretch }))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

it('loads a restored loop once the video duration becomes available', async () => {
  const gain = { gain: { value: 0 }, connect: vi.fn(), disconnect: vi.fn() }
  stretch.connect.mockReturnValue(gain)
  class FakeAudioContext {
    sampleRate = 44100
    state = 'running'
    destination = {}
    createGain() {
      return gain
    }
    async decodeAudioData() {
      return { length: 10, duration: 10, numberOfChannels: 1, copyFromChannel: vi.fn() }
    }
    async close() {}
  }
  const fetchAudio = vi.fn(async () => new Response(new ArrayBuffer(8)))
  vi.stubGlobal('AudioContext', FakeAudioContext)
  vi.stubGlobal('fetch', fetchAudio)
  const video = Object.assign(new EventTarget(), { duration: NaN, isConnected: false })
  const loop = new GaplessLoop(video as HTMLVideoElement, '/audio')
  loop.setRegion({ start: 1, end: 3 })
  expect(fetchAudio).not.toHaveBeenCalled()

  video.duration = 10
  video.dispatchEvent(new Event('durationchange'))
  await vi.waitFor(() => expect(stretch.addBuffers).toHaveBeenCalledOnce())
  expect(fetchAudio).toHaveBeenCalledOnce()
  loop.dispose()
})

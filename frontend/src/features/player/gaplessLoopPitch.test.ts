import { afterEach, expect, it, vi } from 'vitest'
import { GaplessLoop } from './gaplessLoop'

const createStretch = vi.hoisted(() => vi.fn())
vi.mock('signalsmith-stretch', () => ({ default: createStretch }))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

it('routes both the video and the gapless loop through the same pitch effect', async () => {
  const gains: GainNode[] = []
  const contexts: FakeAudioContext[] = []
  class FakeAudioContext {
    state = 'running'
    currentTime = 10
    sampleRate = 44100
    destination = {}
    constructor() {
      contexts.push(this)
    }
    createGain() {
      const gain = Object.assign(Object.create(null) as GainNode, {
        context: this,
        gain: {
          value: 1,
          cancelScheduledValues: vi.fn(),
          setTargetAtTime: vi.fn(),
          setValueAtTime: vi.fn(),
        },
        connect: vi.fn((target: unknown) => target),
        disconnect: vi.fn(),
      })
      gains.push(gain)
      return gain
    }
    createMediaElementSource() {
      return { connect: vi.fn((target: unknown) => target) }
    }
    async decodeAudioData() {
      return { length: 10, duration: 10, numberOfChannels: 1, copyFromChannel: vi.fn() }
    }
    getOutputTimestamp() {
      return { contextTime: this.currentTime, performanceTime: performance.now() }
    }
    async close() {}
  }
  const makeNode = () => ({
    connect: vi.fn((target: unknown) => target),
    disconnect: vi.fn(),
    latency: vi.fn(async () => 0.1),
    schedule: vi.fn(async () => {}),
    dropBuffers: vi.fn(async () => {}),
    addBuffers: vi.fn(async () => {}),
  })
  const pitchNode = makeNode()
  const loopNode = makeNode()
  createStretch.mockResolvedValueOnce(pitchNode).mockResolvedValueOnce(loopNode)
  vi.stubGlobal('AudioContext', FakeAudioContext)
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(new ArrayBuffer(8))),
  )
  const video = Object.assign(new EventTarget(), {
    duration: 10,
    currentTime: 2.8,
    playbackRate: 1,
    muted: false,
    volume: 1,
    isConnected: false,
  })
  const player = new GaplessLoop(video as HTMLVideoElement, '/audio')
  await player.setPitch(0)
  expect(createStretch).not.toHaveBeenCalled()
  await player.setPitch(3)
  player.setRegion({ start: 1, end: 3 })
  await vi.waitFor(() => expect(loopNode.addBuffers).toHaveBeenCalledOnce())
  expect(player.tick()).toBe(true)
  expect(pitchNode.schedule).toHaveBeenCalledWith({ active: true, semitones: 3 })
  expect(gains[3].connect).toHaveBeenCalledWith(gains[0])
  expect(gains[4].connect).toHaveBeenCalledWith(gains[0])
  expect(loopNode.schedule).toHaveBeenCalledWith(
    expect.objectContaining({ active: true, rate: 1, loopStart: 1, loopEnd: 3 }),
  )
  contexts[0].currentTime = 10.6
  expect(player.position()).toBeCloseTo(1.3, 2)
  player.dispose()
})

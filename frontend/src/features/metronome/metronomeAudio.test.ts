import { afterEach, describe, expect, it, vi } from 'vitest'
import type { BeatGrid } from '../beats/beatGrid'
import { MetronomeAudio } from './metronomeAudio'

const grid: BeatGrid = {
  beats: [0.5, 1, 1.5, 2, 2.5],
  bars: [0.5, 2.5],
  beatsPerBar: 4,
  bpm: 120,
}

function makePlayer() {
  const starts: { at: number; frequency: number; stop: ReturnType<typeof vi.fn> }[] = []
  const gain = () => ({
    gain: {
      value: 0,
      setValueAtTime: vi.fn(),
      exponentialRampToValueAtTime: vi.fn(),
    },
    connect: vi.fn(),
    disconnect: vi.fn(),
  })
  const clock = { currentTime: 0 }
  const context: AudioContext = Object.assign(Object.create(null) as AudioContext, {
    state: 'running',
    baseLatency: 0.1,
    outputLatency: 0.05,
    destination: {},
    getOutputTimestamp: () => ({ contextTime: 0, performanceTime: 0 }),
    createGain: gain,
    createOscillator: () => {
      const oscillator = {
        type: 'sine',
        frequency: { value: 0 },
        onended: null,
        connect: () => ({ connect: vi.fn() }),
        disconnect: vi.fn(),
        start: (at: number) =>
          starts.push({ at, frequency: oscillator.frequency.value, stop: oscillator.stop }),
        stop: vi.fn(),
      }
      return oscillator
    },
  })
  Object.defineProperty(context, 'currentTime', { get: () => clock.currentTime })
  const video = Object.assign(new EventTarget(), {
    paused: false,
    readyState: 4,
    playbackRate: 1,
  })
  let position = 0.1
  let gapless = false
  const player = new MetronomeAudio(
    context,
    video as HTMLVideoElement,
    grid,
    null,
    () => position,
    () => gapless,
    0.3,
  )
  const advance = (seconds: number) => {
    for (let elapsed = 0; elapsed < seconds; elapsed += 0.025) {
      clock.currentTime += 0.025
      if (!video.paused) position += 0.025 * video.playbackRate
      vi.advanceTimersByTime(25)
    }
  }
  const seek = (time: number) => {
    video.dispatchEvent(new Event('seeking'))
    position = time
    video.dispatchEvent(new Event('seeked'))
  }
  const setGapless = (active: boolean) => {
    gapless = active
  }
  return { player, video, starts, advance, seek, setGapless }
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('metronome audio scheduling', () => {
  it('continues scheduling each beat ahead even when output has latency', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    const { player, starts, advance } = makePlayer()
    player.start()
    advance(1.7)
    expect(starts.map((click) => click.frequency)).toEqual([1500, 1000, 1000, 1000])
    expect(starts[1].at - starts[0].at).toBeCloseTo(0.5)
    expect(starts[2].at - starts[1].at).toBeCloseTo(0.5)
    expect(starts[3].at - starts[2].at).toBeCloseTo(0.5)
    player.dispose()
  })

  it('cancels scheduled clicks when playback pauses and schedules again on play', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    const { player, video, starts, advance } = makePlayer()
    player.start()
    advance(0.3)
    expect(starts).toHaveLength(1)
    video.paused = true
    video.dispatchEvent(new Event('pause'))
    expect(starts[0].stop).toHaveBeenLastCalledWith()
    advance(0.5)
    expect(starts).toHaveLength(1)
    video.paused = false
    video.dispatchEvent(new Event('playing'))
    advance(0.5)
    expect(starts.length).toBeGreaterThan(1)
    player.dispose()
  })

  it('cancels old clicks after seeking or changing playback rate', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    const { player, video, starts, advance, seek } = makePlayer()
    player.start()
    advance(0.3)
    seek(1.3)
    expect(starts[0].stop).toHaveBeenLastCalledWith()
    advance(0.1)
    expect(starts[1].frequency).toBe(1000)
    video.playbackRate = 2
    video.dispatchEvent(new Event('ratechange'))
    expect(starts[1].stop).toHaveBeenLastCalledWith()
    advance(0.6)
    expect(starts.at(-1)?.frequency).toBe(1500)
    player.dispose()
  })

  it('keeps scheduled clicks when the video follows a gapless loop', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    const { player, video, starts, advance, setGapless } = makePlayer()
    player.start()
    advance(0.3)
    setGapless(true)
    video.dispatchEvent(new Event('seeking'))
    video.dispatchEvent(new Event('waiting'))
    video.dispatchEvent(new Event('seeked'))
    video.dispatchEvent(new Event('playing'))
    expect(starts[0].stop).toHaveBeenCalledTimes(1)
    player.dispose()
  })
})

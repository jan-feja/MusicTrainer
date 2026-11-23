import { afterEach, describe, expect, it, vi } from 'vitest'
import type { BeatGrid } from '../beats/beatGrid'
import type { LoopRegion } from '../player/loop'
import { MetronomeAudio } from './metronomeAudio'

const shortGrid: BeatGrid = {
  beats: [0.5, 1, 1.5, 2, 2.5],
  bars: [0.5, 2.5],
  beatsPerBar: 4,
  bpm: 120,
}

/** 120 BPM in 4/4 for half a minute. */
const steadyBeats = Array.from({ length: 61 }, (_, index) => 0.5 + index * 0.5)
const steadyGrid: BeatGrid = {
  beats: steadyBeats,
  bars: steadyBeats.filter((_, index) => index % 4 === 0),
  beatsPerBar: 4,
  bpm: 120,
}

/** Uneven steps of up to ±5 ms, like Chrome's video.currentTime (repeatable). */
function chromeLikeJitter(): () => number {
  let seed = 12345
  return () => {
    seed = (seed * 1103515245 + 12345) % 2147483648
    return (seed / 2147483648 - 0.5) * 0.01
  }
}

interface PlayerOptions {
  grid?: BeatGrid
  loop?: LoopRegion | null
  /** Added to every reading of the player's position. */
  jitter?: () => number
  /** Song position at the start. */
  start?: number
}

function makePlayer({
  grid = shortGrid,
  loop = null,
  jitter = () => 0,
  start = 0.1,
}: PlayerOptions = {}) {
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
  let position = start
  let gapless = false
  /** A lasting difference between the position read and the true one (another clock). */
  const reading = { offset: 0 }
  const player = new MetronomeAudio(
    context,
    video as HTMLVideoElement,
    grid,
    loop,
    () => position + reading.offset + jitter(),
    () => gapless,
    0.3,
  )
  const advance = (seconds: number) => {
    for (let elapsed = 0; elapsed < seconds; elapsed += 0.025) {
      clock.currentTime += 0.025
      if (!video.paused) position += 0.025 * video.playbackRate
      if (loop && position >= loop.end) position -= loop.end - loop.start
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
  return { player, video, starts, advance, seek, setGapless, reading }
}

function gaps(starts: { at: number }[]): number[] {
  return starts.slice(1).map((click, index) => click.at - starts[index].at)
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

  it('clicks every beat exactly once, evenly, while the player clock jitters', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    const { player, starts, advance } = makePlayer({
      grid: steadyGrid,
      jitter: chromeLikeJitter(),
    })
    player.start()
    advance(25)
    // beats 0.5 … 25.0 are due within 25 s from 0.1; the last ones are scheduled ahead
    expect(starts.length).toBeGreaterThanOrEqual(50)
    expect(starts.length).toBeLessThanOrEqual(51)
    for (const gap of gaps(starts)) expect(Math.abs(gap - 0.5)).toBeLessThan(0.003)
    player.dispose()
  })

  it('clicks every beat of a loop exactly once while the player clock jitters', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    // a bar snapped with the 30 ms lead: beats 0.5, 1, 1.5, 2
    const { player, starts, advance } = makePlayer({
      grid: steadyGrid,
      loop: { start: 0.47, end: 2.47 },
      jitter: chromeLikeJitter(),
    })
    player.start()
    advance(12)
    expect(starts.length).toBeGreaterThanOrEqual(23)
    for (const gap of gaps(starts)) expect(Math.abs(gap - 0.5)).toBeLessThan(0.003)
    starts.forEach((click, index) => expect(click.frequency).toBe(index % 4 === 0 ? 1500 : 1000))
    player.dispose()
  })

  it('follows a lasting clock offset at once, without dropping or doubling a beat', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    const { player, starts, advance, reading } = makePlayer({ grid: steadyGrid })
    player.start()
    advance(2)
    reading.offset = 0.06 // the song is heard 60 ms further on than the clicks assumed
    advance(3)
    const spacing = gaps(starts)
    expect(spacing.filter((gap) => Math.abs(gap - 0.44) < 0.002)).toHaveLength(1)
    expect(spacing.filter((gap) => Math.abs(gap - 0.5) >= 0.002)).toHaveLength(1)
    player.dispose()
  })

  it('waits for the player clock to run before planning the first clicks', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    // the beat at 0.5 comes into the 0.2 s window (+ 0.15 s latency) on the first ticks
    const { player, starts, advance, reading } = makePlayer({ grid: steadyGrid, start: 0.145 })
    player.start()
    // like Chrome after 'playing': the position read jumps to 0.16, stands still for 50 ms, then runs
    for (const offset of [-0.01, -0.035, -0.06]) {
      reading.offset = offset
      advance(0.025)
    }
    advance(2)
    // the beat is read at 0.5 when the true position is 0.56: 0.415 s in, heard 0.15 s later
    expect(starts[0].at).toBeCloseTo(0.415 - 0.15, 3)
    for (const gap of gaps(starts)) expect(gap).toBeCloseTo(0.5, 3)
    player.dispose()
  })

  it('ignores a single odd reading of the player clock', () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('HTMLMediaElement', { HAVE_FUTURE_DATA: 3 })
    const { player, starts, advance, reading } = makePlayer({ grid: steadyGrid })
    player.start()
    advance(2)
    reading.offset = 0.08
    advance(0.025)
    reading.offset = 0
    advance(3)
    for (const gap of gaps(starts)) expect(gap).toBeCloseTo(0.5, 3)
    player.dispose()
  })
})

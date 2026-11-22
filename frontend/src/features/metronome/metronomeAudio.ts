import type { BeatGrid } from '../beats/beatGrid'
import { heardTime } from '../player/audioClock'
import type { LoopRegion } from '../player/loop'
import { metronomeDrift, metronomePosition, planMetronomeClicks } from './metronome'

const LOOKAHEAD_SECONDS = 0.2
const INTERVAL_MS = 25
const MAX_DRIFT_SECONDS = 0.12

/** Schedules short synthesized clicks on the audio clock while following the player. */
export class MetronomeAudio {
  private readonly context: AudioContext
  private readonly video: HTMLVideoElement
  private readonly grid: BeatGrid
  private readonly loop: LoopRegion | null
  private readonly position: () => number
  private readonly gaplessActive: () => boolean
  private readonly gain: GainNode
  private readonly pending = new Set<OscillatorNode>()
  private timer: number | null = null
  private through = 0
  private anchor: { at: number; position: number } | null = null
  private waiting = false

  constructor(
    context: AudioContext,
    video: HTMLVideoElement,
    grid: BeatGrid,
    loop: LoopRegion | null,
    position: () => number,
    gaplessActive: () => boolean,
    volume: number,
  ) {
    this.context = context
    this.video = video
    this.grid = grid
    this.loop = loop
    this.position = position
    this.gaplessActive = gaplessActive
    this.gain = context.createGain()
    this.gain.gain.value = volume
    this.gain.connect(context.destination)
  }

  start(): void {
    this.waiting = this.video.paused || this.video.readyState < HTMLMediaElement.HAVE_FUTURE_DATA
    this.video.addEventListener('playing', this.onPlaying)
    this.video.addEventListener('waiting', this.onWaiting)
    this.video.addEventListener('pause', this.onPause)
    this.video.addEventListener('ended', this.onPause)
    this.video.addEventListener('seeking', this.onSeeking)
    this.video.addEventListener('seeked', this.onSeeked)
    this.video.addEventListener('ratechange', this.reset)
    this.tick()
    this.timer = window.setInterval(this.tick, INTERVAL_MS)
  }

  setVolume(volume: number): void {
    this.gain.gain.setValueAtTime(volume, this.context.currentTime)
  }

  dispose(): void {
    if (this.timer !== null) window.clearInterval(this.timer)
    this.video.removeEventListener('playing', this.onPlaying)
    this.video.removeEventListener('waiting', this.onWaiting)
    this.video.removeEventListener('pause', this.onPause)
    this.video.removeEventListener('ended', this.onPause)
    this.video.removeEventListener('seeking', this.onSeeking)
    this.video.removeEventListener('seeked', this.onSeeked)
    this.video.removeEventListener('ratechange', this.reset)
    this.reset()
    this.gain.disconnect()
  }

  private readonly reset = () => {
    for (const oscillator of this.pending) oscillator.stop()
    this.pending.clear()
    this.through = 0
    this.anchor = null
  }

  private readonly onPlaying = () => {
    if (!this.waiting) return
    this.waiting = false
    this.reset()
    this.tick()
  }

  private readonly onWaiting = () => {
    if (this.gaplessActive()) return
    this.waiting = true
    this.reset()
  }

  private readonly onPause = () => {
    this.waiting = true
    this.reset()
  }

  private readonly onSeeking = () => {
    if (this.gaplessActive()) return
    this.waiting = true
    this.reset()
  }

  private readonly onSeeked = () => {
    if (this.gaplessActive()) return
    this.waiting = this.video.paused || this.video.readyState < HTMLMediaElement.HAVE_FUTURE_DATA
    this.reset()
    this.tick()
  }

  private readonly tick = () => {
    if (this.waiting || this.video.paused || this.context.state !== 'running') return
    const now = this.context.currentTime
    const heard = Math.min(now, heardTime(this.context))
    const position = this.position()
    const rate = this.video.playbackRate
    if (this.anchor) {
      const expected = metronomePosition(
        this.anchor.position,
        (heard - this.anchor.at) * rate,
        this.loop,
      )
      if (metronomeDrift(position, expected, this.loop) > MAX_DRIFT_SECONDS) this.reset()
    }
    this.anchor = { at: heard, position }
    const from = Math.max(0, this.through - heard, now - heard)
    const to = now + LOOKAHEAD_SECONDS - heard
    for (const click of planMetronomeClicks(this.grid, position, rate, from, to, this.loop)) {
      this.click(heard + click.offset, click.accent)
    }
    this.through = Math.max(this.through, now + LOOKAHEAD_SECONDS)
  }

  private click(at: number, accent: boolean): void {
    const oscillator = this.context.createOscillator()
    const envelope = this.context.createGain()
    oscillator.type = 'sine'
    oscillator.frequency.value = accent ? 1500 : 1000
    envelope.gain.setValueAtTime(0.0001, at)
    envelope.gain.exponentialRampToValueAtTime(0.7, at + 0.002)
    envelope.gain.exponentialRampToValueAtTime(0.0001, at + 0.045)
    oscillator.connect(envelope).connect(this.gain)
    oscillator.onended = () => {
      this.pending.delete(oscillator)
      oscillator.disconnect()
      envelope.disconnect()
    }
    this.pending.add(oscillator)
    oscillator.start(at)
    oscillator.stop(at + 0.05)
  }
}

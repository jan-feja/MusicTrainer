import type { BeatGrid } from '../beats/beatGrid'
import { heardTime } from '../player/audioClock'
import type { LoopRegion } from '../player/loop'
import { metronomeDrift, metronomePosition, planMetronomeClicks } from './metronome'

const LOOKAHEAD_SECONDS = 0.2
const INTERVAL_MS = 25
/** A jump this large on the song clock is a seek: the planned clicks are dropped. */
const MAX_DRIFT_SECONDS = 0.12
/** A drift this large on two ticks in a row is followed at once instead of gradually. */
const RESYNC_SECONDS = 0.025
/** The song clock is averaged over about this many ticks. */
const SMOOTHING_TICKS = 20

interface Anchor {
  /** Audio-clock time at which `position` is heard; corrected as the clocks are compared. */
  at: number
  /** Song position the clicks are planned from; fixed until the next reset. */
  readonly position: number
}

/**
 * Schedules short synthesized clicks on the audio clock while following the player.
 *
 * The player's position is read on every tick, but `video.currentTime` moves
 * in uneven steps (about ±5 ms in Chrome). Planning each tick's clicks from
 * the raw reading moved the boundary between ticks with it, so beats near it
 * were scheduled twice or not at all. Instead, clicks are planned from a fixed
 * anchor, and how far ahead they are planned is kept relative to it, so each
 * beat falls in exactly one tick. Only the anchor's time follows the player:
 * averaged against small jitter, at once for a lasting offset, and from
 * scratch after a seek. A new anchor waits until the player's clock runs:
 * Chrome holds `currentTime` still for ~40 ms after playback starts.
 */
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
  private anchor: Anchor | null = null
  /** Clicks are planned up to this many audio-clock seconds after the anchor. */
  private through = 0
  /** Readings averaged into the anchor's time since it was set or moved. */
  private samples = 0
  /** Ticks in a row whose drift exceeded RESYNC_SECONDS. */
  private outliers = 0
  /** Without an anchor: the position read on the last tick, and on how many ticks in a row it moved. */
  private lastPosition: number | null = null
  private moves = 0
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
    this.anchor = null
    this.lastPosition = null
    this.moves = 0
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
    const rate = this.video.playbackRate
    const anchor = this.follow(heard, this.position(), rate)
    if (!anchor) return
    // offsets from the anchor: a beat's offset stays the same while the anchor's time is corrected
    const from = Math.max(this.through, now - anchor.at)
    const to = now + LOOKAHEAD_SECONDS - anchor.at
    const clicks = planMetronomeClicks(this.grid, anchor.position, rate, from, to, this.loop)
    for (const click of clicks) this.click(Math.max(now, anchor.at + click.offset), click.accent)
    this.through = Math.max(this.through, to)
  }

  /**
   * Compare the player's position with the anchor's and correct the anchor's time.
   * Null when no clicks should be planned from this reading.
   */
  private follow(heard: number, position: number, rate: number): Anchor | null {
    const { anchor } = this
    if (anchor) {
      const expected = metronomePosition(anchor.position, (heard - anchor.at) * rate, this.loop)
      const drift = metronomeDrift(position, expected, this.loop)
      if (Math.abs(drift) <= RESYNC_SECONDS) {
        // the running mean of the readings, then a moving average over SMOOTHING_TICKS
        this.outliers = 0
        this.samples = Math.min(this.samples + 1, SMOOTHING_TICKS)
        anchor.at -= drift / rate / this.samples
        return anchor
      }
      if (Math.abs(drift) <= MAX_DRIFT_SECONDS) {
        // an odd reading: plan nothing until the next one shows whether the offset lasts
        // (another clock took over) and is to be followed
        this.outliers += 1
        if (this.outliers < 2) return null
        anchor.at -= drift / rate
        this.samples = 1
        this.outliers = 0
        return anchor
      }
      this.reset()
    }
    // after starting or seeking, the position read may jump and then stand still until the
    // sound starts (Chrome: ~40 ms): anchor once it has moved on two ticks in a row
    const moved = this.lastPosition !== null && position !== this.lastPosition
    this.moves = moved ? this.moves + 1 : 0
    this.lastPosition = position
    if (this.moves < 2) return null
    const fresh = { at: heard, position }
    this.anchor = fresh
    this.through = 0
    this.samples = 1
    this.outliers = 0
    return fresh
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

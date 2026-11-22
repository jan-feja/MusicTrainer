/**
 * Gapless A–B loops.
 *
 * Seeking a <video> silences it while the browser's media pipeline restarts
 * (measured: 5–190 ms per jump), so jumping back to the loop start leaves a
 * gap. Instead, when the video reaches the loop end, the loop's sound is taken
 * over by Web Audio: the audio around the loop is fetched once from the
 * backend as WAV and played by a time stretcher (Signalsmith Stretch), which
 * loops it sample-exactly and keeps the pitch at any speed. The video goes on
 * muted and follows the sound.
 *
 * The video gets the sound back when the user pauses, seeks out of the loop
 * or turns it off. When anything is unsupported or fails, the caller keeps
 * jumping back the plain way.
 */
import type { StretchNode } from 'signalsmith-stretch'
import { clamp } from '../../lib/math'
import {
  type ElementAudio,
  elementAudioFor,
  fadeTo,
  heardTime,
  releaseElementAudio,
  routeElement,
} from './elementAudio'
import type { LoopRegion } from './loop'
import {
  type AudioWindow,
  type LoopSchedule,
  audioWindowFor,
  handoverTime,
  rescheduled,
  scheduledPosition,
  windowCovers,
} from './loopSchedule'

/** Spare time on top of the stretcher's latency when scheduling the takeover. */
const SCHEDULE_MARGIN = 0.03
/** Look out for the loop end this much earlier than strictly needed (animation frames vary). */
const LOOKAHEAD_EXTRA = 0.1
/** Crossfade between the video's sound and the loop's, against clicks. */
const FADE = 0.004
/** The muted video is sent to the sound's position when further away than this. */
const MAX_VIDEO_DRIFT = 0.12
/** After a seek, small drifts wait this long before another seek (slow seeks would chase each other). */
const RESEEK_PAUSE_MS = 1000
/** A drift this large (a wrap) is followed at once. */
const LARGE_DRIFT = 0.5
/** Stop waiting for the 'seeked' of our seek after this long (should it never arrive). */
const SEEK_TIMEOUT_MS = 2000
/** Handing the sound back, a video this close to the sound needs no seek. */
const HANDBACK_TOLERANCE = 0.03
/** Longest stretch of audio held in the browser (the backend's limit). */
const MAX_WINDOW_SECONDS = 900
/** With only the loop start set, audio this far past it is fetched ahead. */
const EXPECTED_LOOP_SECONDS = 20

async function fetchAudio(
  url: string,
  window: AudioWindow,
  context: BaseAudioContext,
): Promise<AudioBuffer> {
  const query = new URLSearchParams({
    start: window.start.toFixed(3),
    end: window.end.toFixed(3),
    sampleRate: String(context.sampleRate),
  })
  const response = await fetch(`${url}?${query}`)
  if (!response.ok) throw new Error(`audio request failed: ${response.status}`)
  return context.decodeAudioData(await response.arrayBuffer())
}

export class GaplessLoop {
  static isSupported(): boolean {
    return typeof AudioWorkletNode !== 'undefined' && typeof WebAssembly !== 'undefined'
  }

  private readonly video: HTMLVideoElement
  private readonly audioUrl: string
  private readonly removeListeners: () => void
  private audio: ElementAudio | null = null
  private node: StretchNode | null = null
  private loopGain: GainNode | null = null
  /** How far ahead the takeover is scheduled: the stretcher's latency and a margin. */
  private ahead = 0.2
  /** The audio the stretcher holds. */
  private window: AudioWindow | null = null
  private loading = false
  private failed = false
  private disposed = false
  /** The loop to play, or null when looping is off. */
  private region: LoopRegion | null = null
  /** A loop expected soon (only its start is set), whose audio is fetched ahead. */
  private expected: LoopRegion | null = null
  /** What the loop plays; null while the video has the sound. */
  private schedule: LoopSchedule | null = null
  /** The schedule replaced by the current one, still heard until the current one's start. */
  private previous: LoopSchedule | null = null
  /** Target of our own seek of the video until its 'seeked', to tell it from the user's seeks. */
  private ownSeekTarget: number | null = null
  private seekStartedAt = 0
  private lastSeekDoneAt = 0
  /** How long the video takes to seek, so that it is sent a little ahead. */
  private seekLatency = 0.1
  /** Give the video its sound back once our seek is done. */
  private unmuteAfterSeek = false

  constructor(video: HTMLVideoElement, audioUrl: string) {
    this.video = video
    this.audioUrl = audioUrl
    const listeners: [string, () => void][] = [
      ['pause', this.onPause],
      ['play', this.onPlay],
      ['seeking', this.onSeeking],
      ['seeked', this.onSeeked],
      ['ratechange', this.onRateChange],
      ['volumechange', this.onVolumeChange],
    ]
    listeners.forEach(([name, listener]) => video.addEventListener(name, listener))
    this.removeListeners = () =>
      listeners.forEach(([name, listener]) => video.removeEventListener(name, listener))
  }

  /** True while the loop, not the video, plays the sound. */
  get active(): boolean {
    return this.schedule !== null
  }

  /** The loop to play (shifted by any lead), or null when looping is off. */
  setRegion(region: LoopRegion | null): void {
    this.region = region
    if (!region) {
      this.handBack(true)
    } else if (!this.covers(region)) {
      this.handBack(true)
      this.load()
    } else if (this.schedule) {
      this.reschedule({ start: region.start, end: region.end })
    }
  }

  /** Only the loop start is set: fetch the audio after it, so the loop is ready when its end is set. */
  expectLoopAt(start: number | null): void {
    this.expected = start === null ? null : { start, end: start + EXPECTED_LOOP_SECONDS }
    if (!this.region) this.load()
  }

  /**
   * Call on every animation frame while the video plays. False means the loop
   * cannot play gapless (yet), and the caller should jump back the plain way.
   */
  tick(): boolean {
    const { region, audio, node, video } = this
    if (!region || !audio || !node || !this.covers(region)) return false
    if (audio.context.state !== 'running') return false
    if (!audio.gain) routeElement(this.video, audio)
    if (this.schedule) {
      this.followSound()
      return true
    }
    const at = handoverTime(
      audio.context.currentTime,
      video.currentTime,
      video.playbackRate,
      region.end,
      this.ahead,
      this.ahead + LOOKAHEAD_EXTRA,
    )
    if (at !== null) this.takeOver(at)
    return true
  }

  /** The song time being heard while the loop plays the sound; otherwise null. */
  position(): number | null {
    const { schedule, audio } = this
    if (!schedule || !audio) return null
    const now = heardTime(audio.context)
    if (now >= schedule.at) return scheduledPosition(schedule, now)
    return this.previous ? scheduledPosition(this.previous, now) : null
  }

  dispose(): void {
    this.handBack(false)
    this.unmuteVideo()
    this.disposed = true
    this.removeListeners()
    this.node?.disconnect()
    this.loopGain?.disconnect()
    void this.node?.dropBuffers()
    if (this.audio) releaseElementAudio(this.video)
  }

  private covers(region: LoopRegion): boolean {
    return this.window !== null && windowCovers(this.window, region, this.video.duration)
  }

  /** Fetch the audio for the loop (or the expected one) unless it is there. */
  private load(): void {
    const wanted = this.region ?? this.expected
    if (!wanted || this.loading || this.failed || this.disposed || this.covers(wanted)) return
    const duration = this.video.duration
    if (!Number.isFinite(duration) || duration <= 0) return
    const window = audioWindowFor(wanted, duration)
    if (window.end - window.start > MAX_WINDOW_SECONDS) return
    this.loading = true
    this.fill(window)
      .catch((error: unknown) => {
        this.failed = true
        console.warn('Gapless loop unavailable, jumping back the plain way:', error)
      })
      .finally(() => {
        this.loading = false
        // the loop may have moved meanwhile
        this.load()
      })
  }

  private async fill(window: AudioWindow): Promise<void> {
    this.audio ??= elementAudioFor(this.video)
    const { context } = this.audio
    const [node, buffer] = await Promise.all([
      this.stretchNode(context),
      fetchAudio(this.audioUrl, window, context),
    ])
    if (this.disposed) return
    const channels = [0, 1].map((channel) => {
      const samples = new Float32Array(buffer.length)
      buffer.copyFromChannel(samples, Math.min(channel, buffer.numberOfChannels - 1))
      return samples
    })
    this.handBack(true)
    this.window = null
    await node.dropBuffers()
    await node.addBuffers(
      channels,
      channels.map((samples) => samples.buffer),
    )
    this.window = { start: window.start, end: window.start + buffer.duration }
  }

  private async stretchNode(context: AudioContext): Promise<StretchNode> {
    if (this.node) return this.node
    const { default: SignalsmithStretch } = await import('signalsmith-stretch')
    const node = await SignalsmithStretch(context)
    const gain = context.createGain()
    gain.gain.value = 0
    node.connect(gain).connect(context.destination)
    this.ahead = (await node.latency()) + SCHEDULE_MARGIN
    this.node = node
    this.loopGain = gain
    return node
  }

  private takeOver(at: number): void {
    const { region, audio, loopGain } = this
    if (!region || !audio?.gain || !loopGain) return
    const schedule = {
      at,
      from: region.start,
      rate: this.video.playbackRate,
      start: region.start,
      end: region.end,
    }
    this.play(schedule)
    fadeTo(audio.gain, 0, at)
    fadeTo(loopGain, this.volume(), at)
    this.schedule = schedule
    this.previous = null
  }

  /** Change rate, loop points or position while the loop plays. */
  private reschedule(
    changes: Partial<Pick<LoopSchedule, 'rate' | 'start' | 'end'>>,
    from?: number,
  ): void {
    const { schedule, audio } = this
    if (!schedule || !audio) return
    // a takeover not heard yet keeps its time
    const at = Math.max(audio.context.currentTime, schedule.at)
    const next = rescheduled(schedule, at, changes, from)
    this.play(next)
    if (schedule.at < at) this.previous = schedule
    this.schedule = next
  }

  private play(schedule: LoopSchedule): void {
    if (!this.node || !this.window) return
    const offset = this.window.start
    void this.node.schedule({
      active: true,
      output: schedule.at,
      input: schedule.from - offset,
      rate: schedule.rate,
      loopStart: schedule.start - offset,
      loopEnd: schedule.end - offset,
    })
  }

  /** Give the sound back to the video, moving the video to what was heard if asked. */
  private handBack(reposition: boolean): void {
    const { schedule, audio, node, loopGain } = this
    if (!schedule || !audio || !node || !loopGain) return
    const position = this.position()
    const now = audio.context.currentTime
    void node.schedule({ active: false, output: now })
    fadeTo(loopGain, 0, now + FADE)
    this.schedule = null
    this.previous = null
    const seek =
      reposition &&
      position !== null &&
      Math.abs(this.video.currentTime - position) > HANDBACK_TOLERANCE
    if (seek) {
      this.unmuteAfterSeek = true
      this.seekVideo(position)
    } else if (audio.gain) {
      fadeTo(audio.gain, 1, now + FADE)
    }
  }

  /** Keep the muted video near the sound. */
  private followSound(): void {
    const { schedule, audio } = this
    const position = this.position()
    // 'seeking' turns false before 'seeked' arrives: wait for our seek's event, not the flag
    if (!schedule || !audio || position === null || this.video.seeking) return
    if (this.ownSeekTarget !== null) {
      if (performance.now() - this.seekStartedAt < SEEK_TIMEOUT_MS) return
      this.ownSeekTarget = null
    }
    const drift = Math.abs(this.video.currentTime - position)
    if (drift <= MAX_VIDEO_DRIFT) return
    if (drift < LARGE_DRIFT && performance.now() - this.lastSeekDoneAt < RESEEK_PAUSE_MS) return
    // the video shows the new frame only once it has seeked: send it where the sound will be then
    this.seekVideo(scheduledPosition(schedule, heardTime(audio.context) + this.seekLatency))
  }

  private seekVideo(time: number): void {
    this.ownSeekTarget = time
    this.seekStartedAt = performance.now()
    this.video.currentTime = time
  }

  /** While seeking, the video reports the requested time exactly: ours or the user's. */
  private isOwnSeek(): boolean {
    const target = this.ownSeekTarget
    return target !== null && Math.abs(this.video.currentTime - target) < 0.001
  }

  /** The sound back to the video after a seek that waited for it. */
  private unmuteVideo(): void {
    if (!this.unmuteAfterSeek || !this.audio?.gain) return
    this.unmuteAfterSeek = false
    fadeTo(this.audio.gain, 1, this.audio.context.currentTime + FADE)
  }

  private volume(): number {
    return this.video.muted ? 0 : this.video.volume
  }

  private readonly onSeeking = () => {
    if (this.isOwnSeek()) return
    this.ownSeekTarget = null
    this.unmuteVideo()
    if (!this.schedule) return
    // the user moved the playhead: inside the loop the sound follows at once, elsewhere the video plays it
    const time = this.video.currentTime
    const { region } = this
    if (region && time >= region.start && time < region.end) this.reschedule({}, time)
    else this.handBack(false)
  }

  private readonly onSeeked = () => {
    // a user seek clears the target; a newer seek in progress makes this event a stale one.
    // (Not compared with the target: the video may have played on before the event arrives.)
    if (this.ownSeekTarget === null || this.video.seeking) return
    const now = performance.now()
    const took = (now - this.seekStartedAt) / 1000
    // follow slower seeks at once, faster ones gradually
    const latency = took > this.seekLatency ? took : 0.5 * this.seekLatency + 0.5 * took
    this.seekLatency = clamp(latency, 0.02, 0.6)
    this.ownSeekTarget = null
    this.lastSeekDoneAt = now
    this.unmuteVideo()
  }

  private readonly onPause = () => {
    if (!this.schedule) return
    if (this.video.ended) {
      // a loop up to the end of the media: the muted video got there first, so keep it going
      const position = this.position()
      if (position !== null) this.seekVideo(position)
      this.video.play().catch(() => {})
      return
    }
    this.handBack(true)
  }

  private readonly onPlay = () => {
    if (this.audio?.context.state === 'suspended') void this.audio.context.resume()
  }

  private readonly onRateChange = () => {
    if (this.schedule) this.reschedule({ rate: this.video.playbackRate })
  }

  private readonly onVolumeChange = () => {
    if (this.schedule && this.loopGain && this.audio) {
      fadeTo(this.loopGain, this.volume(), this.audio.context.currentTime + FADE)
    }
  }
}

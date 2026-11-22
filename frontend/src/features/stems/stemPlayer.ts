/**
 * Plays a song's stems in place of the video's own sound.
 *
 *   stem buffer source (playbackRate = speed) → gain (volume / mute / solo) ─┐
 *   … one per stem …                                                         ├→ ONE Signalsmith node → volume → speakers
 *                                                                            ┘   (pitch shifted back: −12·log2(speed))
 *
 * One time stretcher after the mix, as tested in docs/implementation-report.md
 * (20× faster than real time; one stretcher per stem managed only 3×). The
 * buffer sources keep all stems sample-exactly together, and loop with their
 * own loop points, so loops have no gap.
 *
 * The <video> stays in charge of play, pause, seeking, speed and volume: this
 * follows its events. Its own sound is faded out through Web Audio (its volume
 * and mute stay the user's), and while the stems play, the video is kept near
 * the sound, as the gapless loop does (gaplessLoop.ts).
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
} from '../player/elementAudio'
import type { LoopRegion } from '../player/loop'
import { type LoopSchedule, scheduledPosition } from '../player/loopSchedule'
import type { StemTrack } from './stems'
import { semitonesFor, stemSchedule } from './stemTiming'

/** Sources start this far ahead, so all of them start together. */
const START_AHEAD = 0.03
/** Crossfade when the sound jumps (seek, loop restart), against clicks. */
const FADE = 0.01
/**
 * The muted video is sent to the sound's position when further away than this.
 * Tighter than the gapless loop's 0.12 s: the stems play a whole song, and a
 * picture this far ahead of the sound starts to show.
 */
const MAX_VIDEO_DRIFT = 0.07
/** After a seek, small drifts wait this long before another seek (slow seeks would chase each other). */
const RESEEK_PAUSE_MS = 1000
/** A drift this large (a wrap) is followed at once. */
const LARGE_DRIFT = 0.5
/** Stop waiting for the 'seeked' of our seek after this long (should it never arrive). */
const SEEK_TIMEOUT_MS = 2000
/** On pause, a video this close to the sound is left where it is. */
const PAUSE_TOLERANCE = 0.03

interface Voice {
  sources: AudioBufferSourceNode[]
  /** One per stem, in the order of the tracks. */
  gains: GainNode[]
  out: GainNode
}

export class StemPlayer {
  static isSupported(): boolean {
    return typeof AudioWorkletNode !== 'undefined' && typeof WebAssembly !== 'undefined'
  }

  private readonly video: HTMLVideoElement
  private readonly tracks: StemTrack[]
  private readonly audio: ElementAudio
  private readonly output: GainNode
  private readonly removeListeners: () => void
  private stretch: StretchNode | null = null
  /** How long the stretcher delays the sound. */
  private latency = 0.1
  private region: LoopRegion | null
  private gains: Record<string, number>
  private voice: Voice | null = null
  /** What the stems play; null while paused. */
  private schedule: LoopSchedule | null = null
  private disposed = false
  /** The video's own sound is faded out. */
  private videoSilenced = false
  /** Target of our own seek of the video until its 'seeked', to tell it from the user's seeks. */
  private ownSeekTarget: number | null = null
  private seekStartedAt = 0
  private lastSeekDoneAt = 0
  /** How long the video takes to seek, so that it is sent a little ahead. */
  private seekLatency = 0.1

  constructor(
    video: HTMLVideoElement,
    tracks: StemTrack[],
    gains: Record<string, number>,
    region: LoopRegion | null,
  ) {
    this.video = video
    this.tracks = tracks
    this.gains = gains
    this.region = region
    this.audio = elementAudioFor(video)
    this.output = this.audio.context.createGain()
    this.output.gain.value = this.volume()
    this.output.connect(this.audio.context.destination)
    const listeners: [string, () => void][] = [
      ['play', this.onPlay],
      ['pause', this.onPause],
      ['seeking', this.onSeeking],
      ['seeked', this.onSeeked],
      ['ratechange', this.onRateChange],
      ['volumechange', this.onVolumeChange],
    ]
    listeners.forEach(([name, listener]) => video.addEventListener(name, listener))
    this.removeListeners = () =>
      listeners.forEach(([name, listener]) => video.removeEventListener(name, listener))
    this.init().catch((error: unknown) => {
      console.warn('Stem player unavailable, playing the video’s own sound:', error)
    })
  }

  /** True while the stems, not the video, play the sound. */
  get active(): boolean {
    return this.schedule !== null
  }

  /**
   * Call on every animation frame while the video plays. False means the stems
   * cannot play (yet): the video's own sound is heard.
   */
  tick(): boolean {
    const { stretch, audio, video } = this
    if (!stretch || this.disposed) return false
    if (audio.context.state !== 'running') {
      void audio.context.resume()
      return false
    }
    if (!this.videoSilenced) {
      fadeTo(routeElement(video, audio), 0, audio.context.currentTime + FADE, FADE)
      this.videoSilenced = true
    }
    if (!this.schedule) {
      // the video plays on while the sound starts: start where it will be when heard
      const outputDelay = audio.context.currentTime - heardTime(audio.context)
      const ahead = START_AHEAD + this.latency + Math.max(0, outputDelay)
      this.start(video.currentTime + ahead * video.playbackRate)
    }
    this.followSound()
    return true
  }

  /** The song time being heard while the stems play; otherwise null. */
  position(): number | null {
    if (!this.schedule) return null
    return scheduledPosition(this.schedule, heardTime(this.audio.context) - this.latency)
  }

  /** The loop to play (shifted by any lead), or null when looping is off. */
  setRegion(region: LoopRegion | null): void {
    this.region = region
    const { schedule } = this
    if (!schedule) return
    const now = this.audio.context.currentTime
    const position = scheduledPosition(schedule, now)
    if (region && position >= region.end) {
      this.start(region.start)
      return
    }
    this.schedule = stemSchedule(now, position, schedule.rate, region)
    for (const source of this.voice?.sources ?? []) this.setLoop(source, region)
  }

  /** Gain per stem name: volume, mute and solo. */
  setGains(gains: Record<string, number>): void {
    this.gains = gains
    const now = this.audio.context.currentTime
    this.voice?.gains.forEach((gain, index) => {
      fadeTo(gain, gains[this.tracks[index].name] ?? 1, now + FADE, FADE)
    })
  }

  dispose(): void {
    this.disposed = true
    this.removeListeners()
    this.stopVoice()
    this.schedule = null
    const { audio } = this
    if (audio.gain) fadeTo(audio.gain, 1, audio.context.currentTime + FADE, FADE)
    this.stretch?.disconnect()
    this.output.disconnect()
    releaseElementAudio(this.video)
  }

  private async init(): Promise<void> {
    const { context } = this.audio
    const { default: SignalsmithStretch } = await import('signalsmith-stretch')
    const stretch = await SignalsmithStretch(context)
    if (this.disposed) {
      stretch.disconnect()
      return
    }
    stretch.connect(this.output)
    this.latency = await stretch.latency()
    await stretch.schedule({ active: true, semitones: semitonesFor(this.video.playbackRate) })
    this.stretch = stretch
  }

  /** Play the stems from song time `from`, replacing what plays now. */
  private start(from: number): void {
    const { context } = this.audio
    if (!this.stretch) return
    const at = context.currentTime + START_AHEAD
    const schedule = stemSchedule(at, from, this.video.playbackRate, this.region)
    this.stopVoice(at)
    const out = context.createGain()
    out.gain.value = 0
    fadeTo(out, 1, at + FADE, FADE)
    out.connect(this.stretch)
    const gains: GainNode[] = []
    const sources = this.tracks.map((track) => {
      const source = context.createBufferSource()
      source.buffer = track.buffer
      source.playbackRate.value = schedule.rate
      this.setLoop(source, this.region)
      const gain = context.createGain()
      gain.gain.value = this.gains[track.name] ?? 1
      source.connect(gain).connect(out)
      gains.push(gain)
      if (schedule.from < track.buffer.duration) source.start(at, schedule.from)
      return source
    })
    this.voice = { sources, gains, out }
    this.schedule = schedule
  }

  private setLoop(source: AudioBufferSourceNode, region: LoopRegion | null): void {
    const duration = source.buffer?.duration ?? 0
    source.loop = region !== null
    if (region) {
      // a loop end past the buffer would make the source loop the whole buffer
      source.loopStart = clamp(region.start, 0, duration)
      source.loopEnd = clamp(region.end, 0, duration)
    }
  }

  /** Fade out what plays, from `at` on. */
  private stopVoice(at = this.audio.context.currentTime): void {
    const { voice } = this
    if (!voice) return
    this.voice = null
    fadeTo(voice.out, 0, at + FADE, FADE)
    for (const source of voice.sources) {
      try {
        source.stop(at + 4 * FADE)
      } catch {
        // never started (began after the end of its buffer)
      }
    }
    window.setTimeout(
      () => voice.out.disconnect(),
      (at - this.audio.context.currentTime + 0.5) * 1000,
    )
  }

  /** Keep the video near the sound. */
  private followSound(): void {
    const { schedule } = this
    const position = this.position()
    // 'seeking' turns false before 'seeked' arrives: wait for our seek's event, not the flag
    if (!schedule || position === null || this.video.seeking) return
    if (this.ownSeekTarget !== null) {
      if (performance.now() - this.seekStartedAt < SEEK_TIMEOUT_MS) return
      this.ownSeekTarget = null
    }
    const drift = Math.abs(this.video.currentTime - position)
    if (drift <= MAX_VIDEO_DRIFT) return
    if (drift < LARGE_DRIFT && performance.now() - this.lastSeekDoneAt < RESEEK_PAUSE_MS) return
    // the video shows the new frame only once it has seeked: send it where the sound will be then
    const then = heardTime(this.audio.context) - this.latency + this.seekLatency
    this.seekVideo(scheduledPosition(schedule, then))
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

  private volume(): number {
    return this.video.muted ? 0 : this.video.volume
  }

  private readonly onPlay = () => {
    // play() comes from a user gesture: the moment the context may start
    if (this.audio.context.state === 'suspended') void this.audio.context.resume()
  }

  private readonly onPause = () => {
    if (!this.schedule) return
    const position = this.position()
    if (this.video.ended && this.region) {
      // a loop up to the end of the media: the muted video got there first, so keep it going
      if (position !== null) this.seekVideo(position)
      this.video.play().catch(() => {})
      return
    }
    this.stopVoice()
    this.schedule = null
    // stay where the sound stopped, so playing on starts there
    if (position !== null && Math.abs(this.video.currentTime - position) > PAUSE_TOLERANCE) {
      this.seekVideo(position)
    }
  }

  private readonly onSeeking = () => {
    if (this.isOwnSeek()) return
    this.ownSeekTarget = null
    // the user moved the playhead: the sound follows at once
    if (this.schedule) this.start(this.video.currentTime)
  }

  private readonly onSeeked = () => {
    // a user seek clears the target; a newer seek in progress makes this event a stale one
    if (this.ownSeekTarget === null || this.video.seeking) return
    const now = performance.now()
    const took = (now - this.seekStartedAt) / 1000
    // follow slower seeks at once, faster ones gradually
    const latency = took > this.seekLatency ? took : 0.5 * this.seekLatency + 0.5 * took
    this.seekLatency = clamp(latency, 0.02, 0.6)
    this.ownSeekTarget = null
    this.lastSeekDoneAt = now
  }

  private readonly onRateChange = () => {
    const rate = this.video.playbackRate
    void this.stretch?.schedule({ semitones: semitonesFor(rate) })
    const { schedule } = this
    if (!schedule) return
    const at = this.audio.context.currentTime + START_AHEAD
    for (const source of this.voice?.sources ?? []) source.playbackRate.setValueAtTime(rate, at)
    this.schedule = stemSchedule(at, scheduledPosition(schedule, at), rate, this.region)
  }

  private readonly onVolumeChange = () => {
    fadeTo(this.output, this.volume(), this.audio.context.currentTime + FADE, FADE)
  }
}

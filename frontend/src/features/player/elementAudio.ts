/**
 * The AudioContext of a <video> element, shared by everything that plays the
 * video's sound through Web Audio: the gapless loop and the stem player.
 *
 * A media element can be routed into one AudioContext only, ever, so there is
 * one per element. Once routed, the video's own sound goes through `gain`,
 * which lets it be faded out without touching the element's volume or mute
 * (those stay the user's).
 */

export interface ElementAudio {
  context: AudioContext
  /** The video's own sound, once routed through the context. */
  gain: GainNode | null
}

/** Default crossfade, against clicks. */
const FADE = 0.004

const elementAudio = new WeakMap<HTMLMediaElement, ElementAudio>()

export function elementAudioFor(video: HTMLMediaElement): ElementAudio {
  let audio = elementAudio.get(video)
  if (!audio) {
    audio = { context: new AudioContext({ latencyHint: 'interactive' }), gain: null }
    elementAudio.set(video, audio)
  }
  return audio
}

/**
 * Send the video's sound through the context. Only while the context runs: a
 * routed video is silent while its context is suspended.
 */
export function routeElement(video: HTMLMediaElement, audio: ElementAudio): GainNode {
  if (audio.gain) return audio.gain
  const gain = audio.context.createGain()
  audio.context.createMediaElementSource(video).connect(gain).connect(audio.context.destination)
  audio.gain = gain
  return gain
}

/** Close the context unless the video is routed and still on the page (React may mount it again). */
export function releaseElementAudio(video: HTMLMediaElement): void {
  const audio = elementAudio.get(video)
  if (audio && (!audio.gain || !video.isConnected)) {
    void audio.context.close()
    elementAudio.delete(video)
  }
}

/** The audio-clock time being heard right now (shared with the metronome). */
export { heardTime } from './audioClock'

export function fadeTo(gain: GainNode, value: number, at: number, fade = FADE): void {
  const start = Math.max(gain.context.currentTime, at - fade)
  gain.gain.cancelScheduledValues(start)
  gain.gain.setTargetAtTime(value, start, fade / 4)
}

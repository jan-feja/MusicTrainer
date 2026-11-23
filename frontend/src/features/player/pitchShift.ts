import type { StretchNode } from 'signalsmith-stretch'

export const MIN_PITCH = -12
export const MAX_PITCH = 12

const FADE = 0.01

function fadeTo(gain: GainNode, value: number, at: number): void {
  const now = gain.context.currentTime
  gain.gain.cancelScheduledValues(now)
  gain.gain.setTargetAtTime(value, Math.max(now, at), FADE / 4)
}

/** A live pitch effect shared by the video's sound and the gapless loop. */
export class PitchShift {
  private readonly context: AudioContext
  private readonly input: GainNode
  private readonly dry: GainNode
  private readonly wet: GainNode
  private readonly node: StretchNode
  private readonly latency: number
  private active = false
  private audibleAt = Infinity
  private disposed = false

  private constructor(
    context: AudioContext,
    input: GainNode,
    dry: GainNode,
    wet: GainNode,
    node: StretchNode,
    latency: number,
  ) {
    this.context = context
    this.input = input
    this.dry = dry
    this.wet = wet
    this.node = node
    this.latency = latency
  }

  static async create(context: AudioContext, input: GainNode, dry: GainNode): Promise<PitchShift> {
    const { default: SignalsmithStretch } = await import('signalsmith-stretch')
    const node = await SignalsmithStretch(context)
    const wet = context.createGain()
    wet.gain.value = 0
    let connected = false
    try {
      const latency = await node.latency()
      input.connect(node)
      connected = true
      node.connect(wet).connect(context.destination)
      return new PitchShift(context, input, dry, wet, node, latency)
    } catch (error) {
      if (connected) input.disconnect(node)
      node.disconnect()
      wet.disconnect()
      throw error
    }
  }

  async set(semitones: number): Promise<void> {
    if (this.disposed) throw new Error('The pitch effect has been closed')
    const now = this.context.currentTime
    if (semitones === 0) {
      if (!this.active) return
      await this.node.schedule({ active: false, output: now + FADE * 4 })
      if (this.disposed) throw new Error('The pitch effect has been closed')
      fadeTo(this.dry, 1, now)
      fadeTo(this.wet, 0, now)
      this.active = false
      this.audibleAt = Infinity
      return
    }
    await this.node.schedule({ active: true, semitones })
    if (this.disposed) throw new Error('The pitch effect has been closed')
    if (!this.active) {
      const at = this.context.currentTime + this.latency
      fadeTo(this.dry, 0, at)
      fadeTo(this.wet, 1, at)
      this.audibleAt = at
      this.active = true
    }
  }

  delayAt(time: number): number {
    return this.active && time >= this.audibleAt ? this.latency : 0
  }

  dispose(): void {
    this.disposed = true
    const now = this.context.currentTime
    this.dry.gain.cancelScheduledValues(now)
    this.dry.gain.setValueAtTime(1, now)
    this.input.disconnect(this.node)
    this.node.disconnect()
    this.wet.disconnect()
  }
}

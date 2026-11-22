// The parts of the signalsmith-stretch package (Web Audio time stretch, MIT) the app uses.
declare module 'signalsmith-stretch' {
  export interface StretchChange {
    /** Audio-clock time the change is heard; the node makes up for its own latency. */
    output?: number
    active?: boolean
    /** Position in the node's sample buffers, in seconds. */
    input?: number
    rate?: number
    semitones?: number
    /** A section of the buffers to loop; off when both are equal. */
    loopStart?: number
    loopEnd?: number
  }

  export interface StretchNode extends AudioWorkletNode {
    schedule(change: StretchChange): Promise<unknown>
    /** Appends sample buffers (one per channel); resolves to the new end time. */
    addBuffers(channels: Float32Array[], transfer?: Transferable[]): Promise<number>
    dropBuffers(): Promise<{ start: number; end: number }>
    /** Input plus output latency, in seconds. */
    latency(): Promise<number>
  }

  export default function SignalsmithStretch(
    context: BaseAudioContext,
    options?: AudioWorkletNodeOptions,
  ): Promise<StretchNode>
}

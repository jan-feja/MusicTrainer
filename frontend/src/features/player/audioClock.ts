/** The audio-context time being heard at the output right now. */
export function heardTime(context: AudioContext): number {
  if (typeof context.getOutputTimestamp === 'function') {
    const { contextTime, performanceTime } = context.getOutputTimestamp()
    if (contextTime && performanceTime) {
      return contextTime + (performance.now() - performanceTime) / 1000
    }
  }
  return context.currentTime - (context.baseLatency || 0) - (context.outputLatency || 0)
}

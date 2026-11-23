import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PitchShift } from './pitchShift'

const stretch = vi.hoisted(() => ({
  connect: vi.fn(),
  disconnect: vi.fn(),
  latency: vi.fn(async () => 0.12),
  schedule: vi.fn(async (_change: object) => {}),
}))

vi.mock('signalsmith-stretch', () => ({ default: async () => stretch }))

function setup() {
  const context = Object.assign(Object.create(null) as AudioContext, {
    currentTime: 10,
    destination: {},
  })
  const makeGain = () =>
    Object.assign(Object.create(null) as GainNode, {
      context,
      gain: {
        value: 1,
        cancelScheduledValues: vi.fn(),
        setTargetAtTime: vi.fn(),
        setValueAtTime: vi.fn(),
      },
      connect: vi.fn(),
      disconnect: vi.fn(),
    })
  const input = makeGain()
  const dry = makeGain()
  const wet = makeGain()
  context.createGain = () => wet
  stretch.connect.mockReturnValue(wet)
  return { context, input, dry, wet }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('pitch shift', () => {
  it('shifts live input, changes semitones, and returns to the dry sound on reset', async () => {
    const { context, input, dry, wet } = setup()
    const effect = await PitchShift.create(context, input, dry)
    expect(input.connect).toHaveBeenCalledWith(stretch)
    await effect.set(3)
    expect(stretch.schedule).toHaveBeenLastCalledWith({ active: true, semitones: 3 })
    expect(dry.gain.setTargetAtTime).toHaveBeenLastCalledWith(0, 10.12, expect.any(Number))
    expect(wet.gain.setTargetAtTime).toHaveBeenLastCalledWith(1, 10.12, expect.any(Number))
    expect(effect.delayAt(10.11)).toBe(0)
    expect(effect.delayAt(10.13)).toBe(0.12)

    await effect.set(-2)
    expect(stretch.schedule).toHaveBeenLastCalledWith({ active: true, semitones: -2 })
    expect(dry.gain.setTargetAtTime).toHaveBeenCalledTimes(1)
    await effect.set(0)
    expect(stretch.schedule).toHaveBeenLastCalledWith({ active: false, output: 10.04 })
    expect(dry.gain.setTargetAtTime).toHaveBeenLastCalledWith(1, 10, expect.any(Number))
    expect(wet.gain.setTargetAtTime).toHaveBeenLastCalledWith(0, 10, expect.any(Number))
    expect(effect.delayAt(11)).toBe(0)
    effect.dispose()
    expect(input.disconnect).toHaveBeenCalledWith(stretch)
  })

  it('leaves the dry sound on when the worklet rejects a pitch change', async () => {
    const { context, input, dry, wet } = setup()
    const effect = await PitchShift.create(context, input, dry)
    stretch.schedule.mockRejectedValueOnce(new Error('worklet failed'))
    await expect(effect.set(1)).rejects.toThrow('worklet failed')
    expect(dry.gain.setTargetAtTime).not.toHaveBeenCalled()
    expect(wet.gain.setTargetAtTime).not.toHaveBeenCalled()
    effect.dispose()
  })

  it('does not fade out the dry sound if disposed while a change is pending', async () => {
    const { context, input, dry, wet } = setup()
    const effect = await PitchShift.create(context, input, dry)
    let finish = () => {}
    stretch.schedule.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve
        }),
    )
    const changing = effect.set(1)
    effect.dispose()
    finish()
    await expect(changing).rejects.toThrow('closed')
    expect(dry.gain.setValueAtTime).toHaveBeenCalledWith(1, 10)
    expect(wet.gain.setTargetAtTime).not.toHaveBeenCalled()
  })
})

import { type RefObject, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../../lib/format'
import { useLatest } from '../../lib/useLatest'
import type { BeatGrid } from '../beats/beatGrid'
import type { LoopRegion } from '../player/loop'
import { MetronomeAudio } from './metronomeAudio'

export function useMetronome(
  videoRef: RefObject<HTMLVideoElement | null>,
  grid: BeatGrid | null,
  loop: LoopRegion | null,
  position: () => number,
  gaplessActive: () => boolean,
) {
  const [enabled, setEnabled] = useState(false)
  const [starting, setStarting] = useState(false)
  const [volume, setVolume] = useState(0.3)
  const [error, setError] = useState<string | null>(null)
  const contextRef = useRef<AudioContext | null>(null)
  const audioRef = useRef<MetronomeAudio | null>(null)
  const positionRef = useLatest(position)
  const gaplessRef = useLatest(gaplessActive)
  const volumeRef = useLatest(volume)

  useEffect(() => {
    return () => {
      const context = contextRef.current
      contextRef.current = null
      if (context && context.state !== 'closed') void context.close()
    }
  }, [])

  const start = loop?.start ?? null
  const end = loop?.end ?? null
  useEffect(() => {
    const context = contextRef.current
    const video = videoRef.current
    if (!enabled || !context || !video || !grid) return
    const region = start !== null && end !== null ? { start, end } : null
    const audio = new MetronomeAudio(
      context,
      video,
      grid,
      region,
      () => positionRef.current(),
      () => gaplessRef.current(),
      volumeRef.current,
    )
    audioRef.current = audio
    audio.start()
    return () => {
      audioRef.current = null
      audio.dispose()
    }
  }, [enabled, grid, start, end, videoRef, positionRef, gaplessRef, volumeRef])

  useEffect(() => audioRef.current?.setVolume(volume), [volume])

  useEffect(() => {
    const context = contextRef.current
    if (!enabled || !context) return
    const onStateChange = () => {
      if (context.state !== 'running') {
        setError('Metronome audio was suspended. Turn it off and on to resume.')
      } else {
        setError(null)
      }
    }
    context.addEventListener('statechange', onStateChange)
    onStateChange()
    return () => context.removeEventListener('statechange', onStateChange)
  }, [enabled])

  const toggle = () => {
    if (enabled) {
      setEnabled(false)
      return
    }
    if (starting || !grid) return
    setError(null)
    try {
      const context = contextRef.current ?? new AudioContext({ latencyHint: 'interactive' })
      contextRef.current = context
      setStarting(true)
      void context.resume().then(
        () => {
          if (contextRef.current !== context) return
          setStarting(false)
          setEnabled(true)
        },
        (reason: unknown) => {
          if (contextRef.current !== context) return
          setStarting(false)
          setError(`Could not start the metronome: ${errorMessage(reason)}`)
        },
      )
    } catch (reason) {
      setError(`Could not start the metronome: ${errorMessage(reason)}`)
    }
  }

  return { enabled, starting, volume, setVolume, error, toggle }
}

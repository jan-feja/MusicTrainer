import { memo, useEffect, useMemo, useRef, useState } from 'react'
import type { TimeView } from '../player/timelineView'
import { peakBetween } from './stems'

interface StemWaveformProps {
  peaks: Float32Array
  view: TimeView
  color: string
}

/**
 * A stem's waveform over the shown part of the song, scaled to the stem's own
 * loudest moment. Drawn on a canvas, again only when the view or the size
 * changes (the player re-renders on every frame).
 */
export const StemWaveform = memo(function StemWaveform({ peaks, view, color }: StemWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const loudest = useMemo(() => peaks.reduce((max, peak) => Math.max(max, peak), 0), [peaks])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ width: Math.round(width), height: Math.round(height) })
    })
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!canvas || !context || size.width === 0) return
    const scale = window.devicePixelRatio || 1
    const width = Math.round(size.width * scale)
    const height = Math.round(size.height * scale)
    canvas.width = width
    canvas.height = height
    context.clearRect(0, 0, width, height)
    const length = view.end - view.start
    if (length <= 0 || loudest <= 0) return
    context.fillStyle = color
    const middle = height / 2
    const perPixel = length / width
    for (let x = 0; x < width; x++) {
      const start = view.start + x * perPixel
      const level = peakBetween(peaks, start, start + perPixel) / loudest
      const half = Math.max(0.5 * scale, level * (middle - scale))
      context.fillRect(x, middle - half, 1, 2 * half)
    }
  }, [peaks, view, color, size, loudest])

  return <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
})

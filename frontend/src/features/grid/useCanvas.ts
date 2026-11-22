import { type RefObject, useEffect, useState } from 'react'

/**
 * Keeps a canvas's pixel size at its CSS size times the screen's pixel ratio; returns that
 * size (0 until laid out). Draw again when it changes.
 */
export function useCanvasSize(ref: RefObject<HTMLCanvasElement | null>): {
  width: number
  height: number
} {
  const [size, setSize] = useState({ width: 0, height: 0 })
  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const update = () => {
      const ratio = window.devicePixelRatio || 1
      const width = Math.round(canvas.clientWidth * ratio)
      const height = Math.round(canvas.clientHeight * ratio)
      if (canvas.width !== width) canvas.width = width
      if (canvas.height !== height) canvas.height = height
      setSize((old) => (old.width === width && old.height === height ? old : { width, height }))
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [ref])
  return size
}

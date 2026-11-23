import { type RefObject, useEffect } from 'react'
import { clamp } from '../../lib/math'
import { useLatest } from '../../lib/useLatest'
import type { TimeView } from './timelineView'

/** Wheel sensitivity of the zoom: e^(0.002 per pixel scrolled). */
const WHEEL_ZOOM_RATE = 0.002

/**
 * Ctrl / Cmd + wheel (a pinch on a touchpad) zooms around the pointer; Shift +
 * wheel or sideways scrolling pans. A native listener, since React's wheel
 * listeners cannot stop the browser from zooming the page.
 */
export function useWheelZoom(
  barRef: RefObject<HTMLDivElement | null>,
  view: TimeView,
  duration: number,
  onZoom?: (factor: number, anchor: number) => void,
  onPan?: (seconds: number) => void,
) {
  const latest = useLatest({ view, duration, onZoom, onPan })
  useEffect(() => {
    const bar = barRef.current
    if (!bar) return
    const handleWheel = (event: WheelEvent) => {
      const { view, duration, onZoom, onPan } = latest.current
      const rect = bar.getBoundingClientRect()
      if (rect.width === 0) return
      // Firefox scrolls in lines or pages
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.width : 1
      const length = view.end - view.start
      if ((event.ctrlKey || event.metaKey) && onZoom) {
        event.preventDefault()
        const anchor = view.start + clamp((event.clientX - rect.left) / rect.width, 0, 1) * length
        onZoom(Math.exp(event.deltaY * unit * WHEEL_ZOOM_RATE), anchor)
        return
      }
      const sideways = event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)
      if (sideways && onPan && length < duration) {
        event.preventDefault()
        const delta = (event.deltaX !== 0 ? event.deltaX : event.deltaY) * unit
        onPan((delta / rect.width) * length)
      }
    }
    bar.addEventListener('wheel', handleWheel, { passive: false })
    return () => bar.removeEventListener('wheel', handleWheel)
  }, [barRef, latest])
}

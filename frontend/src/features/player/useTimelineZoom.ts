import { useCallback, useMemo, useState } from 'react'
import {
  type TimeView,
  ZOOM_STEP,
  clampView,
  fitView,
  isZoomed,
  panView,
  wholeView,
  zoomFactor,
  zoomView,
} from './timelineView'

export interface TimelineZoom {
  /** The part of the song the timeline shows. */
  view: TimeView
  zoomed: boolean
  /** 1 = the whole song, 4 = a quarter of it, ... */
  factor: number
  setView: (view: TimeView) => void
  /** Zoom by `factor` (below 1 = in) around `anchor` (default: the middle of the view). */
  zoomBy: (factor: number, anchor?: number) => void
  zoomIn: () => void
  zoomOut: () => void
  pan: (seconds: number) => void
  /** Show `region` over most of the timeline. */
  fit: (region: { start: number; end: number }) => void
  reset: () => void
}

export function useTimelineZoom(duration: number): TimelineZoom {
  // null: the whole song, whatever the duration turns out to be
  const [stored, setStored] = useState<TimeView | null>(null)
  const view = useMemo(
    () => (stored ? clampView(stored, duration) : wholeView(duration)),
    [stored, duration],
  )

  const setView = useCallback(
    (next: TimeView) => {
      const clamped = clampView(next, duration)
      setStored(isZoomed(clamped, duration) ? clamped : null)
    },
    [duration],
  )
  const zoomBy = useCallback(
    (factor: number, anchor?: number) =>
      setView(zoomView(view, factor, anchor ?? (view.start + view.end) / 2, duration)),
    [view, duration, setView],
  )

  return {
    view,
    zoomed: isZoomed(view, duration),
    factor: zoomFactor(view, duration),
    setView,
    zoomBy,
    zoomIn: () => zoomBy(1 / ZOOM_STEP),
    zoomOut: () => zoomBy(ZOOM_STEP),
    pan: (seconds) => setView(panView(view, seconds, duration)),
    fit: (region) => setView(fitView(region, duration)),
    reset: () => setStored(null),
  }
}

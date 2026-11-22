import { formatTimePrecise } from '../../lib/format'
import type { TimelineZoom } from './useTimelineZoom'
import { MIN_VIEW_SECONDS } from './timelineView'
import styles from './PlayerControls.module.css'

interface ZoomControlsProps {
  zoom: TimelineZoom
  /** The current loop, to zoom to; null without one. */
  region: { start: number; end: number } | null
}

/** Zoom the timeline in and out, to the loop, or back to the whole song. */
export function ZoomControls({ zoom, region }: ZoomControlsProps) {
  const { view, zoomed, factor } = zoom
  const atClosest = view.end - view.start <= MIN_VIEW_SECONDS + 1e-6
  return (
    <div className={styles.group} role="group" aria-label="Zoom">
      <span className={styles.groupLabel}>Zoom</span>
      <button
        type="button"
        className="icon-button icon-button-small"
        onClick={zoom.zoomOut}
        disabled={!zoomed}
        aria-label="Zoom out"
        title="Zoom out (Ctrl + scroll on the timeline)"
      >
        −
      </button>
      <button
        type="button"
        className="icon-button icon-button-small"
        onClick={zoom.zoomIn}
        disabled={atClosest || view.end <= 0}
        aria-label="Zoom in"
        title="Zoom in (Ctrl + scroll on the timeline)"
      >
        +
      </button>
      <button
        type="button"
        className="button button-small"
        onClick={() => region && zoom.fit(region)}
        disabled={!region}
        title="Show the loop over the whole timeline (Z)"
      >
        Fit loop
      </button>
      <button
        type="button"
        className="button button-small button-ghost"
        onClick={zoom.reset}
        disabled={!zoomed}
        title="Show the whole song (Z)"
      >
        Whole song
      </button>
      {zoomed && (
        <span className={styles.loopLength}>
          {formatTimePrecise(view.start)}–{formatTimePrecise(view.end)} ({Math.round(factor)}×)
        </span>
      )}
    </div>
  )
}

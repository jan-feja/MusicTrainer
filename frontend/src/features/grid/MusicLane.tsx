import { useEffect, useRef } from 'react'
import { type TimeView, visibleRange } from '../player/timelineView'
import { drawColors, drawLines, drawSpectrogram } from './drawMusic'
import type { MusicPicture } from './musicVisual'
import { useCanvasSize } from './useCanvas'
import styles from './GridEditor.module.css'

/** Beat lines are drawn once this few are in view, bar lines once this few bars. */
const MAX_BEAT_LINES = 160
const MAX_BAR_LINES = 120
const COLOR_STRIP = 0.16 // share of the lane's height

interface MusicLaneProps {
  picture: MusicPicture
  view: TimeView
  beats: readonly number[]
  bars: readonly number[]
  currentTime: number
  onSeek: (time: number) => void
}

/**
 * The music under the timeline: on top, the section colors (similar music, similar color);
 * below, the spectrogram (low notes at the bottom, attacks as vertical lines) with the bar
 * lines of the grid.
 */
export function MusicLane({ picture, view, beats, bars, currentTime, onSeek }: MusicLaneProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { width, height } = useCanvasSize(canvasRef)

  useEffect(() => {
    const context = canvasRef.current?.getContext('2d')
    if (!context || width === 0) return
    context.clearRect(0, 0, width, height)
    const strip = Math.round(height * COLOR_STRIP)
    drawColors(context, picture, view.start, view.end, 0, 0, width, strip - 1)
    drawSpectrogram(context, picture, view.start, view.end, 0, strip, width, height - strip)
    const [first, last] = visibleRange(beats, view)
    if (last - first <= MAX_BEAT_LINES) {
      drawLines(
        context,
        beats,
        view.start,
        view.end,
        0,
        strip,
        width,
        height - strip,
        'rgb(255 255 255 / 22%)',
      )
    }
    const [firstBar, lastBar] = visibleRange(bars, view)
    if (lastBar - firstBar > MAX_BAR_LINES) return
    drawLines(
      context,
      bars,
      view.start,
      view.end,
      0,
      0,
      width,
      height,
      'rgb(255 255 255 / 75%)',
      1.5,
    )
  }, [picture, view, beats, bars, width, height])

  const length = view.end - view.start
  const playhead = length > 0 ? ((currentTime - view.start) / length) * 100 : -1
  return (
    <div className={styles.musicLane}>
      <canvas
        ref={canvasRef}
        className={styles.canvas}
        onPointerDown={(event) => {
          const rect = event.currentTarget.getBoundingClientRect()
          onSeek(view.start + ((event.clientX - rect.left) / rect.width) * length)
        }}
        aria-label="Music: section colors and spectrogram with the bar lines; click to go there"
        role="img"
      />
      {playhead >= 0 && playhead <= 100 && (
        <span className={styles.playhead} style={{ left: `${playhead}%` }} aria-hidden="true" />
      )}
    </div>
  )
}

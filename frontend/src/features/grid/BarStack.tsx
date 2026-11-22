import { type PointerEvent, useEffect, useMemo, useRef } from 'react'
import { stackRows } from './barRows'
import { drawLines, drawSpectrogram } from './drawMusic'
import type { MusicPicture } from './musicVisual'
import { useCanvasSize } from './useCanvas'
import styles from './GridEditor.module.css'

const ROW_HEIGHT = 24 // CSS pixels
const LABEL_WIDTH = 34
/** Each row starts this share of the longest bar before its bar start (to show it). */
const LEAD_IN = 0.06

interface BarStackProps {
  picture: MusicPicture
  beats: readonly number[]
  bars: readonly number[]
  /** Show the bars that start in [start, end). */
  start: number
  end: number
  currentTime: number
  /** With more bars than fit, the rows around this time. */
  focus: number
  onSeek: (time: number) => void
}

/**
 * Every bar a row, one under another, each starting at its bar start, as long as it lasts:
 * when the bars are right, the rows look alike and the bright marks (where the beat network
 * hears a bar start) sit at their left edge; a bar of another length sticks out. Click a
 * row to go to that bar.
 */
export function BarStack({
  picture,
  beats,
  bars,
  start,
  end,
  currentTime,
  focus,
  onSeek,
}: BarStackProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  // the rows follow the focus in steps (they only move when there are more than fit)
  const step = Math.floor(focus / 4) * 4
  const rows = useMemo(() => stackRows(bars, start, end, step), [bars, start, end, step])
  const longest = rows.reduce((max, row) => Math.max(max, row.end - row.start), 0)
  const span = longest * (1 + LEAD_IN)
  const { width, height } = useCanvasSize(canvasRef)

  useEffect(() => {
    const context = canvasRef.current?.getContext('2d')
    if (!context || width === 0 || rows.length === 0) return
    const ratio = width / (canvasRef.current?.clientWidth || width)
    const rowHeight = ROW_HEIGHT * ratio
    const label = LABEL_WIDTH * ratio
    const plot = width - label
    context.clearRect(0, 0, width, height)
    context.font = `${11 * ratio}px system-ui, sans-serif`
    context.textBaseline = 'middle'
    rows.forEach((row, i) => {
      const y = i * rowHeight
      const from = row.start - longest * LEAD_IN
      const rowWidth = ((row.end - from) / span) * plot
      drawSpectrogram(
        context,
        picture,
        from,
        row.end,
        label,
        y + 1,
        rowWidth,
        rowHeight - 7 * ratio,
      )
      if (picture.downbeat) {
        drawNetworkBars(
          context,
          picture,
          from,
          row.end,
          label,
          y + rowHeight - 6 * ratio,
          rowWidth,
          5 * ratio,
        )
      }
      drawLines(
        context,
        beats,
        from,
        row.end,
        label,
        y + 1,
        rowWidth,
        rowHeight - 2,
        'rgb(255 255 255 / 30%)',
      )
      drawLines(
        context,
        [row.start],
        from,
        row.end,
        label,
        y,
        rowWidth,
        rowHeight,
        'rgb(255 255 255 / 90%)',
        2,
      )
      context.fillStyle = 'rgb(200 200 210)'
      context.fillText(String(row.number), 2 * ratio, y + rowHeight / 2)
    })
  }, [picture, rows, beats, longest, span, width, height])

  const rowAt = (event: PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return rows[Math.floor((event.clientY - rect.top) / ROW_HEIGHT)]
  }
  const playing = rows.findIndex((row) => currentTime >= row.start && currentTime < row.end)
  // the bar being played stays in view of the scrolling box
  const scrollRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const box = scrollRef.current
    if (!box || playing < 0) return
    const top = playing * ROW_HEIGHT
    if (top < box.scrollTop || top + ROW_HEIGHT > box.scrollTop + box.clientHeight) {
      box.scrollTop = Math.max(0, top - box.clientHeight / 3)
    }
  }, [playing])

  if (rows.length === 0) return <p className={styles.note}>No bars here.</p>
  return (
    <div ref={scrollRef} className={styles.stackScroll}>
      <div className={styles.stack} style={{ height: rows.length * ROW_HEIGHT }}>
        <canvas
          ref={canvasRef}
          className={styles.canvas}
          onPointerDown={(event) => {
            const row = rowAt(event)
            if (row) onSeek(row.start)
          }}
          role="img"
          aria-label={`Bars ${rows[0].number} to ${rows.at(-1)?.number} as rows; click one to go to it`}
        />
        {playing >= 0 && (
          <span
            className={styles.stackPlayhead}
            style={{
              top: playing * ROW_HEIGHT,
              left: `calc(${LABEL_WIDTH}px + (100% - ${LABEL_WIDTH}px) * ${
                (currentTime - (rows[playing].start - longest * LEAD_IN)) / span
              })`,
            }}
            aria-hidden="true"
          />
        )}
      </div>
    </div>
  )
}

/** The beat network's bar-start likelihood as a yellow band (brighter = likelier). */
function drawNetworkBars(
  context: CanvasRenderingContext2D,
  picture: MusicPicture,
  start: number,
  end: number,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  const downbeat = picture.downbeat
  if (!downbeat) return
  const columns = Math.max(1, Math.floor(width))
  for (let column = 0; column < columns; column += 1) {
    const f0 = Math.floor((start + ((end - start) * column) / columns) * picture.beatFps)
    const f1 = Math.max(
      f0 + 1,
      Math.floor((start + ((end - start) * (column + 1)) / columns) * picture.beatFps),
    )
    let level = 0
    for (let f = Math.max(0, f0); f < Math.min(downbeat.length, f1); f += 1)
      level = Math.max(level, downbeat[f])
    if (level < 60) continue
    context.fillStyle = `rgb(255 200 0 / ${Math.round((level / 255) * 100)}%)`
    context.fillRect(x + (column * width) / columns, y, width / columns + 0.5, height)
  }
}

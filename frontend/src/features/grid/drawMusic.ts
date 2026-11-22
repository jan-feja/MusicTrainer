/**
 * Drawing the pictures of the music onto canvases (pure, given a 2D context).
 */
import { type MusicPicture, SPECTROGRAM_COLORS } from './musicVisual'

/** Draw the spectrogram of [start, end) into the rectangle (x, y, width, height), in pixels. */
export function drawSpectrogram(
  context: CanvasRenderingContext2D,
  picture: MusicPicture,
  start: number,
  end: number,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  const columns = Math.max(1, Math.floor(width))
  const { bands, fps, frames, spectrogram } = picture
  if (bands === 0 || frames === 0 || end <= start) return
  const image = context.createImageData(columns, bands)
  const pixels = image.data
  for (let column = 0; column < columns; column += 1) {
    const t0 = start + ((end - start) * column) / columns
    const t1 = start + ((end - start) * (column + 1)) / columns
    const f0 = Math.floor(t0 * fps)
    const f1 = Math.max(f0 + 1, Math.floor(t1 * fps))
    for (let band = 0; band < bands; band += 1) {
      let level = 0
      for (let frame = Math.max(0, f0); frame < Math.min(frames, f1); frame += 1) {
        const value = spectrogram[frame * bands + band]
        if (value > level) level = value
      }
      const row = bands - 1 - band // low frequencies at the bottom
      const p = (row * columns + column) * 4
      pixels[p] = SPECTROGRAM_COLORS[level * 3]
      pixels[p + 1] = SPECTROGRAM_COLORS[level * 3 + 1]
      pixels[p + 2] = SPECTROGRAM_COLORS[level * 3 + 2]
      pixels[p + 3] = f0 < frames && f1 > 0 ? 255 : 0
    }
  }
  const scratch = document.createElement('canvas')
  scratch.width = columns
  scratch.height = bands
  scratch.getContext('2d')?.putImageData(image, 0, 0)
  context.imageSmoothingEnabled = true
  context.drawImage(scratch, x, y, width, height)
}

/** Draw the section colors of [start, end) as a strip. */
export function drawColors(
  context: CanvasRenderingContext2D,
  picture: MusicPicture,
  start: number,
  end: number,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  const { colors, colorStep } = picture
  const steps = colors.length / 3
  if (steps === 0 || end <= start) return
  const columns = Math.max(1, Math.floor(width))
  for (let column = 0; column < columns; column += 1) {
    const t = start + ((end - start) * (column + 0.5)) / columns
    const step = Math.floor(t / colorStep)
    if (step < 0 || step >= steps) continue
    context.fillStyle = `rgb(${colors[step * 3]} ${colors[step * 3 + 1]} ${colors[step * 3 + 2]})`
    context.fillRect(x + (column * width) / columns, y, width / columns + 1, height)
  }
}

/** The mean section color over [start, end), as CSS, or null outside the song. */
export function meanColor(picture: MusicPicture, start: number, end: number): string | null {
  const { colors, colorStep } = picture
  const first = Math.max(0, Math.floor(start / colorStep))
  const last = Math.min(colors.length / 3, Math.ceil(end / colorStep))
  if (last <= first) return null
  let r = 0
  let g = 0
  let b = 0
  for (let step = first; step < last; step += 1) {
    r += colors[step * 3]
    g += colors[step * 3 + 1]
    b += colors[step * 3 + 2]
  }
  const n = last - first
  return `rgb(${Math.round(r / n)} ${Math.round(g / n)} ${Math.round(b / n)})`
}

/** Vertical lines at `times` in [start, end). */
export function drawLines(
  context: CanvasRenderingContext2D,
  times: readonly number[],
  start: number,
  end: number,
  x: number,
  y: number,
  width: number,
  height: number,
  style: string,
  lineWidth = 1,
): void {
  context.strokeStyle = style
  context.lineWidth = lineWidth
  context.beginPath()
  for (const time of times) {
    if (time < start || time >= end) continue
    const px = Math.round(x + ((time - start) / (end - start)) * width) + 0.5
    context.moveTo(px, y)
    context.lineTo(px, y + height)
  }
  context.stroke()
}

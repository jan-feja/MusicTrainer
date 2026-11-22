/** Which bars the "bars as rows" view shows. */

/** Most bars shown at once. */
export const MAX_ROWS = 48

export interface StackRow {
  /** Bar number, from 1. */
  number: number
  start: number
  end: number
}

/** The bars that start in [start, end), at most MAX_ROWS, around `focus` if there are more. */
export function stackRows(
  bars: readonly number[],
  start: number,
  end: number,
  focus: number,
  max: number = MAX_ROWS,
): StackRow[] {
  const rows: StackRow[] = []
  for (let i = 0; i + 1 < bars.length; i += 1) {
    if (bars[i] >= start - 1e-6 && bars[i] < end - 1e-6) {
      rows.push({ number: i + 1, start: bars[i], end: bars[i + 1] })
    }
  }
  if (rows.length <= max) return rows
  const at = rows.findIndex((row) => row.end > focus)
  const first = Math.min(Math.max(0, (at < 0 ? rows.length : at) - max / 2), rows.length - max)
  return rows.slice(first, first + max)
}

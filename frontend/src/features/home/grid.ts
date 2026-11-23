import { useCallback, useState } from 'react'

/**
 * How many columns a `repeat(auto-fill, minmax(minWidth, 1fr))` grid with this
 * gap has in the element given to `ref`; 0 until it is measured (before the
 * first paint), then kept up to date as the element resizes.
 */
export function useColumnCount(minWidth: number, gap: number) {
  const [columns, setColumns] = useState(0)
  const ref = useCallback(
    (element: HTMLElement | null) => {
      if (!element) return
      const update = () =>
        setColumns(Math.max(1, Math.floor((element.clientWidth + gap) / (minWidth + gap))))
      update()
      const observer = new ResizeObserver(update)
      observer.observe(element)
      return () => observer.disconnect()
    },
    [minWidth, gap],
  )
  return [ref, columns] as const
}

/** Rows of songs: two, more on a narrow screen (at least six songs). */
export function songRows(columns: number): number {
  return Math.max(2, Math.ceil(6 / columns))
}

/**
 * How many of `available` items to show in up to `rows` rows of `columns`:
 * only full rows, unless there is not even one.
 */
export function shownCount(available: number, columns: number, rows: number): number {
  if (available <= columns) return available
  return Math.min(Math.floor(available / columns), rows) * columns
}

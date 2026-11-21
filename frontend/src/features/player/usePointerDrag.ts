import { type PointerEvent, useMemo } from 'react'
import { useLatest } from '../../lib/useLatest'

/**
 * Pointer handlers for click-and-drag along the x axis (mouse, touch, pen).
 * Spread the result onto the element: `<div {...drag} />`.
 */
export function usePointerDrag(onDrag: (clientX: number) => void) {
  const onDragRef = useLatest(onDrag)
  return useMemo(
    () => ({
      onPointerDown(event: PointerEvent<HTMLElement>) {
        if (event.button !== 0) return
        event.preventDefault()
        event.stopPropagation() // a handle inside the seek bar must not also seek
        event.currentTarget.setPointerCapture(event.pointerId)
        onDragRef.current(event.clientX)
      },
      onPointerMove(event: PointerEvent<HTMLElement>) {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
          onDragRef.current(event.clientX)
        }
      },
      onPointerUp(event: PointerEvent<HTMLElement>) {
        event.currentTarget.releasePointerCapture(event.pointerId)
      },
    }),
    [onDragRef],
  )
}

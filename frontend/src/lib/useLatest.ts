import { type RefObject, useLayoutEffect, useRef } from 'react'

/**
 * A ref that always holds the latest `value`. Lets long-lived callbacks (event
 * listeners, animation frames) read current props without being re-created.
 */
export function useLatest<T>(value: T): RefObject<T> {
  const ref = useRef(value)
  useLayoutEffect(() => {
    ref.current = value
  })
  return ref
}

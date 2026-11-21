import { useEffect, useRef } from 'react'

/** Calls `callback` whenever `value` changes (not on the first render). */
export function useOnChange<T>(value: T, callback: () => void): void {
  const previous = useRef(value)
  useEffect(() => {
    if (!Object.is(previous.current, value)) {
      previous.current = value
      callback()
    }
  }, [value, callback])
}

import { type RefObject, useCallback, useEffect, useState } from 'react'

export function useFullscreen(elementRef: RefObject<HTMLElement | null>) {
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const update = () => setIsFullscreen(document.fullscreenElement === elementRef.current)
    document.addEventListener('fullscreenchange', update)
    return () => document.removeEventListener('fullscreenchange', update)
  }, [elementRef])

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
    } else {
      void elementRef.current?.requestFullscreen()
    }
  }, [elementRef])

  return { isFullscreen, toggleFullscreen }
}

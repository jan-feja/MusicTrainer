import { useEffect } from 'react'
import { useLatest } from '../../lib/useLatest'
import { type ShortcutId, findShortcut } from './shortcuts'

function isTextInput(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
  )
}

/** Runs the matching action when a player shortcut key is pressed; it gets the key. */
export function usePlayerShortcuts(actions: Record<ShortcutId, (key: string) => void>): void {
  const actionsRef = useLatest(actions)

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return
      if (isTextInput(event.target)) return
      const shortcut = findShortcut(event.key)
      if (!shortcut) return
      // also stops Space from scrolling the page or clicking the focused button
      event.preventDefault()
      actionsRef.current[shortcut](event.key)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [actionsRef])
}

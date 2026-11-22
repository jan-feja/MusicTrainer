/** Keyboard shortcuts of the player: one list drives both the key handling and the help. */

export const PLAYER_SHORTCUTS = [
  { id: 'togglePlay', keys: [' ', 'k'], label: 'Space / K', description: 'Play / pause' },
  { id: 'seekBackward', keys: ['ArrowLeft'], label: '←', description: 'Back 5 s' },
  { id: 'seekForward', keys: ['ArrowRight'], label: '→', description: 'Forward 5 s' },
  { id: 'slower', keys: ['-', '<'], label: '− / <', description: 'Slower (−0.05×)' },
  { id: 'faster', keys: ['+', '=', '>'], label: '+ / >', description: 'Faster (+0.05×)' },
  { id: 'setLoopStart', keys: ['a'], label: 'A', description: 'Set loop start here' },
  { id: 'setLoopEnd', keys: ['b'], label: 'B', description: 'Set loop end here' },
  { id: 'toggleLoop', keys: ['l'], label: 'L', description: 'Loop on / off' },
  { id: 'clearLoop', keys: ['c'], label: 'C', description: 'Clear loop' },
  { id: 'saveLoop', keys: ['s'], label: 'S', description: 'Save the loop with the video' },
  {
    id: 'selectSavedLoop',
    keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'],
    label: '1–9',
    description: 'Go to saved loop 1–9',
  },
  { id: 'toggleZoom', keys: ['z'], label: 'Z', description: 'Zoom to the loop / whole song' },
  { id: 'cycleSnapMode', keys: ['g'], label: 'G', description: 'Snap loop: off / beats / bars' },
  { id: 'jumpToLoopStart', keys: ['Home'], label: 'Home', description: 'Go to loop start' },
  { id: 'toggleMute', keys: ['m'], label: 'M', description: 'Mute / unmute' },
  { id: 'toggleFullscreen', keys: ['f'], label: 'F', description: 'Full screen' },
] as const

export type ShortcutId = (typeof PLAYER_SHORTCUTS)[number]['id']

/** The shortcut for a pressed key (letters ignore Shift / Caps Lock). */
export function findShortcut(key: string): ShortcutId | undefined {
  const normalized = key.length === 1 ? key.toLowerCase() : key
  return PLAYER_SHORTCUTS.find((shortcut) =>
    (shortcut.keys as readonly string[]).includes(normalized),
  )?.id
}

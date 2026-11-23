/** How chord labels from the server ('A:min', 'C:maj', 'N') are shown. */

const SHARP = '♯'

/** 'A:min' → 'Am', 'C:maj' → 'C', 'F#:maj' → 'F♯'; null for no chord. */
export function chordName(label: string): string | null {
  if (label === 'N') return null
  const [root, quality] = label.split(':')
  return `${root.replace('#', SHARP)}${quality === 'min' ? 'm' : ''}`
}

/** The chord at `time`, from chords in time order. */
export function chordAt<T extends { start: number; end: number }>(
  chords: readonly T[],
  time: number,
): T | null {
  let low = 0
  let high = chords.length
  while (low < high) {
    const middle = (low + high) >> 1
    if (chords[middle].end <= time) low = middle + 1
    else high = middle
  }
  const chord = chords[low]
  return chord && chord.start <= time ? chord : null
}

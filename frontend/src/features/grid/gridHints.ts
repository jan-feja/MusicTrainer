/**
 * Editing the user's hints for the beat grid: sections with their own bars and tapped bar
 * starts. Pure functions on BeatGridHints; the backend decodes the grid again with them.
 */
import type { BeatAnalysis, BeatGridHints, GridSection } from '../../api/types'
import { nearestIndex } from '../beats/beatGrid'

/** Two section starts or bar starts closer than this are the same one. */
export const SAME_TIME = 0.05
/** Longest bar pattern the backend takes, and the most beats in one of its bars. */
export const MAX_PATTERN_BARS = 16
export const MAX_PATTERN_BEATS = 16

/** A part of the song with its range; `section` null: before the first section (song settings). */
export interface SectionSpan {
  section: GridSection | null
  start: number
  end: number
}

/** The beat nearest to `time`: section starts and bar starts sit on beats. */
export function snapToBeat(beats: readonly number[], time: number): number {
  const i = nearestIndex(beats, time)
  return i < 0 ? time : beats[i]
}

function sameTime(a: number, b: number): boolean {
  return Math.abs(a - b) < SAME_TIME
}

function sorted(sections: GridSection[]): GridSection[] {
  return [...sections].sort((a, b) => a.start - b.start)
}

/** A section from the beat nearest `time`, with everything left to the detection. */
export function addSection(
  hints: BeatGridHints,
  time: number,
  beats: readonly number[],
): BeatGridHints {
  const start = Math.max(0, snapToBeat(beats, time))
  if (hints.sections.some((section) => sameTime(section.start, start))) return hints
  const section: GridSection = { start, beatsPerBar: null, pattern: [], tempoBpm: null }
  return { ...hints, sections: sorted([...hints.sections, section]) }
}

export function updateSection(
  hints: BeatGridHints,
  start: number,
  changes: Partial<GridSection>,
): BeatGridHints {
  return {
    ...hints,
    sections: sorted(
      hints.sections.map((section) =>
        sameTime(section.start, start) ? { ...section, ...changes } : section,
      ),
    ),
  }
}

export function removeSection(hints: BeatGridHints, start: number): BeatGridHints {
  return { ...hints, sections: hints.sections.filter((section) => !sameTime(section.start, start)) }
}

/**
 * Move a section's start to the beat nearest `time`, staying between its neighbours.
 * Unchanged if that would be on another section's start.
 */
export function moveSection(
  hints: BeatGridHints,
  start: number,
  time: number,
  beats: readonly number[],
): BeatGridHints {
  const target = Math.max(0, snapToBeat(beats, time))
  const others = hints.sections.filter((section) => !sameTime(section.start, start))
  if (others.some((section) => sameTime(section.start, target))) return hints
  const before = others.filter((section) => section.start < start).at(-1)
  const after = others.find((section) => section.start > start)
  if ((before && target <= before.start) || (after && target >= after.start)) return hints
  return updateSection(hints, start, { start: target })
}

/** One beat earlier (-1) or later (+1). */
export function shiftSection(
  hints: BeatGridHints,
  start: number,
  delta: -1 | 1,
  beats: readonly number[],
): BeatGridHints {
  const i = nearestIndex(beats, start)
  const target = beats[Math.min(Math.max(i + delta, 0), beats.length - 1)]
  return target === undefined ? hints : moveSection(hints, start, target, beats)
}

/** The parts of the song: before the first section (if it starts later), then every section. */
export function sectionSpans(hints: BeatGridHints, duration: number): SectionSpan[] {
  const sections = sorted(hints.sections)
  const spans: SectionSpan[] = []
  if (sections.length === 0 || sections[0].start > 0) {
    spans.push({ section: null, start: 0, end: sections[0]?.start ?? duration })
  }
  sections.forEach((section, i) => {
    spans.push({ section, start: section.start, end: sections[i + 1]?.start ?? duration })
  })
  return spans
}

/** The span that `time` is in. */
export function spanAt(spans: SectionSpan[], time: number): SectionSpan | null {
  return spans.find((span) => time >= span.start && time < span.end) ?? spans.at(-1) ?? null
}

/** A tapped bar start, on the beat nearest `time` (one there already: unchanged). */
export function addBarStart(
  hints: BeatGridHints,
  time: number,
  beats: readonly number[],
): BeatGridHints {
  const start = snapToBeat(beats, time)
  if (hints.barStarts.some((t) => sameTime(t, start))) return hints
  return { ...hints, barStarts: [...hints.barStarts, start].sort((a, b) => a - b) }
}

export function removeBarStart(hints: BeatGridHints, time: number): BeatGridHints {
  return { ...hints, barStarts: hints.barStarts.filter((t) => !sameTime(t, time)) }
}

/**
 * "6+6+5+6+5+5", "3 3 2" or "7": bar lengths in beats; null if it is not that. One number
 * means every bar has that many beats.
 */
export function parsePattern(text: string): number[] | null {
  const parts = text
    .trim()
    .split(/[\s+,/]+/)
    .filter(Boolean)
  if (parts.length === 0 || parts.length > MAX_PATTERN_BARS) return null
  const numbers = parts.map(Number)
  if (numbers.some((n) => !Number.isInteger(n) || n < 1 || n > MAX_PATTERN_BEATS)) return null
  return numbers
}

/** The section's bars as the user set them: "4", "6+6+5" — or null (left to the detection). */
export function describeBars(section: GridSection | null): string | null {
  if (!section) return null
  if (section.pattern.length > 0) return section.pattern.join('+')
  return section.beatsPerBar ? String(section.beatsPerBar) : null
}

/** Median tempo of the grid's beats in [start, end), or null with fewer than 3 beats. */
export function localBpm(analysis: BeatAnalysis, start: number, end: number): number | null {
  const beats = analysis.beats.filter((t) => t >= start && t < end)
  if (beats.length < 3) return null
  const gaps = beats
    .slice(1)
    .map((t, i) => t - beats[i])
    .sort((a, b) => a - b)
  return 60 / gaps[Math.floor(gaps.length / 2)]
}

/** Numbers of beats per bar in the grid between `start` and `end`, most bars first. */
export function barLengthsBetween(analysis: BeatAnalysis, start: number, end: number): number[] {
  const counts = new Map<number, number>()
  const { beats, downbeats } = analysis
  for (let i = 0; i + 1 < downbeats.length; i += 1) {
    if (downbeats[i] < start - SAME_TIME || downbeats[i] >= end - SAME_TIME) continue
    const length = nearestIndex(beats, downbeats[i + 1]) - nearestIndex(beats, downbeats[i])
    if (length > 0) counts.set(length, (counts.get(length) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]).map(([n]) => n)
}

function rounded(hints: BeatGridHints): string {
  const ms = (t: number) => Math.round(t * 1000)
  return JSON.stringify({
    ...hints,
    tempoBpm: hints.tempoBpm === null ? null : Math.round(hints.tempoBpm * 10),
    barStarts: hints.barStarts.map(ms),
    sections: sorted(hints.sections ?? []).map((section) => ({
      start: ms(section.start),
      beatsPerBar: section.beatsPerBar,
      pattern: section.pattern,
      tempoBpm: section.tempoBpm === null ? null : Math.round(section.tempoBpm * 10),
    })),
  })
}

/** The same hints (times to the millisecond; the backend sends back what it got). */
export function sameHints(a: BeatGridHints, b: BeatGridHints): boolean {
  return rounded(a) === rounded(b)
}

/** What a span's bars are: what the user set, else what the grid has there (in grey). */
export function spanLabel(
  span: SectionSpan,
  analysis: BeatAnalysis,
): { text: string; auto: boolean } {
  const set = describeBars(span.section)
  const tempo = span.section?.tempoBpm ? ` · ${Math.round(span.section.tempoBpm)} BPM` : ''
  if (set) return { text: `${set} beats${tempo}`, auto: false }
  const detected = barLengthsBetween(analysis, span.start, span.end).slice(0, 2).join(' / ')
  return { text: `${detected ? `${detected} beats` : '…'}${tempo}`, auto: true }
}

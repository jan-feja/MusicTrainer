import { type RefObject, useEffect, useImperativeHandle, useMemo, useState } from 'react'
import type { BeatAnalysis, GridSection } from '../../api/types'
import { formatTimePrecise } from '../../lib/format'
import { useLatest } from '../../lib/useLatest'
import type { BeatTracking } from '../beats/useBeatTracking'
import type { TimeView } from '../player/timelineView'
import { BarStack } from './BarStack'
import {
  type SectionSpan,
  addBarStart,
  addSection,
  barLengthsBetween,
  localBpm,
  parsePattern,
  removeBarStart,
  removeSection,
  sectionSpans,
  shiftSection,
  moveSection,
  spanAt,
  updateSection,
} from './gridHints'
import { MusicLane } from './MusicLane'
import { type PictureState } from './musicVisual'
import { SectionLane } from './SectionLane'
import { type HintEditor, useHintEditor } from './useHintEditor'
import styles from './GridEditor.module.css'

const BEATS_PER_BAR = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

/** What the player's keyboard shortcuts can do in the editor. */
export interface GridEditorActions {
  tap: () => void
  addSection: () => void
}

interface GridEditorProps {
  tracking: BeatTracking
  picture: PictureState
  view: TimeView
  duration: number
  currentTime: number
  getCurrentTime: () => number
  onSeek: (time: number) => void
  clickOn: boolean
  onToggleClick: () => void
  onClose: () => void
  actions: RefObject<GridEditorActions | null>
}

/**
 * The grid editor: the music in pictures under the timeline, the song's sections and the
 * bar starts the user tapped; for the selected section its beats per bar, bar pattern and
 * beat speed. Every change decodes the grid again (a few seconds), the clicks tell whether
 * it is right.
 */
export function GridEditor(props: GridEditorProps) {
  const { tracking, picture, view, duration, currentTime, onSeek } = props
  const analysis = tracking.analysis
  const editor = useHintEditor(tracking)
  const hints = editor.hints
  const spans = useMemo(() => (hints ? sectionSpans(hints, duration) : []), [hints, duration])
  // the selected section: the one picked, else the one playing (if in view; else the one in
  // the middle of the view: what the user looks at)
  const [picked, setPicked] = useState<number | null>(null)
  const pickedSpan = picked === null ? null : spans.find((s) => Math.abs(s.start - picked) < 1e-6)
  const playheadInView = currentTime >= view.start && currentTime <= view.end
  const focus = playheadInView ? currentTime : (view.start + view.end) / 2
  const selected = pickedSpan ?? spanAt(spans, focus)

  const beats = analysis?.beats ?? []
  const latest = useLatest({ hints, beats, editor, getCurrentTime: props.getCurrentTime })
  useImperativeHandle(props.actions, () => ({
    tap() {
      const { hints, beats, editor, getCurrentTime } = latest.current
      if (hints && beats.length > 0) editor.edit(addBarStart(hints, getCurrentTime(), beats))
    },
    addSection() {
      const { hints, beats, editor, getCurrentTime } = latest.current
      if (!hints || beats.length === 0) return
      const next = addSection(hints, getCurrentTime(), beats)
      editor.edit(next)
      const added = next.sections.find((s) => !hints.sections.includes(s))
      if (added) setPicked(added.start)
    },
  }))

  // Ctrl / Cmd + Z: undo the last change
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !event.shiftKey) {
        event.preventDefault()
        latest.current.editor.undo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [latest])

  if (!analysis || !hints) return null
  const ready = picture.status === 'ready' ? picture.picture : null

  return (
    <section className={styles.editor} aria-label="Grid editor">
      <div className={styles.toolbar}>
        <span className={styles.title}>Beats &amp; bars</span>
        <button
          type="button"
          className={styles.tool}
          aria-pressed={props.clickOn}
          onClick={props.onToggleClick}
          title="A click on every beat, higher on bar starts (Q)"
        >
          Click
        </button>
        <button
          type="button"
          className={styles.tool}
          onClick={() => props.actions.current?.addSection()}
          title="The bars change here: start a section at the playhead (N)"
        >
          + Section here
        </button>
        <button
          type="button"
          className={styles.tool}
          onClick={() => props.actions.current?.tap()}
          title="While it plays, press T on the first beat of a bar: a bar starts there (T)"
        >
          Tap bar start (T)
        </button>
        <button
          type="button"
          className={styles.tool}
          onClick={editor.undo}
          disabled={!editor.canUndo}
          title="Undo the last change (Ctrl+Z)"
        >
          Undo
        </button>
        {(editor.pending || tracking.updating) && (
          <span className={styles.status} role="status">
            Updating the grid…
          </span>
        )}
        <span className={styles.spacer} />
        <button type="button" className={styles.tool} onClick={props.onClose} title="Close (E)">
          Done
        </button>
      </div>
      <p className={styles.help}>
        Play with <strong>Click</strong> on. Where the high click stops falling on the first beat of
        the bar, start a section there and set its bars, or tap the bar starts (T). Similar music
        has a similar color.
      </p>
      <SectionLane
        spans={spans}
        view={view}
        selected={selected?.start ?? null}
        analysis={analysis}
        picture={ready}
        barStarts={hints.barStarts}
        onSelect={(span) => setPicked(span.start)}
        onMoveSection={(start, time) => {
          editor.edit(moveSection(hints, start, time, beats))
          setPicked(null)
        }}
        onRemoveBarStart={(time) => editor.edit(removeBarStart(hints, time))}
      />
      {ready ? (
        <MusicLane
          picture={ready}
          view={view}
          beats={beats}
          bars={analysis.downbeats}
          currentTime={currentTime}
          onSeek={onSeek}
        />
      ) : (
        <p className={styles.musicPlaceholder}>
          {picture.status === 'failed'
            ? `No picture of the music: ${picture.error}`
            : 'Drawing the music…'}
        </p>
      )}
      {selected && (
        <SectionSettings
          key={selected.start}
          span={selected}
          analysis={analysis}
          editor={editor}
          index={spans.indexOf(selected)}
          onPick={setPicked}
        />
      )}
      {ready && selected && (
        <details className={styles.stackPanel} open>
          <summary>Bars as rows</summary>
          <p className={styles.help}>
            Each row is one bar. When the bars are right, the rows look alike and the yellow marks
            (where the beat detection hears a bar start) are at their left edge.
          </p>
          <BarStack
            picture={ready}
            beats={beats}
            bars={analysis.downbeats}
            start={selected.start}
            end={selected.end}
            currentTime={currentTime}
            focus={focus}
            onSeek={onSeek}
          />
        </details>
      )}
    </section>
  )
}

/** Beats per bar, bar pattern and beat speed of one section. */
function SectionSettings({
  span,
  analysis,
  editor,
  index,
  onPick,
}: {
  span: SectionSpan
  analysis: BeatAnalysis
  editor: HintEditor
  index: number
  onPick: (start: number | null) => void
}) {
  const hints = editor.hints
  const section = span.section
  const beats = analysis.beats
  const detected = barLengthsBetween(analysis, span.start, span.end)
  const bpm = localBpm(analysis, span.start, span.end)
  const [patternText, setPatternText] = useState(section?.pattern.join('+') ?? '')
  const [patternOpen, setPatternOpen] = useState((section?.pattern.length ?? 0) > 0)
  const patternValue = parsePattern(patternText)
  if (!hints) return null

  const change = (changes: Partial<GridSection>) => {
    if (section) editor.edit(updateSection(hints, section.start, changes))
  }
  /** Move the section start a beat, and keep it selected. */
  const shift = (delta: -1 | 1) => {
    if (!section) return
    const next = shiftSection(hints, section.start, delta, beats)
    editor.edit(next)
    const moved = next.sections.find((s) => !hints.sections.some((old) => old.start === s.start))
    if (moved) onPick(moved.start)
  }
  const makeSection = () => {
    const next = addSection(hints, span.start, beats)
    editor.edit(next)
    onPick(span.start)
  }
  const meterValue = section?.pattern.length ? 'pattern' : String(section?.beatsPerBar ?? 'auto')

  return (
    <div className={styles.settings} role="group" aria-label="Section settings">
      <span className={styles.settingsTitle}>
        {section ? `Section ${index + 1}` : 'Song start'}
        <span className={styles.muted}> from {formatTimePrecise(span.start)}</span>
      </span>
      {!section ? (
        <>
          <span className={styles.muted}>
            {detected.length ? `${detected.join(' / ')} beats per bar` : ''} · uses the song’s
            settings
          </span>
          <button type="button" className={styles.tool} onClick={makeSection}>
            Make it a section
          </button>
        </>
      ) : (
        <>
          <label className={styles.field}>
            <span className={styles.muted}>Beats per bar</span>
            <select
              className={styles.select}
              value={patternOpen ? 'pattern' : meterValue}
              onChange={(event) => {
                const value = event.target.value
                if (value === 'pattern') {
                  setPatternOpen(true)
                  return
                }
                setPatternOpen(false)
                change({ beatsPerBar: value === 'auto' ? null : Number(value), pattern: [] })
              }}
            >
              <option value="auto">
                Auto{detected.length ? ` (${detected.join(' / ')})` : ''}
              </option>
              {BEATS_PER_BAR.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
              <option value="pattern">Pattern…</option>
            </select>
          </label>
          {patternOpen && (
            <form
              className={styles.field}
              onSubmit={(event) => {
                event.preventDefault()
                if (!patternValue) return
                if (patternValue.length === 1) {
                  change({ beatsPerBar: patternValue[0], pattern: [] })
                  setPatternOpen(false)
                } else {
                  change({ beatsPerBar: null, pattern: patternValue })
                }
              }}
            >
              <input
                className={styles.input}
                value={patternText}
                onChange={(event) => setPatternText(event.target.value)}
                placeholder="e.g. 6+6+5+6+5+5"
                aria-label="Bar pattern: beats of each bar, repeated"
                aria-invalid={patternText !== '' && !patternValue}
                title="Beats of each bar, repeated from the section start, e.g. 6+6+5+6+5+5"
                size={14}
              />
              <button type="submit" className={styles.tool} disabled={!patternValue}>
                Set
              </button>
            </form>
          )}
          <span className={styles.field} role="group" aria-label="Beat speed">
            <span className={styles.muted}>Beats</span>
            {section.tempoBpm === null ? (
              <>
                <button
                  type="button"
                  className={styles.tool}
                  disabled={!bpm}
                  onClick={() => bpm && change({ tempoBpm: Math.round(bpm / 2) })}
                  title="Count beats half as fast in this section"
                >
                  ½×
                </button>
                <button
                  type="button"
                  className={styles.tool}
                  disabled={!bpm}
                  onClick={() => bpm && change({ tempoBpm: Math.round(bpm * 2) })}
                  title="Count beats twice as fast in this section (e.g. eighth notes for 5/8 bars)"
                >
                  2×
                </button>
              </>
            ) : (
              <button
                type="button"
                className={styles.tool}
                onClick={() => change({ tempoBpm: null })}
                title="Detect the beat speed again"
              >
                {Math.round(section.tempoBpm)} BPM ↺
              </button>
            )}
          </span>
          <span className={styles.field} role="group" aria-label="Section start">
            <button
              type="button"
              className="icon-button icon-button-small"
              onClick={() => shift(-1)}
              aria-label="Start the section one beat earlier"
              title="Start the section one beat earlier"
            >
              ‹
            </button>
            <span className={styles.muted}>start</span>
            <button
              type="button"
              className="icon-button icon-button-small"
              onClick={() => shift(1)}
              aria-label="Start the section one beat later"
              title="Start the section one beat later"
            >
              ›
            </button>
          </span>
          <button
            type="button"
            className={styles.tool}
            onClick={() => {
              editor.edit(removeSection(hints, section.start))
              onPick(null)
            }}
          >
            Remove section
          </button>
        </>
      )}
    </div>
  )
}

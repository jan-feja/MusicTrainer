import { type KeyboardEvent, useState } from 'react'
import type { SavedLoop } from '../../api/types'
import { DeleteIcon } from '../../components/icons'
import { MAX_LOOP_NAME_LENGTH, cleanLoopName } from './loopList'
import styles from './SavedLoops.module.css'

/** Loops 1–9 can be picked with the number keys. */
const NUMBER_KEYS = 9

interface SavedLoopsProps {
  /** In playing order. */
  loops: readonly SavedLoop[]
  activeId: string | null
  /** A complete loop is set that is not saved yet. */
  canSave: boolean
  /** e.g. "1:00.6 · 2 bars · 0.75×" */
  describe: (loop: SavedLoop) => string
  onSelect: (id: string) => void
  onSave: () => void
  /** Leave the saved loop as it is and start a new one. */
  onNew: () => void
  onRename: (id: string, name: string) => void
  onDelete: (id: string) => void
  /** Saving to the library failed with this message. */
  saveError?: string | null
}

/** The loops saved with the video: pick one to play it, save the current one, rename, delete. */
export function SavedLoops({
  loops,
  activeId,
  canSave,
  describe,
  onSelect,
  onSave,
  onNew,
  onRename,
  onDelete,
  saveError,
}: SavedLoopsProps) {
  const [renaming, setRenaming] = useState<string | null>(null)

  return (
    <div className={styles.group} role="group" aria-label="Saved loops">
      <span className={styles.label}>Saved loops</span>
      {loops.length === 0 && !canSave && (
        <span className={styles.hint}>
          Set A and B, then save the loop to keep it with the video.
        </span>
      )}
      {loops.map((loop, index) => {
        const active = loop.id === activeId
        if (renaming === loop.id) {
          return (
            <RenameField
              key={loop.id}
              name={loop.name}
              onDone={(name) => {
                setRenaming(null)
                if (name !== null) onRename(loop.id, name)
              }}
            />
          )
        }
        const shortcut = index < NUMBER_KEYS ? ` (${index + 1})` : ''
        return (
          <span key={loop.id} className={styles.item} data-active={active}>
            <button
              type="button"
              className={styles.chip}
              aria-pressed={active}
              onClick={() => onSelect(loop.id)}
              onDoubleClick={() => setRenaming(loop.id)}
              title={`Go to “${loop.name}”${shortcut}. Double-click to rename.`}
            >
              <span className={styles.name}>{loop.name}</span>
              <span className={styles.meta}>{describe(loop)}</span>
            </button>
            {active && (
              <>
                <button
                  type="button"
                  className="icon-button icon-button-small"
                  onClick={() => setRenaming(loop.id)}
                  aria-label={`Rename ${loop.name}`}
                  title="Rename"
                >
                  ✎
                </button>
                <button
                  type="button"
                  className="icon-button icon-button-small"
                  onClick={() => onDelete(loop.id)}
                  aria-label={`Delete ${loop.name}`}
                  title="Delete this saved loop"
                >
                  <DeleteIcon />
                </button>
              </>
            )}
          </span>
        )
      })}
      {canSave && (
        <button
          type="button"
          className="button button-small"
          onClick={onSave}
          title="Keep this loop with the video, with its snap and speed (S)"
        >
          + Save loop
        </button>
      )}
      {activeId !== null && (
        <button
          type="button"
          className="button button-small button-ghost"
          onClick={onNew}
          title="Start a new loop; the saved one stays as it is"
        >
          New loop
        </button>
      )}
      {saveError && (
        <span className={styles.error} role="alert">
          Not saved: {saveError}
        </span>
      )}
    </div>
  )
}

function RenameField({ name, onDone }: { name: string; onDone: (name: string | null) => void }) {
  const [value, setValue] = useState(name)
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') onDone(cleanLoopName(value))
    if (event.key === 'Escape') onDone(null)
  }
  return (
    <input
      className={styles.rename}
      value={value}
      maxLength={MAX_LOOP_NAME_LENGTH}
      aria-label="Loop name"
      autoFocus
      onFocus={(event) => event.currentTarget.select()}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={() => onDone(cleanLoopName(value))}
    />
  )
}

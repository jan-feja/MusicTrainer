import { type FormEvent, type KeyboardEvent, type ReactNode, useState } from 'react'
import type { Preset } from '../../api/types'
import {
  AddIcon,
  DeleteIcon,
  EditIcon,
  LoopIcon,
  MetronomeIcon,
  MixIcon,
  SpeedIcon,
} from '../../components/icons'
import { MAX_PRESET_NAME_LENGTH, type PresetTag, cleanPresetName } from './presets'
import styles from './PresetsPanel.module.css'

/** Presets 1–9 can be picked with the number keys. */
const NUMBER_KEYS = 9

const TAG_ICONS: Record<PresetTag['kind'], ReactNode> = {
  loop: <LoopIcon />,
  speed: <SpeedIcon />,
  mix: <MixIcon />,
  metronome: <MetronomeIcon />,
}

interface PresetsPanelProps {
  /** In the order the number keys pick them. */
  presets: readonly Preset[]
  activeId: string | null
  /** The player was changed since the active preset was chosen. */
  modified: boolean
  tags: (preset: Preset) => PresetTag[]
  /** What saving now would keep: the next free name, and its tags. */
  draft: { name: string; tags: PresetTag[] }
  /** The player is as the song first opens (and no preset is chosen). */
  defaultActive: boolean
  onSelectDefault: () => void
  onSelect: (id: string) => void
  onSave: (name: string) => void
  /** Store the player as it is now in the active preset. */
  onUpdate: () => void
  onRename: (id: string, name: string) => void
  onDelete: (id: string) => void
  /** Saving to the library failed with this message. */
  saveError?: string | null
  /** Shown below the user's presets (other people's presets). */
  children?: ReactNode
}

/** The song's presets as cards: pick one to set the player that way, save, update, rename. */
export function PresetsPanel({
  presets,
  activeId,
  modified,
  tags,
  draft,
  defaultActive,
  onSelectDefault,
  onSelect,
  onSave,
  onUpdate,
  onRename,
  onDelete,
  saveError,
  children,
}: PresetsPanelProps) {
  const [saving, setSaving] = useState(false)
  const [renaming, setRenaming] = useState<string | null>(null)
  const active = presets.find((preset) => preset.id === activeId) ?? null

  return (
    <section className={styles.panel} aria-labelledby="presets-title">
      <header className={styles.header}>
        <h2 id="presets-title" className={styles.title}>
          Presets
        </h2>
        {!saving && (
          <div className={styles.actions}>
            <button
              type="button"
              className="button button-small button-ghost"
              onClick={onSelectDefault}
              disabled={defaultActive}
              title="Back to how the song first opens: whole song, normal speed, stems and metronome off (0)"
            >
              Default
            </button>
            {active && modified && (
              <button
                type="button"
                className="button button-small button-primary"
                onClick={onUpdate}
                title={`Keep the player as it is now in “${active.name}”`}
              >
                Update preset
              </button>
            )}
            {(!active || modified) && (
              <button
                type="button"
                className={`button button-small ${active ? 'button-ghost' : 'button-primary'}`}
                onClick={() => setSaving(true)}
                title="Save the player as it is now as a new preset"
              >
                <AddIcon /> {active ? 'Save as new' : 'Save preset'}
              </button>
            )}
          </div>
        )}
      </header>

      {saving && (
        <SaveForm
          draft={draft}
          onSave={(name) => {
            setSaving(false)
            onSave(name)
          }}
          onCancel={() => setSaving(false)}
        />
      )}

      {presets.length === 0 && !saving && <p className={styles.empty}>No presets yet</p>}
      <ul className={styles.list}>
        {presets.map((preset, index) => (
          <PresetCard
            key={preset.id}
            name={preset.name}
            number={index < NUMBER_KEYS ? index + 1 : null}
            active={preset.id === activeId}
            modified={preset.id === activeId && modified}
            tags={tags(preset)}
            title={`Set the player as “${preset.name}”${index < NUMBER_KEYS ? ` (${index + 1})` : ''}. Double-click to rename.`}
            renaming={renaming === preset.id}
            onSelect={() => onSelect(preset.id)}
            onStartRename={() => setRenaming(preset.id)}
            onRename={(name) => {
              setRenaming(null)
              if (name !== null) onRename(preset.id, name)
            }}
            onDelete={() => onDelete(preset.id)}
          />
        ))}
      </ul>

      {children}

      {saveError && (
        <p className={styles.error} role="alert">
          Not saved: {saveError}
        </p>
      )}
    </section>
  )
}

interface PresetCardProps {
  name: string
  /** Its number key, if it has one. */
  number: number | null
  active: boolean
  modified: boolean
  tags: PresetTag[]
  title: string
  onSelect: () => void
  /** Without these the card cannot be renamed or deleted. */
  renaming?: boolean
  onStartRename?: () => void
  onRename?: (name: string | null) => void
  onDelete?: () => void
}

function PresetCard({
  name,
  number,
  active,
  modified,
  tags,
  title,
  onSelect,
  renaming = false,
  onStartRename,
  onRename,
  onDelete,
}: PresetCardProps) {
  const editable = onRename !== undefined
  const top = (
    <span className={styles.cardTop} data-editable={editable}>
      {number !== null && <kbd className={styles.key}>{number}</kbd>}
      {renaming && onRename ? (
        <NameField name={name} label="Preset name" onDone={onRename} />
      ) : (
        <span className={styles.name}>{name}</span>
      )}
      {active && (
        <span className={styles.badge} data-modified={modified}>
          {modified ? 'Changed' : 'On'}
        </span>
      )}
    </span>
  )
  const tagList = <TagList tags={tags} />
  return (
    <li className={styles.card} data-active={active}>
      {renaming ? (
        <div className={styles.cardMain}>
          {top}
          {tagList}
        </div>
      ) : (
        <button
          type="button"
          className={styles.cardMain}
          aria-pressed={active}
          onClick={onSelect}
          onDoubleClick={onStartRename}
          title={title}
        >
          {top}
          {tagList}
        </button>
      )}
      {editable && !renaming && (
        <span className={styles.cardActions}>
          <button
            type="button"
            className="icon-button icon-button-small"
            onClick={onStartRename}
            aria-label={`Rename ${name}`}
            title="Rename"
          >
            <EditIcon />
          </button>
          <button
            type="button"
            className="icon-button icon-button-small"
            onClick={onDelete}
            aria-label={`Delete ${name}`}
            title="Delete this preset"
          >
            <DeleteIcon />
          </button>
        </span>
      )}
    </li>
  )
}

export function TagList({ tags }: { tags: PresetTag[] }) {
  return (
    <span className={styles.tags}>
      {tags.map((tag) => (
        <span key={tag.kind} className={styles.tag} data-kind={tag.kind}>
          {TAG_ICONS[tag.kind]}
          {tag.label}
        </span>
      ))}
    </span>
  )
}

function SaveForm({
  draft,
  onSave,
  onCancel,
}: {
  draft: { name: string; tags: PresetTag[] }
  onSave: (name: string) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(draft.name)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSave(cleanPresetName(name) ?? draft.name)
  }
  return (
    <form className={styles.saveForm} onSubmit={submit} aria-label="Save preset">
      <div className={styles.saveRow}>
        <input
          className={styles.input}
          value={name}
          maxLength={MAX_PRESET_NAME_LENGTH}
          aria-label="Preset name"
          placeholder={draft.name}
          autoFocus
          onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => setName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') onCancel()
          }}
        />
        <button type="submit" className="button button-small button-primary">
          Save
        </button>
        <button type="button" className="button button-small button-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
      <div className={styles.saveSummary}>
        <span className={styles.saveSummaryLabel}>Keeps</span>
        <TagList tags={draft.tags} />
      </div>
    </form>
  )
}

function NameField({
  name,
  label,
  onDone,
}: {
  name: string
  label: string
  onDone: (name: string | null) => void
}) {
  const [value, setValue] = useState(name)
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') onDone(cleanPresetName(value))
    if (event.key === 'Escape') onDone(null)
  }
  return (
    <input
      className={`${styles.input} ${styles.renameInput}`}
      value={value}
      maxLength={MAX_PRESET_NAME_LENGTH}
      aria-label={label}
      autoFocus
      onFocus={(event) => event.currentTarget.select()}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={() => onDone(cleanPresetName(value))}
    />
  )
}

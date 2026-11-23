import { useState } from 'react'
import { Link } from 'react-router'
import type { FollowedPresets, Preset } from '../../api/types'
import { paths } from '../../app/paths'
import { AddIcon } from '../../components/icons'
import { UserAvatar } from '../profile/UserAvatar'
import type { PresetTag } from './presets'
import { TagList } from './PresetsPanel'
import styles from './FollowedPresetsList.module.css'

/** Chips shown before "+N more": about one row. */
const COLLAPSED_COUNT = 6

interface FollowedPresetsListProps {
  followed: readonly FollowedPresets[]
  /** The preset being tried (while the player is still set that way). */
  tried: { owner: string; id: string } | null
  tags: (preset: Preset) => PresetTag[]
  onTry: (owner: string, preset: Preset) => void
  onCopy: (preset: Preset) => void
}

/**
 * The presets of the people the user follows, as small chips: one row, the
 * rest behind "+N more". Picking one tries it; it can be added to the user's own.
 */
export function FollowedPresetsList({
  followed,
  tried,
  tags,
  onTry,
  onCopy,
}: FollowedPresetsListProps) {
  const [expanded, setExpanded] = useState(false)
  const all = followed.flatMap(({ username, presets }) =>
    presets.map((preset) => ({ owner: username, preset })),
  )
  const shown = expanded ? all : all.slice(0, COLLAPSED_COUNT)
  const hidden = all.length - shown.length
  const current = all.find(({ owner, preset }) => owner === tried?.owner && preset.id === tried.id)

  return (
    <section className={styles.followed} aria-labelledby="followed-presets-title">
      <h3 id="followed-presets-title" className={styles.title}>
        From people you follow <span className={styles.count}>{all.length}</span>
      </h3>
      <ul className={styles.chips}>
        {shown.map(({ owner, preset }) => {
          const on = current?.owner === owner && current.preset.id === preset.id
          return (
            <li key={`${owner}:${preset.id}`}>
              <button
                type="button"
                className={styles.chip}
                aria-pressed={on}
                onClick={() => onTry(owner, preset)}
                title={`Try ${owner}’s “${preset.name}”: ${tags(preset)
                  .map((tag) => tag.label)
                  .join(', ')}`}
              >
                <UserAvatar username={owner} size={18} />
                <span className={styles.chipName}>{preset.name}</span>
              </button>
            </li>
          )
        })}
        {(hidden > 0 || expanded) && all.length > COLLAPSED_COUNT && (
          <li>
            <button
              type="button"
              className={styles.more}
              onClick={() => setExpanded((value) => !value)}
              aria-expanded={expanded}
            >
              {expanded ? 'Show less' : `+${hidden} more`}
            </button>
          </li>
        )}
      </ul>

      {current && (
        <div className={styles.detail}>
          <span className={styles.detailText}>
            <Link to={paths.profile(current.owner)} className={styles.owner}>
              {current.owner}
            </Link>
            ’s <strong>{current.preset.name}</strong>
          </span>
          <TagList tags={tags(current.preset)} />
          <button
            type="button"
            className={`button button-small button-primary ${styles.copy}`}
            onClick={() => onCopy(current.preset)}
            title="Add a copy to your presets (yours to change)"
          >
            <AddIcon /> Add to my presets
          </button>
        </div>
      )}
    </section>
  )
}

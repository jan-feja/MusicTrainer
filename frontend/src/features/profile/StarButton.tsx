import { useState } from 'react'
import { api } from '../../api/client'
import { StarIcon, StarOutlineIcon } from '../../components/icons'
import { errorMessage } from '../../lib/format'
import styles from './StarButton.module.css'

interface StarButtonProps {
  videoId: string
  title: string
  starred: boolean
  /** With the word next to the star ("Star" / "Starred"). */
  labelled?: boolean
}

/** Stars a song of the user's library: starred songs show on the profile. */
export function StarButton({
  videoId,
  title,
  starred: initial,
  labelled = false,
}: StarButtonProps) {
  const [starred, setStarred] = useState(initial)
  const [busy, setBusy] = useState(false)

  const toggle = () => {
    const next = !starred
    setStarred(next) // at once; back if saving fails
    setBusy(true)
    api.setStarred(videoId, next).then(
      () => setBusy(false),
      (error: unknown) => {
        setStarred(!next)
        setBusy(false)
        window.alert(`Could not ${next ? 'star' : 'unstar'} the song: ${errorMessage(error)}`)
      },
    )
  }

  const label = starred ? `Unstar ${title}` : `Star ${title}`
  return (
    <button
      type="button"
      className={labelled ? `button button-small button-ghost ${styles.labelled}` : 'icon-button'}
      data-starred={starred}
      aria-pressed={labelled ? undefined : starred}
      aria-label={labelled ? undefined : label}
      title={
        starred
          ? 'Starred: shown on your profile. Click to unstar.'
          : 'Star: show it on your profile'
      }
      onClick={toggle}
      disabled={busy}
    >
      <span className={styles.icon} data-starred={starred}>
        {starred ? <StarIcon /> : <StarOutlineIcon />}
      </span>
      {labelled && (starred ? 'Starred' : 'Star')}
    </button>
  )
}

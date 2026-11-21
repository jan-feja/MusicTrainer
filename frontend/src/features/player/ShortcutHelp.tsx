import { PLAYER_SHORTCUTS } from './shortcuts'
import styles from './ShortcutHelp.module.css'

export function ShortcutHelp() {
  return (
    <details className={styles.help}>
      <summary>Keyboard shortcuts</summary>
      <dl className={styles.list}>
        {PLAYER_SHORTCUTS.map((shortcut) => (
          <div key={shortcut.id} className={styles.item}>
            <dt>
              <kbd>{shortcut.label}</kbd>
            </dt>
            <dd>{shortcut.description}</dd>
          </div>
        ))}
      </dl>
    </details>
  )
}

import { Children, type ReactNode } from 'react'
import styles from './VideoGrid.module.css'

/** Responsive grid of video cards. */
export function VideoGrid({ children }: { children: ReactNode }) {
  return (
    <ul className={styles.grid}>
      {Children.map(children, (child) => (
        <li>{child}</li>
      ))}
    </ul>
  )
}

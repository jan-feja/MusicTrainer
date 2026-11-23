import styles from './Profile.module.css'

/** A round badge with the username's first letter, in a colour that stays the same per user. */
export function UserAvatar({ username, size = 40 }: { username: string; size?: number }) {
  let hash = 0
  for (const char of username.toLowerCase()) hash = (hash * 31 + char.charCodeAt(0)) % 360
  return (
    <span
      className={styles.avatar}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.45,
        background: `hsl(${hash} 55% 45%)`,
      }}
      aria-hidden="true"
    >
      {username.charAt(0).toUpperCase()}
    </span>
  )
}

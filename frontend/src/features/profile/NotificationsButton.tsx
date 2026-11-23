import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api/client'
import type { FollowState, Notification, Notifications } from '../../api/types'
import { paths } from '../../app/paths'
import { BellIcon } from '../../components/icons'
import { errorMessage, formatTimeAgo } from '../../lib/format'
import { UserAvatar } from './UserAvatar'
import styles from './NotificationsButton.module.css'

/** How often the unread count is checked while the page is open. */
const POLL_MS = 60_000

/** The bell in the header: the unread count, and a panel with the notifications. */
export function NotificationsButton() {
  const [data, setData] = useState<Notifications | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const load = useCallback(async () => {
    try {
      const loaded = await api.getNotifications()
      setData(loaded)
      setError(null)
      return loaded
    } catch (reason) {
      setError(errorMessage(reason))
      return null
    }
  }, [])

  // the count stays fresh: now and then, and when the user comes back to the tab
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === 'visible') void load()
    }
    refresh()
    const timer = window.setInterval(refresh, POLL_MS)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [load])

  // a click outside or Escape closes the panel
  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const toggle = () => {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    // opening shows what is new (still marked) and clears the count
    void load().then((loaded) => {
      if (loaded && loaded.unread > 0) {
        api.markNotificationsSeen().then(
          () => setData((current) => current && { ...current, unread: 0 }),
          () => {},
        )
      }
    })
  }

  const unread = data?.unread ?? 0
  return (
    <div className={styles.root} ref={rootRef}>
      <button
        type="button"
        className={`icon-button ${styles.bell}`}
        onClick={toggle}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={unread > 0 ? `Notifications, ${unread} new` : 'Notifications'}
        title="Notifications"
      >
        <BellIcon />
        {unread > 0 && <span className={styles.badge}>{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <div className={styles.panel} role="dialog" aria-label="Notifications">
          <h2 className={styles.title}>Notifications</h2>
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          {data && data.items.length === 0 && (
            <p className={styles.empty}>
              Nothing yet. When someone follows you or asks to, it shows up here.
            </p>
          )}
          {data && data.items.length > 0 && (
            <ul className={styles.list}>
              {data.items.map((notification) => (
                <NotificationItem
                  key={`${notification.kind}:${notification.username}`}
                  notification={notification}
                  onChange={() => void load()}
                  onOpenProfile={() => setOpen(false)}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

function NotificationItem({
  notification,
  onChange,
  onOpenProfile,
}: {
  notification: Notification
  /** Something was answered: load the notifications again. */
  onChange: () => void
  onOpenProfile: () => void
}) {
  const { kind, username } = notification
  const [busy, setBusy] = useState(false)
  const [followState, setFollowState] = useState<FollowState>(notification.followState)

  const run = (action: () => Promise<unknown>, after?: (result: unknown) => void) => {
    setBusy(true)
    action().then(
      (result) => {
        setBusy(false)
        after?.(result)
      },
      (reason: unknown) => {
        setBusy(false)
        window.alert(errorMessage(reason))
      },
    )
  }

  const who = (
    <Link to={paths.profile(username)} className={styles.user} onClick={onOpenProfile}>
      {username}
    </Link>
  )
  const text = {
    follow_request: <>{who} asks to follow you</>,
    new_follower: <>{who} started following you</>,
    request_accepted: <>{who} accepted your follow request</>,
  }[kind]

  return (
    <li className={styles.item} data-unread={notification.unread}>
      <Link to={paths.profile(username)} onClick={onOpenProfile} tabIndex={-1} aria-hidden="true">
        <UserAvatar username={username} size={36} />
      </Link>
      <div className={styles.body}>
        <p className={styles.text}>
          {text}
          <span className={styles.time}> · {formatTimeAgo(notification.at)}</span>
        </p>
        {kind === 'follow_request' && (
          <div className={styles.actions}>
            <button
              type="button"
              className="button button-small button-primary"
              disabled={busy}
              onClick={() => run(() => api.acceptFollower(username), onChange)}
            >
              Accept
            </button>
            <button
              type="button"
              className="button button-small button-ghost"
              disabled={busy}
              onClick={() => run(() => api.removeFollower(username), onChange)}
            >
              Decline
            </button>
          </div>
        )}
        {kind === 'new_follower' && followState === 'none' && (
          <div className={styles.actions}>
            <button
              type="button"
              className="button button-small button-ghost"
              disabled={busy}
              onClick={() =>
                run(
                  () => api.follow(username),
                  (state) => setFollowState(state as FollowState),
                )
              }
            >
              Follow back
            </button>
          </div>
        )}
        {kind === 'new_follower' && followState === 'requested' && (
          <p className={styles.time}>Follow request sent</p>
        )}
      </div>
    </li>
  )
}

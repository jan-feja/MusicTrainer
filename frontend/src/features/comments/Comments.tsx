import { type FormEvent, type KeyboardEvent, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api/client'
import type { Comment } from '../../api/types'
import { paths } from '../../app/paths'
import { StatusMessage } from '../../components/StatusMessage'
import { DeleteIcon } from '../../components/icons'
import { errorMessage, formatTimeAgo } from '../../lib/format'
import { useAuth } from '../auth/authContext'
import { UserAvatar } from '../profile/UserAvatar'
import styles from './Comments.module.css'

const MAX_COMMENT_LENGTH = 250
/** The API's page size: a full page means there may be more. */
const PAGE_SIZE = 30

interface Loaded {
  items: Comment[]
  hasMore: boolean
}

/** Comments under a song: everyone reads them, an account writes them. Newest first. */
export function Comments({ videoId }: { videoId: string }) {
  const { user } = useAuth()
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  // the page being loaded: the first one (undefined) or after the comment with that time
  const [request, setRequest] = useState<{ before?: string; attempt: number } | null>({
    attempt: 0,
  })
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    if (request === null) return
    const controller = new AbortController()
    api.listComments(videoId, request.before, controller.signal).then(
      (page) => {
        if (controller.signal.aborted) return
        setLoaded((current) => ({
          items: request.before && current ? [...current.items, ...page] : page,
          hasMore: page.length >= PAGE_SIZE,
        }))
        setLoadError(null)
        setRequest(null)
      },
      (reason: unknown) => {
        if (controller.signal.aborted) return
        setLoadError(errorMessage(reason))
        setRequest(null)
      },
    )
    return () => controller.abort()
  }, [videoId, request])

  const items = loaded?.items ?? []
  const loading = request !== null
  const remove = (id: number) =>
    setLoaded(
      (current) => current && { ...current, items: current.items.filter((c) => c.id !== id) },
    )

  return (
    <section className={styles.comments} aria-labelledby="comments-title">
      <h2 id="comments-title" className={styles.title}>
        Comments
      </h2>
      {user ? (
        <CommentForm
          videoId={videoId}
          onPosted={(comment) =>
            setLoaded((current) => ({
              items: [comment, ...(current?.items ?? [])],
              hasMore: current?.hasMore ?? false,
            }))
          }
        />
      ) : (
        <p className={styles.guest}>
          <Link to={paths.login}>Log in</Link> or <Link to={paths.register}>register</Link> to
          comment.
        </p>
      )}
      {loaded && items.length === 0 && !loading && (
        <p className={styles.empty}>No comments yet{user ? ': be the first.' : '.'}</p>
      )}
      <ul className={styles.list}>
        {items.map((comment) => (
          <CommentItem
            key={comment.id}
            videoId={videoId}
            comment={comment}
            mine={comment.username === user?.username}
            onDeleted={() => remove(comment.id)}
          />
        ))}
      </ul>
      {loading ? (
        <StatusMessage kind="loading">Loading comments…</StatusMessage>
      ) : loadError ? (
        <StatusMessage
          kind="error"
          onRetry={() =>
            setRequest((current) => ({
              before: items.at(-1)?.createdAt,
              attempt: (current?.attempt ?? 0) + 1,
            }))
          }
        >
          Comments could not be loaded: {loadError}
        </StatusMessage>
      ) : (
        loaded?.hasMore && (
          <button
            type="button"
            className={`button button-small button-ghost ${styles.more}`}
            onClick={() => setRequest({ before: items.at(-1)?.createdAt, attempt: 0 })}
          >
            Show more
          </button>
        )
      )}
    </section>
  )
}

function CommentForm({
  videoId,
  onPosted,
}: {
  videoId: string
  onPosted: (comment: Comment) => void
}) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const empty = text.trim() === ''

  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    if (empty || busy) return
    setBusy(true)
    setError(null)
    try {
      onPosted(await api.addComment(videoId, text.trim()))
      setText('')
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) void submit()
  }

  return (
    <form className={styles.form} onSubmit={(event) => void submit(event)}>
      <textarea
        className={styles.input}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
        maxLength={MAX_COMMENT_LENGTH}
        rows={2}
        placeholder="Add a comment… (everyone sees it)"
        aria-label="Comment"
      />
      <div className={styles.formRow}>
        {error && (
          <span className={styles.error} role="alert">
            {error}
          </span>
        )}
        {text.length > MAX_COMMENT_LENGTH - 50 && (
          <small className={styles.counter}>
            {text.length} / {MAX_COMMENT_LENGTH}
          </small>
        )}
        <button
          type="submit"
          className="button button-small button-primary"
          disabled={empty || busy}
          title="Post (Ctrl+Enter)"
        >
          {busy ? 'Posting…' : 'Post'}
        </button>
      </div>
    </form>
  )
}

function CommentItem({
  videoId,
  comment,
  mine,
  onDeleted,
}: {
  videoId: string
  comment: Comment
  mine: boolean
  onDeleted: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const remove = async () => {
    if (!window.confirm('Delete your comment?')) return
    setBusy(true)
    setError(null)
    try {
      await api.deleteComment(videoId, comment.id)
      onDeleted()
    } catch (reason) {
      setError(errorMessage(reason))
      setBusy(false)
    }
  }

  return (
    <li className={styles.item}>
      <Link to={paths.profile(comment.username)} className={styles.avatar} tabIndex={-1}>
        <UserAvatar username={comment.username} size={32} />
      </Link>
      <div className={styles.body}>
        <p className={styles.meta}>
          <Link to={paths.profile(comment.username)} className={styles.user}>
            {comment.username}
          </Link>
          <time dateTime={comment.createdAt} title={new Date(comment.createdAt).toLocaleString()}>
            {formatTimeAgo(comment.createdAt)}
          </time>
        </p>
        <p className={styles.text}>{comment.text}</p>
        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
      </div>
      {mine && (
        <button
          type="button"
          className={`button button-small button-ghost ${styles.delete}`}
          onClick={() => void remove()}
          disabled={busy}
          aria-label="Delete comment"
          title="Delete comment"
        >
          <DeleteIcon />
        </button>
      )}
    </li>
  )
}

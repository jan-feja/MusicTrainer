import { type FormEvent, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router'
import { paths } from '../../app/paths'
import { SearchIcon } from '../../components/icons'
import styles from './SearchBox.module.css'

export function SearchBox() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const queryInUrl = location.pathname === '/search' ? (searchParams.get('q') ?? '') : null
  const [text, setText] = useState(queryInUrl ?? '')
  const [shownQuery, setShownQuery] = useState(queryInUrl)

  // follow back / forward navigation between searches
  if (queryInUrl !== null && queryInUrl !== shownQuery) {
    setShownQuery(queryInUrl)
    setText(queryInUrl)
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const query = text.trim()
    if (query) navigate(paths.search(query))
  }

  return (
    <form className={styles.form} role="search" onSubmit={submit}>
      <input
        className={styles.input}
        type="search"
        name="q"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Search YouTube or paste a link"
        aria-label="Search YouTube"
        maxLength={300}
        autoComplete="off"
      />
      <button className={styles.button} type="submit" aria-label="Search">
        <SearchIcon />
      </button>
    </form>
  )
}

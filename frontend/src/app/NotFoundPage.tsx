import { Link } from 'react-router'
import { StatusMessage } from '../components/StatusMessage'
import { useDocumentTitle } from '../lib/useDocumentTitle'
import { paths } from './paths'

export function NotFoundPage() {
  useDocumentTitle('Page not found')
  return (
    <StatusMessage kind="info">
      This page does not exist. <Link to={paths.library}>Go to your library</Link>.
    </StatusMessage>
  )
}

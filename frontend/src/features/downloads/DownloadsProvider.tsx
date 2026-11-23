import { type ReactNode, useCallback, useEffect, useMemo, useReducer } from 'react'
import { api } from '../../api/client'
import type { DownloadJob } from '../../api/types'
import { useMyLibrary } from '../library/myLibrary'
import { DownloadsContext, type DownloadsContextValue } from './downloadsContext'
import { INITIAL_DOWNLOADS_STATE, downloadsReducer, isActiveStatus } from './downloadsState'

const POLL_INTERVAL_MS = 1000

/**
 * Keeps track of the downloads of the user's songs and polls the server while
 * any of them is running. Give it a `key` per user.
 */
export function DownloadsProvider({ children }: { children: ReactNode }) {
  const library = useMyLibrary()
  const [state, dispatch] = useReducer(downloadsReducer, INITIAL_DOWNLOADS_STATE)
  const hasActiveJobs = useMemo(
    () => [...state.jobs.values()].some((job) => isActiveStatus(job.status)),
    [state.jobs],
  )
  const receiveJobs = useCallback(
    (jobs: readonly DownloadJob[]) => dispatch({ type: 'jobsReceived', jobs }),
    [],
  )

  // pick up downloads that were started before the page was (re)loaded
  useEffect(() => {
    const controller = new AbortController()
    api.listDownloads(library.downloadIds(), controller.signal).then(receiveJobs, () => {})
    return () => controller.abort()
  }, [receiveJobs, library])

  useEffect(() => {
    if (!hasActiveJobs) return
    const timer = window.setInterval(() => {
      // if the server is unreachable, try again on the next tick
      api.listDownloads(library.downloadIds()).then(receiveJobs, () => {})
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [hasActiveJobs, receiveJobs, library])

  const startDownload = useCallback(
    async (videoId: string, title?: string) => {
      const job = await api.startDownload(videoId, title)
      library.downloadStarted(videoId)
      receiveJobs([job])
    },
    [receiveJobs, library],
  )

  const forgetDownload = useCallback(
    (videoId: string) => dispatch({ type: 'jobRemoved', videoId }),
    [],
  )

  const value = useMemo<DownloadsContextValue>(
    () => ({
      jobs: state.jobs,
      completedCount: state.completedCount,
      startDownload,
      forgetDownload,
    }),
    [state, startDownload, forgetDownload],
  )
  return <DownloadsContext value={value}>{children}</DownloadsContext>
}

import { createContext, useContext } from 'react'
import type { DownloadJob } from '../../api/types'
import { isActiveStatus } from './downloadsState'

export interface DownloadsContextValue {
  jobs: ReadonlyMap<string, DownloadJob>
  /** Grows by one whenever a download finishes. */
  completedCount: number
  startDownload: (videoId: string, title?: string) => Promise<void>
  /** Drop the job of a video that was deleted from the library. */
  forgetDownload: (videoId: string) => void
}

export const DownloadsContext = createContext<DownloadsContextValue | null>(null)

export function useDownloads(): DownloadsContextValue {
  const value = useContext(DownloadsContext)
  if (value === null) {
    throw new Error('useDownloads() must be used inside <DownloadsProvider>')
  }
  return value
}

export function useDownloadJob(videoId: string): DownloadJob | undefined {
  return useDownloads().jobs.get(videoId)
}

export function useActiveDownloadCount(): number {
  const { jobs } = useDownloads()
  return [...jobs.values()].filter((job) => isActiveStatus(job.status)).length
}

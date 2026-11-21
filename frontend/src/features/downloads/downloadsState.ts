import type { DownloadJob, DownloadStatus } from '../../api/types'

export interface DownloadsState {
  jobs: ReadonlyMap<string, DownloadJob>
  /** Grows by one whenever a download finishes; lists watch it to refresh. */
  completedCount: number
}

export type DownloadsAction =
  /** Fresh job snapshots from the server. */
  | { type: 'jobsReceived'; jobs: readonly DownloadJob[] }
  /** The video was deleted from the library; its old job no longer applies. */
  | { type: 'jobRemoved'; videoId: string }

export const INITIAL_DOWNLOADS_STATE: DownloadsState = { jobs: new Map(), completedCount: 0 }

export function isActiveStatus(status: DownloadStatus): boolean {
  return status === 'queued' || status === 'downloading' || status === 'processing'
}

export function downloadsReducer(state: DownloadsState, action: DownloadsAction): DownloadsState {
  switch (action.type) {
    case 'jobsReceived': {
      const jobs = new Map(state.jobs)
      let newlyCompleted = 0
      for (const job of action.jobs) {
        const previous = jobs.get(job.videoId)
        if (job.status === 'completed' && previous && isActiveStatus(previous.status)) {
          newlyCompleted += 1
        }
        jobs.set(job.videoId, job)
      }
      return { jobs, completedCount: state.completedCount + newlyCompleted }
    }
    case 'jobRemoved': {
      const jobs = new Map(state.jobs)
      jobs.delete(action.videoId)
      return { ...state, jobs }
    }
  }
}

export function describeJob(job: DownloadJob): string {
  switch (job.status) {
    case 'queued':
      return 'Waiting to download…'
    case 'downloading':
      return `Downloading ${Math.round(job.progress * 100)} %`
    case 'processing':
      return 'Merging video and audio…'
    case 'completed':
      return 'Downloaded'
    case 'failed':
      return `Download failed: ${job.error ?? 'unknown error'}`
  }
}

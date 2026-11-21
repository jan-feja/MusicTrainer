import { describe, expect, it } from 'vitest'
import type { DownloadJob } from '../../api/types'
import {
  type DownloadsState,
  INITIAL_DOWNLOADS_STATE,
  describeJob,
  downloadsReducer,
} from './downloadsState'

function job(status: DownloadJob['status'], progress = 0, videoId = 'jNQXAC9IVRw'): DownloadJob {
  return { videoId, status, progress, title: null, error: null }
}

function receive(state: DownloadsState, ...jobs: DownloadJob[]): DownloadsState {
  return downloadsReducer(state, { type: 'jobsReceived', jobs })
}

describe('downloadsReducer', () => {
  it('adds and replaces jobs by video ID', () => {
    const state = receive(INITIAL_DOWNLOADS_STATE, job('downloading', 0.2))
    const next = receive(state, job('downloading', 0.6), job('queued', 0, 'dQw4w9WgXcQ'))
    expect(next.jobs.get('jNQXAC9IVRw')?.progress).toBe(0.6)
    expect(next.jobs.size).toBe(2)
  })

  it('counts downloads that just finished', () => {
    let state = receive(INITIAL_DOWNLOADS_STATE, job('downloading', 0.5))
    state = receive(state, job('completed', 1))
    expect(state.completedCount).toBe(1)
    // the same finished job again does not count twice
    state = receive(state, job('completed', 1))
    expect(state.completedCount).toBe(1)
  })

  it('does not count jobs that were already finished when first seen', () => {
    expect(receive(INITIAL_DOWNLOADS_STATE, job('completed', 1)).completedCount).toBe(0)
  })

  it('removes jobs of deleted videos', () => {
    const state = receive(INITIAL_DOWNLOADS_STATE, job('completed', 1))
    const next = downloadsReducer(state, { type: 'jobRemoved', videoId: 'jNQXAC9IVRw' })
    expect(next.jobs.size).toBe(0)
  })
})

describe('describeJob', () => {
  it('describes each status', () => {
    expect(describeJob(job('downloading', 0.426))).toBe('Downloading 43 %')
    expect(describeJob({ ...job('failed'), error: 'Video unavailable' })).toBe(
      'Download failed: Video unavailable',
    )
  })
})

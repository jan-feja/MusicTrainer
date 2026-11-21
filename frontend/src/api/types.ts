/** JSON types of the backend API (mirrors backend/src/music_trainer/models.py). */

export interface SearchResult {
  videoId: string
  title: string
  channel: string | null
  durationSeconds: number | null
  viewCount: number | null
  thumbnailUrl: string | null
  isDownloaded: boolean
}

export interface LibraryVideo {
  videoId: string
  title: string
  channel: string | null
  durationSeconds: number | null
  /** ISO date, e.g. "2024-01-31" */
  uploadDate: string | null
  viewCount: number | null
  description: string | null
  sourceUrl: string
  /** ISO date-time */
  downloadedAt: string | null
  mediaUrl: string
  thumbnailUrl: string | null
}

export type DownloadStatus = 'queued' | 'downloading' | 'processing' | 'completed' | 'failed'

export interface DownloadJob {
  videoId: string
  status: DownloadStatus
  /** 0..1 */
  progress: number
  title: string | null
  error: string | null
}

/** The beat grid of a song. */
export interface BeatAnalysis {
  bpm: number | null
  beatsPerBar: number | null
  /** Beat times in seconds, ascending. */
  beats: number[]
  /** Bar starts in seconds; each one is also in `beats`. */
  downbeats: number[]
  analyzer: string
}

export type AnalysisStatus = 'not_started' | 'queued' | 'analyzing' | 'completed' | 'failed'

export interface BeatTrackingState {
  videoId: string
  status: AnalysisStatus
  /** Set once the status is 'completed'. */
  analysis: BeatAnalysis | null
  error: string | null
}

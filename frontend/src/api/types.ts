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
  /** Sections of the audio as WAV: `?start=&end=` in seconds. */
  audioUrl: string
  /** Pictures of the music for the grid editor (MusicVisual). */
  visualUrl: string
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

/**
 * A part of the song with its own bars: one starts at `start`, the section lasts until the
 * next one. Unset fields are left to the detection.
 */
export interface GridSection {
  start: number
  /** Every bar of the section has this many beats. */
  beatsPerBar: number | null
  /** Bar lengths in beats, repeated from the section start, e.g. [6, 6, 5, 6, 5, 5]. */
  pattern: number[]
  /** The section's beats are near this tempo (e.g. eighth notes, twice the song's tempo). */
  tempoBpm: number | null
}

/** What the user knows about a song's beat grid; null leaves it to the detection. */
export interface BeatGridHints {
  /** Every bar has this many beats. */
  beatsPerBar: number | null
  /** The tempo is near this; decides between e.g. 75 and 150 BPM. */
  tempoBpm: number | null
  /** Times (s) where a bar starts; from each one on, bars are counted from there. */
  barStarts: number[]
  /** The song is played to a click: all beats exactly evenly spaced. */
  steadyTempo: boolean
  /** Parts of the song with their own meter, bar pattern or tempo. */
  sections: GridSection[]
}

/** Pictures of the music for the grid editor; arrays are base64 of uint8 values. */
export interface MusicVisual {
  /** Spectrogram frames per second. */
  fps: number
  bands: number
  frames: number
  /** frames x bands, low frequencies first, 255 = loudest. */
  spectrogram: string
  /** Seconds per section color. */
  colorStep: number
  /** RGB per color step: similar music, similar color. */
  colors: string
  beatFps: number | null
  /** Per frame, how likely the beat network finds a beat (0-255). */
  beat: string | null
  /** Per frame, how likely it finds a bar start (0-255). */
  downbeat: string | null
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
  /** The hints the grid was detected with. */
  hints: BeatGridHints
}

export type AnalysisStatus = 'not_started' | 'queued' | 'analyzing' | 'completed' | 'failed'

export interface BeatTrackingState {
  videoId: string
  status: AnalysisStatus
  /** Set once the status is 'completed'. */
  analysis: BeatAnalysis | null
  error: string | null
}

/** What loop points snap to. */
export type LoopSnapMode = 'off' | 'beat' | 'bar'

/** A practice loop saved with a video (the video's loops.json). */
export interface SavedLoop {
  id: string
  name: string
  start: number
  end: number
  snapMode: LoopSnapMode
  /** The speed the loop is practiced at. */
  playbackRate: number
}

/** How the player was left for a video (its player.json); restored when it is opened. */
export interface PlayerSettings {
  volume: number
  muted: boolean
  playbackRate: number
  /** null: whatever the browser used last */
  snapMode: LoopSnapMode | null
  position: number
  loopStart: number | null
  loopEnd: number | null
  loopEnabled: boolean
  /** The saved loop being played and edited. */
  activeLoopId: string | null
}

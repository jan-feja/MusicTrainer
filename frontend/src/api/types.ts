/** JSON types of the backend API (mirrors backend/src/music_trainer/models.py). */

export interface SearchResult {
  videoId: string
  title: string
  channel: string | null
  durationSeconds: number | null
  viewCount: number | null
  thumbnailUrl: string | null
  /** On the server (someone has it): adding it to a library is instant. */
  isDownloaded: boolean
  /** In the logged-in user's library; always false for a guest (theirs is in the browser). */
  inLibrary: boolean
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
  /** The stem mixer; null or missing: stems were never turned on for this video. */
  mixer?: MixerSettings | null
}

/** One separated instrument track, e.g. 'drums', 'bass', 'vocals', 'guitar', 'piano', 'other'. */
export interface StemInfo {
  name: string
  /** File name inside the video's stems/ folder (FLAC). */
  file: string
  /** Loudness 0–1; near 0: the instrument is not in the song. */
  rms: number
}

/** The separated tracks of a song: same sample rate and length, all starting at time 0. */
export interface StemSet {
  /** e.g. 'demucs:htdemucs_6s' */
  model: string
  sampleRate: number
  duration: number
  stems: StemInfo[]
}

export interface StemSeparationState {
  videoId: string
  status: AnalysisStatus
  /** Share separated (0–1) while 'analyzing'; null if unknown. */
  progress: number | null
  /** While 'queued': how many songs are separated before this one. */
  queuePosition: number | null
  /** Set once the status is 'completed'. */
  stems: StemSet | null
  error: string | null
}

export interface Chord {
  start: number
  end: number
  /** e.g. 'A:min', 'C:maj'; 'N' for no chord */
  label: string
}

/** The chords of a song, changing only on beats. */
export interface ChordAnalysis {
  method: string
  /** In time order, without gaps. */
  chords: Chord[]
  /** The beat grid they were found on. */
  grid: string | null
  /** Found on the pitched stems (no drums or vocals) rather than the whole mix. */
  fromStems: boolean
}

export interface ChordDetectionState {
  videoId: string
  status: AnalysisStatus
  /** Set once the status is 'completed'. */
  analysis: ChordAnalysis | null
  error: string | null
}

/** The stem mixer of a video, kept in its player.json. */
export interface MixerSettings {
  /** Play the stems instead of the video's own sound. */
  enabled: boolean
  /** Per stem, 0–1; a stem not listed plays at 1. */
  volumes: Record<string, number>
  muted: string[]
  /** When not empty, only these stems are heard. */
  solo: string[]
}

export interface User {
  id: number
  username: string
}

/** A song from a guest's library in the browser, moved into the account on login. */
export interface GuestImportEntry {
  videoId: string
  loops?: SavedLoop[]
  settings?: PlayerSettings
}

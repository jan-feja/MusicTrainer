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

export interface MetronomeSettings {
  enabled: boolean
  /** 0–1 */
  volume: number
}

/**
 * A named way to practice a song: its loop, speed, stem mix and metronome.
 * Choosing it sets the player that way; what it does not hold is left as it is.
 */
export interface Preset {
  id: string
  name: string
  /** The loop in seconds; null (both): the whole song, no loop. */
  start: number | null
  end: number | null
  snapMode: LoopSnapMode
  playbackRate: number
  /** null or missing: the stems are left as they are. */
  mixer?: MixerSettings | null
  /** null or missing: the metronome is left as it is. */
  metronome?: MetronomeSettings | null
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
  /** The preset chosen last. */
  activePresetId: string | null
  /** The stem mixer; null or missing: stems were never turned on for this video. */
  mixer?: MixerSettings | null
  metronome?: MetronomeSettings | null
  /** The user's fixes of the beat grid; null or missing: the detected grid as it is. */
  gridHints?: BeatGridHints | null
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
  /** The beat grid the chords are on; poll with it. null: no beat grid yet. */
  grid: string | null
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
  presets?: Preset[]
  settings?: PlayerSettings
}

/** A song in the logged-in user's library. */
export interface MyLibraryVideo extends LibraryVideo {
  starred: boolean
}

export interface MyLibraryEntry {
  videoId: string
  addedAt: string
  starred: boolean
}

/** How the viewer relates to a profile: 'requested' waits for a private profile's owner. */
export type FollowState = 'none' | 'requested' | 'following' | 'self'

/** A user in a list (followers, requests). */
export interface UserSummary {
  username: string
  description: string
}

/** A user's profile as the viewer may see it. */
export interface Profile {
  username: string
  description: string
  isPrivate: boolean
  joinedAt: string
  followers: number
  following: number
  followState: FollowState
  /** The viewer may see the songs and history (public, their own, or an accepted follower). */
  canView: boolean
  /** null when the viewer may not see it (also below). */
  libraryCount: number | null
  practiceSeconds: number | null
}

export interface ProfileSettings {
  description: string
  isPrivate: boolean
}

/** How long a user practiced a song on one day (UTC). */
export interface PracticeEntry {
  videoId: string
  title: string
  /** YYYY-MM-DD */
  day: string
  /** When the song was last played that day. */
  lastAt: string
  seconds: number
}

export interface FeedEntry extends PracticeEntry {
  username: string
}

export type FeedScope = 'everyone' | 'following'

/** The first songs of a user's library, and how many there are in all. */
export interface ProfileLibrary {
  videos: LibraryVideo[]
  total: number
}

/** Someone asks to follow the user / started following them / accepted the user's request. */
export type NotificationKind = 'follow_request' | 'new_follower' | 'request_accepted'

export interface Notification {
  kind: NotificationKind
  /** The other user. */
  username: string
  at: string
  /** Newer than when the user last opened the notifications. */
  unread: boolean
  /** How the user relates to the other user (e.g. whether they follow back). */
  followState: FollowState
}

export interface Notifications {
  /** Follow requests first, then the rest, newest first. */
  items: Notification[]
  unread: number
}

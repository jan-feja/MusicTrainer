/**
 * A guest's library, kept in this browser: which songs, with their saved loops
 * and player settings. Moved into the account on login (see `importEntries`).
 *
 * Storage can be missing or full (private mode, blocked site data): reads then
 * find nothing and writes are dropped, so the app still works for the page.
 */
import type { GuestImportEntry, PlayerSettings, SavedLoop } from '../../api/types'
import { isValidVideoId } from '../../lib/youtube'

export type KeyValueStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

const PREFIX = 'musicTrainer.guest.'
const LIBRARY_KEY = `${PREFIX}library`
const loopsKey = (videoId: string) => `${PREFIX}loops.${videoId}`
const settingsKey = (videoId: string) => `${PREFIX}settings.${videoId}`

export interface GuestSong {
  videoId: string
  /** ms since 1970 */
  addedAt: number
}

export class GuestStorage {
  private readonly storage: KeyValueStorage | null

  constructor(storage: KeyValueStorage | null) {
    this.storage = storage
  }

  /** The songs, most recently added first. */
  songs(): GuestSong[] {
    const stored = this.read(LIBRARY_KEY)
    if (!Array.isArray(stored)) return []
    return stored.filter(isGuestSong).sort((a, b) => b.addedAt - a.addedAt)
  }

  videoIds(): string[] {
    return this.songs().map((song) => song.videoId)
  }

  add(videoId: string, now = Date.now()): void {
    const songs = this.songs()
    if (songs.some((song) => song.videoId === videoId)) return
    this.write(LIBRARY_KEY, [{ videoId, addedAt: now }, ...songs])
  }

  /** Remove the song with its loops and settings. */
  remove(videoId: string): void {
    this.write(
      LIBRARY_KEY,
      this.songs().filter((song) => song.videoId !== videoId),
    )
    this.delete(loopsKey(videoId))
    this.delete(settingsKey(videoId))
  }

  loops(videoId: string): SavedLoop[] {
    const stored = this.read(loopsKey(videoId))
    return Array.isArray(stored) ? stored.filter(isSavedLoop) : []
  }

  saveLoops(videoId: string, loops: SavedLoop[]): void {
    this.write(loopsKey(videoId), loops)
  }

  /** How the player was left; null if never opened (the caller uses the defaults). */
  settings(videoId: string): PlayerSettings | null {
    const stored = this.read(settingsKey(videoId))
    return isObject(stored) ? (stored as unknown as PlayerSettings) : null
  }

  saveSettings(videoId: string, settings: PlayerSettings): void {
    this.write(settingsKey(videoId), settings)
  }

  /** Everything, as the account's import takes it. */
  importEntries(): GuestImportEntry[] {
    return this.songs().map(({ videoId }) => {
      const loops = this.loops(videoId)
      const settings = this.settings(videoId)
      return {
        videoId,
        ...(loops.length > 0 && { loops }),
        ...(settings && { settings }),
      }
    })
  }

  /** Forget the guest's library, e.g. once it is in the account. */
  clear(): void {
    for (const { videoId } of this.songs()) this.remove(videoId)
    this.delete(LIBRARY_KEY)
  }

  private read(key: string): unknown {
    try {
      const text = this.storage?.getItem(key)
      return text ? (JSON.parse(text) as unknown) : null
    } catch {
      return null // unreadable: as if nothing was stored
    }
  }

  private write(key: string, value: unknown): void {
    try {
      this.storage?.setItem(key, JSON.stringify(value))
    } catch {
      // full or blocked: kept for this page only
    }
  }

  private delete(key: string): void {
    try {
      this.storage?.removeItem(key)
    } catch {
      // blocked: nothing to remove
    }
  }
}

function browserStorage(): KeyValueStorage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** The guest library of this browser. */
export const guestStorage = new GuestStorage(browserStorage())

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isGuestSong(value: unknown): value is GuestSong {
  return (
    isObject(value) &&
    typeof value.videoId === 'string' &&
    isValidVideoId(value.videoId) &&
    typeof value.addedAt === 'number'
  )
}

function isSavedLoop(value: unknown): value is SavedLoop {
  return (
    isObject(value) &&
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    typeof value.start === 'number' &&
    typeof value.end === 'number' &&
    value.end > value.start
  )
}

/**
 * A guest's library, kept in this browser: which songs, with their presets
 * and player settings. Moved into the account on login (see `importEntries`).
 *
 * Storage can be missing or full (private mode, blocked site data): reads then
 * find nothing and writes are dropped, so the app still works for the page.
 */
import type { GuestImportEntry, PlayerSettings, Preset } from '../../api/types'
import { isValidVideoId } from '../../lib/youtube'

export type KeyValueStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

const PREFIX = 'musicTrainer.guest.'
const LIBRARY_KEY = `${PREFIX}library`
const presetsKey = (videoId: string) => `${PREFIX}presets.${videoId}`
/** Before presets there were saved loops; a saved loop is a valid preset. */
const oldLoopsKey = (videoId: string) => `${PREFIX}loops.${videoId}`
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

  /** Remove the song with its presets and settings. */
  remove(videoId: string): void {
    this.write(
      LIBRARY_KEY,
      this.songs().filter((song) => song.videoId !== videoId),
    )
    this.delete(presetsKey(videoId))
    this.delete(oldLoopsKey(videoId))
    this.delete(settingsKey(videoId))
  }

  presets(videoId: string): Preset[] {
    const stored = this.read(presetsKey(videoId)) ?? this.read(oldLoopsKey(videoId))
    return Array.isArray(stored) ? stored.filter(isPreset) : []
  }

  savePresets(videoId: string, presets: Preset[]): void {
    this.write(presetsKey(videoId), presets)
    this.delete(oldLoopsKey(videoId))
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
      const presets = this.presets(videoId)
      const settings = this.settings(videoId)
      return {
        videoId,
        ...(presets.length > 0 && { presets }),
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

function isPreset(value: unknown): value is Preset {
  if (!isObject(value) || typeof value.id !== 'string' || typeof value.name !== 'string') {
    return false
  }
  const { start, end } = value
  const wholeSong = (start === null || start === undefined) && (end === null || end === undefined)
  const loop = typeof start === 'number' && typeof end === 'number' && end > start
  return wholeSong || loop
}

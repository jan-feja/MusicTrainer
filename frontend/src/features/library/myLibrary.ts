/**
 * The user's own library, whoever the user is: an account keeps it on the
 * server, a guest in this browser. Opening a song adds it, as downloading does.
 */
import { useMemo } from 'react'
import { api, isNotFoundError } from '../../api/client'
import type { FollowedPresets, LibraryVideo, PlayerSettings, Preset, User } from '../../api/types'
import { useAuth } from '../auth/authContext'
import { guestStorage } from './guestStorage'

export interface LibraryListing {
  /** `starred` only for an account (guests cannot star). */
  videos: (LibraryVideo & { starred?: boolean })[]
  /** A guest's songs that are gone from the server (nobody used them for a while). */
  removedCount: number
}

export interface PracticeData {
  presets: Preset[]
  /** null: the song was never opened (the player starts from its defaults). */
  settings: PlayerSettings | null
  /** Only for an account (guests cannot star). */
  starred?: boolean
}

export interface MyLibrary {
  isGuest: boolean
  /** The song is in the library; `inAccountLibrary` is what the server said for an account. */
  has: (videoId: string, inAccountLibrary: boolean) => boolean
  /** The songs on the server; those still downloading are the downloads' jobs. */
  list: (signal?: AbortSignal) => Promise<LibraryListing>
  /** Up to `count` of the songs on the server, picked at random. */
  sample: (count: number, signal?: AbortSignal) => Promise<LibraryListing['videos']>
  remove: (videoId: string) => Promise<void>
  /** A download was started; an account's library has it already. */
  downloadStarted: (videoId: string) => void
  /** The songs whose downloads to follow; undefined: the server knows them. */
  downloadIds: () => string[] | undefined
  /** Add the song (if needed) and load its presets and player settings. */
  openSong: (videoId: string, signal?: AbortSignal) => Promise<PracticeData>
  savePresets: (videoId: string, presets: Preset[], keepalive: boolean) => Promise<unknown>
  saveSettings: (videoId: string, settings: PlayerSettings, keepalive: boolean) => Promise<unknown>
  /** The presets of the song made by the users the account follows (guests follow nobody). */
  followedPresets?: (videoId: string, signal?: AbortSignal) => Promise<FollowedPresets[]>
  /** The music played `seconds` more: the account's practice history (guests have none). */
  reportPractice?: (videoId: string, seconds: number, keepalive: boolean) => void
}

export function useMyLibrary(): MyLibrary {
  const { user } = useAuth()
  return useMemo(() => (user ? accountLibrary(user) : GUEST_LIBRARY), [user])
}

function accountLibrary(_user: User): MyLibrary {
  return {
    isGuest: false,
    has: (_videoId, inAccountLibrary) => inAccountLibrary,
    list: async (signal) => ({ videos: await api.listMyVideos(signal), removedCount: 0 }),
    sample: (count, signal) => api.randomMyVideos(count, signal),
    remove: (videoId) => api.removeFromMyLibrary(videoId),
    downloadStarted: () => {},
    downloadIds: () => undefined,
    openSong: async (videoId, signal) => {
      await api.addToMyLibrary(videoId)
      const [presets, settings, entry] = await Promise.all([
        api.getPresets(videoId, signal),
        api.getPlayerSettings(videoId, signal),
        api.getMyEntry(videoId, signal),
      ])
      return { presets, settings, starred: entry.starred }
    },
    savePresets: (videoId, presets, keepalive) => api.savePresets(videoId, presets, keepalive),
    saveSettings: (videoId, settings, keepalive) =>
      api.savePlayerSettings(videoId, settings, keepalive),
    followedPresets: (videoId, signal) => api.getFollowedPresets(videoId, signal),
    // the history is not worth bothering the user about
    reportPractice: (videoId, seconds, keepalive) =>
      void api.reportPractice(videoId, seconds, keepalive).catch(() => {}),
  }
}

const GUEST_LIBRARY: MyLibrary = {
  isGuest: true,
  has: (videoId) => guestStorage.videoIds().includes(videoId),
  list: async (signal) => {
    const videoIds = guestStorage.videoIds()
    const results = await Promise.all(
      videoIds.map((videoId) =>
        api.getVideo(videoId, signal).catch((error: unknown) => {
          if (!isNotFoundError(error)) throw error
          return null
        }),
      ),
    )
    const videos = results.filter((video) => video !== null)
    const missing = videoIds.filter((_videoId, index) => results[index] === null)
    if (missing.length === 0) return { videos, removedCount: 0 }
    // not on the server: still downloading (or failed: it can be retried), or deleted
    const jobs = await api.listDownloads(missing, signal)
    const downloading = new Set(
      jobs.filter((job) => job.status !== 'completed').map((job) => job.videoId),
    )
    const deleted = missing.filter((videoId) => !downloading.has(videoId))
    deleted.forEach((videoId) => guestStorage.remove(videoId))
    return { videos, removedCount: deleted.length }
  },
  sample: async (count, signal) => {
    // a few more than needed: some may be gone from the server or still downloading
    const videoIds = shuffled(guestStorage.videoIds()).slice(0, count * 2)
    const videos = await Promise.all(
      videoIds.map((videoId) => api.getVideo(videoId, signal).catch(() => null)),
    )
    return videos.filter((video) => video !== null).slice(0, count)
  },
  remove: async (videoId) => guestStorage.remove(videoId),
  downloadStarted: (videoId) => guestStorage.add(videoId),
  downloadIds: () => guestStorage.videoIds(),
  openSong: async (videoId) => {
    guestStorage.add(videoId)
    return { presets: guestStorage.presets(videoId), settings: guestStorage.settings(videoId) }
  },
  savePresets: async (videoId, presets) => guestStorage.savePresets(videoId, presets),
  saveSettings: async (videoId, settings) => guestStorage.saveSettings(videoId, settings),
}

function shuffled<T>(items: readonly T[]): T[] {
  const result = [...items]
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[result[i], result[j]] = [result[j], result[i]]
  }
  return result
}

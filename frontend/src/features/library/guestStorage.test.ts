import { describe, expect, it } from 'vitest'
import type { PlayerSettings, Preset } from '../../api/types'
import { GuestStorage, type KeyValueStorage } from './guestStorage'

const A = 'jNQXAC9IVRw'
const B = 'dQw4w9WgXcQ'
const LOOP: Preset = {
  id: 'l1',
  name: 'Verse',
  start: 1,
  end: 2,
  snapMode: 'off',
  playbackRate: 1,
}

function memoryStorage(): KeyValueStorage & { data: Map<string, string> } {
  const data = new Map<string, string>()
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
    removeItem: (key) => void data.delete(key),
  }
}

describe('GuestStorage', () => {
  it('keeps songs newest first, each once', () => {
    const guest = new GuestStorage(memoryStorage())
    guest.add(A, 1)
    guest.add(B, 2)
    guest.add(A, 3)
    expect(guest.videoIds()).toEqual([B, A])
  })

  it('removes a song with its presets and settings', () => {
    const storage = memoryStorage()
    const guest = new GuestStorage(storage)
    guest.add(A)
    guest.savePresets(A, [LOOP])
    guest.saveSettings(A, { volume: 0.5 } as PlayerSettings)
    guest.remove(A)
    expect(guest.videoIds()).toEqual([])
    expect(guest.presets(A)).toEqual([])
    expect(guest.settings(A)).toBeNull()
  })

  it('builds the import for the account and clears everything', () => {
    const storage = memoryStorage()
    const guest = new GuestStorage(storage)
    guest.add(A, 1)
    guest.add(B, 2)
    guest.savePresets(A, [LOOP])
    guest.saveSettings(B, { volume: 0.5 } as PlayerSettings)
    expect(guest.importEntries()).toEqual([
      { videoId: B, settings: { volume: 0.5 } },
      { videoId: A, presets: [LOOP] },
    ])
    guest.clear()
    expect(storage.data.size).toBe(0)
  })

  it('ignores unreadable or odd data', () => {
    const storage = memoryStorage()
    const guest = new GuestStorage(storage)
    storage.setItem('musicTrainer.guest.library', '{broken')
    expect(guest.songs()).toEqual([])
    storage.setItem(
      'musicTrainer.guest.library',
      JSON.stringify([{ videoId: '../x', addedAt: 1 }, { videoId: A, addedAt: 2 }, 'nope']),
    )
    expect(guest.videoIds()).toEqual([A])
    // saved loops from before presets are presets too
    storage.setItem(
      `musicTrainer.guest.loops.${A}`,
      JSON.stringify([LOOP, { ...LOOP, end: 0 }, { ...LOOP, end: null }, null]),
    )
    expect(guest.presets(A)).toEqual([LOOP])
    const wholeSong = { ...LOOP, id: 'l2', start: null, end: null }
    guest.savePresets(A, [wholeSong])
    expect(guest.presets(A)).toEqual([wholeSong])
    expect(storage.data.has(`musicTrainer.guest.loops.${A}`)).toBe(false)
  })

  it('works without storage, and when it throws', () => {
    expect(new GuestStorage(null).songs()).toEqual([])
    const throwing: KeyValueStorage = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('full')
      },
      removeItem: () => {
        throw new Error('blocked')
      },
    }
    const guest = new GuestStorage(throwing)
    expect(() => guest.add(A)).not.toThrow()
    expect(guest.songs()).toEqual([])
    expect(() => guest.clear()).not.toThrow()
  })
})

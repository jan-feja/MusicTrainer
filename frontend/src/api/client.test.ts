import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, isNotFoundError } from './client'

function mockFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('builds the search URL and returns the JSON body', async () => {
    const fetchMock = mockFetch(Response.json([{ videoId: 'jNQXAC9IVRw' }]))
    const results = await api.search('bass & drums')
    expect(fetchMock).toHaveBeenCalledWith('/api/search?q=bass+%26+drums', { signal: undefined })
    expect(results).toEqual([{ videoId: 'jNQXAC9IVRw' }])
  })

  it('sends download requests as JSON', async () => {
    const fetchMock = mockFetch(Response.json({ videoId: 'jNQXAC9IVRw' }, { status: 202 }))
    await api.startDownload('jNQXAC9IVRw', 'Me at the zoo')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/downloads')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ videoId: 'jNQXAC9IVRw', title: 'Me at the zoo' })
  })

  it("starts beat detection and asks for the user's own grid", async () => {
    const fetchMock = mockFetch(Response.json({ status: 'queued' }, { status: 202 }))
    await api.detectBeats('jNQXAC9IVRw')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/library/jNQXAC9IVRw/beats')
    expect(fetchMock.mock.calls[0][1].body).toBeUndefined()

    fetchMock.mockResolvedValue(Response.json({ status: 'queued' }, { status: 202 }))
    await api.detectBeats('jNQXAC9IVRw', { force: true })
    expect(fetchMock.mock.calls[1][0]).toBe('/api/library/jNQXAC9IVRw/beats?force=true')

    fetchMock.mockResolvedValue(Response.json({ beats: [] }))
    const hints = { beatsPerBar: 3, tempoBpm: null, barStarts: [], steadyTempo: false }
    await api.getBeatGrid('jNQXAC9IVRw', hints)
    const [url, init] = fetchMock.mock.calls[2]
    expect(url).toBe('/api/library/jNQXAC9IVRw/beats/grid')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual(hints)
  })

  it('asks for the chords on a grid', async () => {
    const fetchMock = mockFetch(Response.json({ status: 'queued', grid: '0123456789abcdef' }))
    await api.detectChords('jNQXAC9IVRw', null)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/library/jNQXAC9IVRw/chords')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toBeNull()
    fetchMock.mockResolvedValue(Response.json({ status: 'queued' }))
    await api.getChords('jNQXAC9IVRw', '0123456789abcdef')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/library/jNQXAC9IVRw/chords?grid=0123456789abcdef')
  })

  it('starts stem separation and points at the stem files', async () => {
    const fetchMock = mockFetch(Response.json({ status: 'queued' }, { status: 202 }))
    await api.separateStems('jNQXAC9IVRw', { force: true })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/library/jNQXAC9IVRw/stems?force=true')
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
    expect(api.stemUrl('jNQXAC9IVRw', 'drums')).toBe('/api/library/jNQXAC9IVRw/stems/drums')
  })

  it("keeps presets and settings in the user's own library", async () => {
    const fetchMock = mockFetch(Response.json([]))
    await api.getPresets('jNQXAC9IVRw')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/me/library/jNQXAC9IVRw/presets')
    fetchMock.mockResolvedValue(Response.json({}))
    await api.savePlayerSettings('jNQXAC9IVRw', {} as never, true)
    expect(fetchMock.mock.calls[1][0]).toBe('/api/me/library/jNQXAC9IVRw/settings')
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: 'PUT', keepalive: true })
  })

  it("lists the downloads of a guest's songs by their IDs", async () => {
    const fetchMock = mockFetch(Response.json([]))
    await api.listDownloads(['jNQXAC9IVRw', 'dQw4w9WgXcQ'])
    expect(fetchMock.mock.calls[0][0]).toBe('/api/downloads?ids=jNQXAC9IVRw&ids=dQw4w9WgXcQ')
    fetchMock.mockResolvedValue(Response.json([]))
    await api.listDownloads()
    expect(fetchMock.mock.calls[1][0]).toBe('/api/downloads')
  })

  it('logs in with a JSON body', async () => {
    const fetchMock = mockFetch(Response.json({ id: 1, username: 'alice' }))
    await api.login('alice', 'secret password')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/login')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ username: 'alice', password: 'secret password' })
  })

  it('returns nothing for 204 responses', async () => {
    mockFetch(new Response(null, { status: 204 }))
    await expect(api.removeFromMyLibrary('jNQXAC9IVRw')).resolves.toBeUndefined()
  })

  it('throws ApiError with the server message', async () => {
    mockFetch(Response.json({ detail: 'Video x is not in the library' }, { status: 404 }))
    const error = await api.getVideo('jNQXAC9IVRw').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).message).toBe('Video x is not in the library')
    expect(isNotFoundError(error)).toBe(true)
  })

  it('falls back to the status text when the body is not JSON', async () => {
    mockFetch(new Response('oops', { status: 500, statusText: 'Internal Server Error' }))
    await expect(api.listMyVideos()).rejects.toThrow('Request failed (500 Internal Server Error)')
  })
})

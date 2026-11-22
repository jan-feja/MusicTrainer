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

  it('starts beat detection with or without hints', async () => {
    const fetchMock = mockFetch(Response.json({ status: 'queued' }, { status: 202 }))
    await api.detectBeats('jNQXAC9IVRw')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/library/jNQXAC9IVRw/beats')
    expect(fetchMock.mock.calls[0][1].body).toBeUndefined()

    fetchMock.mockResolvedValue(Response.json({ status: 'queued' }, { status: 202 }))
    await api.detectBeats('jNQXAC9IVRw', { force: true })
    expect(fetchMock.mock.calls[1][0]).toBe('/api/library/jNQXAC9IVRw/beats?force=true')

    fetchMock.mockResolvedValue(Response.json({ status: 'queued' }, { status: 202 }))
    await api.detectBeats('jNQXAC9IVRw', {
      hints: { beatsPerBar: 3, tempoBpm: null, barStarts: [], steadyTempo: false, sections: [] },
    })
    const [url, init] = fetchMock.mock.calls[2]
    expect(url).toBe('/api/library/jNQXAC9IVRw/beats')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({
      beatsPerBar: 3,
      tempoBpm: null,
      barStarts: [],
      steadyTempo: false,
      sections: [],
    })
  })

  it('returns nothing for 204 responses', async () => {
    mockFetch(new Response(null, { status: 204 }))
    await expect(api.deleteVideo('jNQXAC9IVRw')).resolves.toBeUndefined()
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
    await expect(api.listVideos()).rejects.toThrow('Request failed (500 Internal Server Error)')
  })
})

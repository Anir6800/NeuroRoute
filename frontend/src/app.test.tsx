import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { fetchHealth } from './api/health'

afterEach(cleanup)

const jsonFetch = (body: unknown, status = 200) =>
  vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })) as unknown as typeof fetch

describe('fetchHealth', () => {
  it('returns data on a valid response', async () => {
    const r = await fetchHealth(jsonFetch({ status: 'ok', app: 'NeuroRoute', version: '0.1.0' }), '/api')
    expect(r).toEqual({ ok: true, data: { status: 'ok', app: 'NeuroRoute', version: '0.1.0' } })
  })
  it('reports HTTP errors', async () => {
    expect(await fetchHealth(jsonFetch({}, 500), '/api')).toEqual({ ok: false, error: 'HTTP 500' })
  })
  it('rejects a malformed body', async () => {
    expect((await fetchHealth(jsonFetch({ status: 1 }), '/api')).ok).toBe(false)
  })
  it('reports unreachable backend', async () => {
    const down = vi.fn().mockRejectedValue(new TypeError('x')) as unknown as typeof fetch
    expect(await fetchHealth(down, '/api')).toEqual({ ok: false, error: 'Backend unreachable' })
  })
  it('times out', async () => {
    const hang = ((_u: string, init: RequestInit) =>
      new Promise((_, reject) =>
        init.signal!.addEventListener('abort', () => reject(new DOMException('a', 'AbortError'))),
      )) as unknown as typeof fetch
    expect(await fetchHealth(hang, '/api', 20)).toEqual({ ok: false, error: 'Timed out after 20 ms' })
  })
})

describe('App shell', () => {
  it('renders home with navigation', () => {
    vi.stubGlobal('fetch', jsonFetch({ status: 'ok', app: 'NeuroRoute', version: '0.1.0' }))
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Overview' })).toBeTruthy()
    vi.unstubAllGlobals()
  })
  it('renders not-found for unknown routes', () => {
    vi.stubGlobal('fetch', jsonFetch({}))
    render(
      <MemoryRouter initialEntries={['/nope']}>
        <App />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeTruthy()
    vi.unstubAllGlobals()
  })
})

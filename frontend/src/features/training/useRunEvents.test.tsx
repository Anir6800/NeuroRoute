import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useRunEvents } from './useRunEvents'

class Socket {
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  sent: string[] = []

  send(data: string) { this.sent.push(data) }
  close() { /* test controls disconnects explicitly */ }
  open() { this.onopen?.(new Event('open')) }
  message(value: object) { this.onmessage?.({ data: JSON.stringify(value) } as MessageEvent<string>) }
  disconnect() { this.onclose?.(new CloseEvent('close')) }
}

afterEach(() => vi.restoreAllMocks())

describe('useRunEvents', () => {
  it('streams progress, polls on disconnect, reconnects, and stops at completion', async () => {
    const sockets: Socket[] = []
    const socketFactory = vi.fn(() => {
      const socket = new Socket()
      sockets.push(socket)
      return socket
    })
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        job_id: 'job-1', status: 'running', error: null,
        elapsed_s: 4, completed_runs: 2, total_runs: 3,
      }),
    }) as unknown as typeof fetch
    const options = {
      baseUrl: '/api', fetchImpl, getToken: async () => 'token', socketFactory,
      pollMs: 5, reconnectMs: 10,
    }
    const { result } = renderHook(() => useRunEvents('job-1', options))

    await waitFor(() => expect(sockets).toHaveLength(1))
    act(() => sockets[0].open())
    expect(JSON.parse(sockets[0].sent[0])).toEqual({ token: 'token' })
    act(() => sockets[0].message({
      type: 'progress', job_id: 'job-1', status: 'running', error: null,
      elapsed_s: 2, completed_runs: 1, total_runs: 3,
    }))
    expect(result.current.event?.completed_runs).toBe(1)

    act(() => sockets[0].disconnect())
    await waitFor(() => expect(result.current.transport).toBe('polling'))
    await waitFor(() => expect(fetchImpl).toHaveBeenCalled())
    await waitFor(() => expect(result.current.event?.completed_runs).toBe(2))
    await waitFor(() => expect(sockets).toHaveLength(2))
    act(() => sockets[1].open())
    await waitFor(() => expect(result.current.transport).toBe('websocket'))
    act(() => sockets[1].message({
      type: 'progress', job_id: 'job-1', status: 'done', error: null,
      elapsed_s: 9, completed_runs: 3, total_runs: 3,
    }))
    expect(result.current.event?.status).toBe('done')
    expect(result.current.transport).toBe('stopped')
  })

  it('uses polling when WebSocket construction fails', async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        job_id: 'job-2', status: 'done', error: null,
        elapsed_s: 5, completed_runs: 3, total_runs: 3,
      }),
    }) as unknown as typeof fetch
    const options = {
      baseUrl: '/api', fetchImpl, getToken: async () => 'token', pollMs: 5, reconnectMs: 20,
      socketFactory: () => { throw new Error('unavailable') },
    }
    const { result } = renderHook(() => useRunEvents('job-2', options))
    await waitFor(() => expect(result.current.event?.status).toBe('done'))
    expect(fetchImpl).toHaveBeenCalledOnce()
    expect(result.current.transport).toBe('stopped')
  })
})

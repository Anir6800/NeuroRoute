import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../../config'
import { getIdToken } from '../../lib/session'

export type RunStatus = 'queued' | 'running' | 'cancelled' | 'failed' | 'done'
export interface RunProgress {
  type: 'progress'
  job_id: string
  status: RunStatus
  error: string | null
  elapsed_s: number
  completed_runs: number
  total_runs: number
}
export type RunTransport = 'connecting' | 'websocket' | 'polling' | 'stopped'

interface SocketLike {
  onopen: ((event: Event) => void) | null
  onmessage: ((event: MessageEvent<string>) => void) | null
  onclose: ((event: CloseEvent) => void) | null
  onerror: ((event: Event) => void) | null
  send(data: string): void
  close(): void
}

interface Options {
  baseUrl?: string
  fetchImpl?: typeof fetch
  getToken?: () => Promise<string | null>
  socketFactory?: (url: string) => SocketLike
  pollMs?: number
  reconnectMs?: number
}

const terminal = (status: RunStatus) => ['cancelled', 'failed', 'done'].includes(status)
const defaultSocketFactory = (url: string): SocketLike => new WebSocket(url)

export function useRunEvents(jobId: string | null, options: Options = {}) {
  const [event, setEvent] = useState<RunProgress | null>(null)
  const [transport, setTransport] = useState<RunTransport>(jobId ? 'connecting' : 'stopped')
  const [error, setError] = useState<string | null>(null)
  const baseUrl = options.baseUrl ?? API_BASE_URL
  const fetchImpl = options.fetchImpl ?? fetch
  const tokenProvider = options.getToken ?? getIdToken
  const socketFactory = options.socketFactory ?? defaultSocketFactory
  const pollMs = options.pollMs ?? 1000
  const reconnectMs = options.reconnectMs ?? 2000

  useEffect(() => {
    if (!jobId) return
    let active = true
    let socket: SocketLike | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let lastEvent: RunProgress | null = null

    const stop = () => {
      if (pollTimer) clearInterval(pollTimer)
      if (reconnectTimer) clearTimeout(reconnectTimer)
      pollTimer = null
      reconnectTimer = null
    }
    const update = (next: RunProgress) => {
      lastEvent = next
      setEvent(next)
      setError(next.error)
      if (terminal(next.status)) {
        stop()
        setTransport('stopped')
        socket?.close()
      }
    }
    const poll = async () => {
      const token = await tokenProvider()
      if (!active || !token) return
      try {
        const response = await fetchImpl(`${baseUrl}/experiments/${jobId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const body = (await response.json()) as Omit<RunProgress, 'type'>
        update({ type: 'progress', ...body })
      } catch {
        if (active) setError('Training status unavailable')
      }
    }
    const startFallback = () => {
      if (!active || terminal(lastEvent?.status ?? 'running')) return
      setTransport('polling')
      void poll()
      if (!pollTimer) pollTimer = setInterval(() => void poll(), pollMs)
      if (!reconnectTimer) reconnectTimer = setTimeout(connect, reconnectMs)
    }
    const connect = async () => {
      reconnectTimer = null
      const token = await tokenProvider()
      if (!active || !token) {
        startFallback()
        return
      }
      try {
        const url = new URL(`${baseUrl}/events/experiments/${jobId}`, window.location.href)
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
        socket = socketFactory(url.toString())
        socket.onopen = () => {
          if (pollTimer) clearInterval(pollTimer)
          pollTimer = null
          setTransport('websocket')
          socket?.send(JSON.stringify({ token }))
        }
        socket.onmessage = ({ data }) => {
          try {
            const next = JSON.parse(data) as RunProgress
            if (next.type === 'progress') update(next)
          } catch { /* ignore malformed server events */ }
        }
        socket.onerror = () => socket?.close()
        socket.onclose = startFallback
      } catch {
        startFallback()
      }
    }

    const begin = async () => {
      await Promise.resolve()
      if (!active) return
      setEvent(null)
      setTransport('connecting')
      setError(null)
      await connect()
    }
    void begin()
    return () => {
      active = false
      stop()
      socket?.close()
    }
  }, [jobId, baseUrl, fetchImpl, tokenProvider, socketFactory, pollMs, reconnectMs])

  return jobId ? { event, transport, error } : { event: null, transport: 'stopped' as const, error: null }
}

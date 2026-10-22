import { API_BASE_URL } from '../../config'
import { gridPosition, toRequest, type NodeKind, type TopologyDoc } from './model'

export interface Reason {
  code: string
  message: string
  path?: string | null
}

export interface TopologySummary {
  id: string
  name: string
  version: number
  n_nodes: number
  n_links: number
  updated_at: string
}

export type ApiError =
  | { ok: false; kind: 'unauthorized' | 'forbidden' | 'not_found' | 'unavailable' | 'network' | 'bad_response'; message: string }
  | { ok: false; kind: 'invalid'; message: string; reasons: Reason[] }
  | { ok: false; kind: 'conflict'; message: string; currentVersion: number | null }

export type ApiResult<T> = { ok: true; data: T } | ApiError

export interface TopologyApi {
  list(): Promise<ApiResult<TopologySummary[]>>
  get(id: string): Promise<ApiResult<TopologyDoc>>
  /** POST when the document has no id yet, otherwise PUT with its version. */
  save(doc: TopologyDoc): Promise<ApiResult<TopologyDoc>>
}

export const SAVE_TIMEOUT_MS = 5000

interface Options {
  getToken: () => Promise<string | null>
  fetchImpl?: typeof fetch
  baseUrl?: string
  timeoutMs?: number
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null
const num = (v: unknown, fallback: number) => (typeof v === 'number' && Number.isFinite(v) ? v : fallback)

/** Strict about the shape we rely on; a surprising response becomes `bad_response`, never a crash. */
export function parseDoc(body: unknown): TopologyDoc | null {
  if (!isObj(body) || typeof body.id !== 'string' || typeof body.version !== 'number' || typeof body.name !== 'string') return null
  if (!Array.isArray(body.nodes) || !Array.isArray(body.links)) return null
  const nodes: TopologyDoc['nodes'] = []
  for (const [i, n] of body.nodes.entries()) {
    if (!isObj(n) || typeof n.id !== 'string') return null
    const kind: NodeKind = n.kind === 'host' ? 'host' : 'router'
    const fallback = gridPosition(i) // topologies saved without positions get a grid
    nodes.push({ id: n.id, kind, x: num(n.x, fallback.x), y: num(n.y, fallback.y) })
  }
  const links: TopologyDoc['links'] = []
  for (const l of body.links) {
    if (!isObj(l) || typeof l.id !== 'string' || typeof l.source !== 'string' || typeof l.target !== 'string') return null
    links.push({
      id: l.id, source: l.source, target: l.target,
      capacity_mbps: num(l.capacity_mbps, 0), prop_delay_ms: num(l.prop_delay_ms, 0), buffer_pkts: num(l.buffer_pkts, 0), weight: num(l.weight, 1),
    })
  }
  return { id: body.id, version: body.version, name: body.name, nodes, links }
}

function parseSummaries(body: unknown): TopologySummary[] | null {
  if (!isObj(body) || !Array.isArray(body.items)) return null
  const out: TopologySummary[] = []
  for (const it of body.items) {
    if (!isObj(it) || typeof it.id !== 'string' || typeof it.name !== 'string' || typeof it.version !== 'number') return null
    out.push({ id: it.id, name: it.name, version: it.version, n_nodes: num(it.n_nodes, 0), n_links: num(it.n_links, 0), updated_at: String(it.updated_at ?? '') })
  }
  return out
}

function detailOf(body: unknown): Record<string, unknown> | null {
  return isObj(body) && isObj(body.detail) ? body.detail : null
}

export function createTopologyApi({ getToken, fetchImpl = fetch, baseUrl = API_BASE_URL, timeoutMs = SAVE_TIMEOUT_MS }: Options): TopologyApi {
  async function call<T>(path: string, init: RequestInit, parse: (body: unknown) => T | null): Promise<ApiResult<T>> {
    const token = await getToken()
    if (!token) return { ok: false, kind: 'unauthorized', message: 'You are not signed in.' }
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const res = await fetchImpl(`${baseUrl}${path}`, {
        ...init,
        headers: { Authorization: `Bearer ${token}`, ...(init.body ? { 'Content-Type': 'application/json' } : {}) },
        signal: controller.signal,
      })
      let body: unknown = null
      try {
        body = await res.json()
      } catch {
        // an empty or non-JSON body; judged by status below
      }
      if (res.ok) {
        const data = parse(body)
        return data === null ? { ok: false, kind: 'bad_response', message: 'The server answered with an unexpected shape.' } : { ok: true, data }
      }
      const detail = detailOf(body)
      switch (res.status) {
        case 400: {
          const reasons = Array.isArray(detail?.reasons) ? (detail.reasons as Reason[]).filter((r) => isObj(r) && typeof r.code === 'string') : []
          return { ok: false, kind: 'invalid', message: 'The server rejected this topology.', reasons }
        }
        case 401: return { ok: false, kind: 'unauthorized', message: 'Your session is not valid. Sign in again.' }
        case 403: return { ok: false, kind: 'forbidden', message: 'This account is not allowed to use topologies.' }
        case 404: return { ok: false, kind: 'not_found', message: 'That topology no longer exists.' }
        case 409: return { ok: false, kind: 'conflict', message: 'The topology was changed elsewhere.', currentVersion: typeof detail?.current_version === 'number' ? detail.current_version : null }
        case 422: return { ok: false, kind: 'bad_response', message: 'The server could not read the request (422).' }
        default: return { ok: false, kind: 'unavailable', message: `The server answered HTTP ${res.status}.` }
      }
    } catch (e) {
      const timedOut = e instanceof DOMException && e.name === 'AbortError'
      return { ok: false, kind: 'network', message: timedOut ? `No answer after ${timeoutMs} ms.` : 'The backend is unreachable.' }
    } finally {
      clearTimeout(timer)
    }
  }

  return {
    list: () => call('/topologies?limit=100', { method: 'GET' }, parseSummaries),
    get: (id) => call(`/topologies/${encodeURIComponent(id)}`, { method: 'GET' }, parseDoc),
    save: (doc) =>
      doc.id === null
        ? call('/topologies', { method: 'POST', body: JSON.stringify(toRequest(doc)) }, parseDoc)
        : call(`/topologies/${encodeURIComponent(doc.id)}`, { method: 'PUT', body: JSON.stringify({ ...toRequest(doc), version: doc.version }) }, parseDoc),
  }
}

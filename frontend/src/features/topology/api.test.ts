import { describe, expect, it, vi } from 'vitest'
import { createTopologyApi, parseDoc } from './api'
import { addNode, EMPTY_DOC, moveNode, type TopologyDoc } from './model'

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const server = {
  id: 'abc', version: 3, name: 'net', created_at: 'x', updated_at: 'y', content_hash: 'h', schema_version: '1.0',
  nodes: [{ id: 'r1', kind: 'router', x: 1.5, y: 2 }, { id: 'h1', kind: 'host', x: null, y: null }],
  links: [{ id: 'r1-h1', source: 'r1', target: 'h1', capacity_mbps: 10, prop_delay_ms: 2, buffer_pkts: 5, weight: 1 }],
}

function api(fetchImpl: typeof fetch, token: string | null = 'tok', timeoutMs = 50) {
  return createTopologyApi({ getToken: async () => token, fetchImpl, baseUrl: '/api', timeoutMs })
}
const doc = (over: Partial<TopologyDoc> = {}): TopologyDoc => ({ ...moveNode(addNode(addNode(EMPTY_DOC, 'router').doc, 'host').doc, 'r1', 10.04, 20), name: ' net ', ...over })

describe('requests', () => {
  it('creates with POST when the document has no id, sending the bearer token and rounded positions', async () => {
    const f = vi.fn().mockResolvedValue(json(201, server))
    const r = await api(f).save(doc())
    expect(r.ok).toBe(true)
    const [url, init] = f.mock.calls[0]
    expect(url).toBe('/api/topologies')
    expect(init.method).toBe('POST')
    expect(init.headers).toMatchObject({ Authorization: 'Bearer tok', 'Content-Type': 'application/json' })
    const body = JSON.parse(init.body)
    expect(body.name).toBe('net')
    expect(body.nodes[0]).toEqual({ id: 'r1', kind: 'router', x: 10, y: 20 })
    expect('version' in body).toBe(false)
  })

  it('updates with PUT and the version it is based on', async () => {
    const f = vi.fn().mockResolvedValue(json(200, server))
    await api(f).save(doc({ id: 'a/b', version: 7 }))
    const [url, init] = f.mock.calls[0]
    expect(url).toBe('/api/topologies/a%2Fb')
    expect(init.method).toBe('PUT')
    expect(JSON.parse(init.body).version).toBe(7)
  })

  it('lists with a page size and gets by id', async () => {
    const f = vi.fn().mockResolvedValueOnce(json(200, { items: [{ id: 'abc', name: 'net', version: 3, n_nodes: 2, n_links: 1, updated_at: 'y' }], total: 1 })).mockResolvedValueOnce(json(200, server))
    const a = api(f)
    expect(await a.list()).toEqual({ ok: true, data: [{ id: 'abc', name: 'net', version: 3, n_nodes: 2, n_links: 1, updated_at: 'y' }] })
    expect((await a.get('abc')).ok).toBe(true)
    expect(f.mock.calls[0][0]).toBe('/api/topologies?limit=100')
    expect(f.mock.calls[1][0]).toBe('/api/topologies/abc')
  })

  it('does not call the network without a token', async () => {
    const f = vi.fn()
    expect(await api(f, null).list()).toMatchObject({ ok: false, kind: 'unauthorized' })
    expect(f).not.toHaveBeenCalled()
  })
})

describe('responses', () => {
  it('parses a server document, giving grid positions to nodes saved without any', () => {
    const d = parseDoc(server) as TopologyDoc
    expect(d).toMatchObject({ id: 'abc', version: 3, name: 'net' })
    expect(d.nodes[0]).toEqual({ id: 'r1', kind: 'router', x: 1.5, y: 2 })
    expect(d.nodes[1]).toMatchObject({ id: 'h1', kind: 'host', x: 180, y: 0 })
  })

  it.each([
    [400, { detail: { code: 'invalid_topology', reasons: [{ code: 'self_loop', message: 'm', path: 'links[0]' }, 'junk'] } }, { kind: 'invalid', reasons: [{ code: 'self_loop', message: 'm', path: 'links[0]' }] }],
    [401, { detail: 'Invalid token' }, { kind: 'unauthorized' }],
    [403, { detail: 'Role not permitted' }, { kind: 'forbidden' }],
    [404, { detail: { code: 'topology_not_found' } }, { kind: 'not_found' }],
    [409, { detail: { code: 'version_conflict', current_version: 5 } }, { kind: 'conflict', currentVersion: 5 }],
    [409, { detail: 'odd' }, { kind: 'conflict', currentVersion: null }],
    [422, { detail: [] }, { kind: 'bad_response' }],
    [503, { detail: { code: 'storage_unavailable' } }, { kind: 'unavailable' }],
    [500, null, { kind: 'unavailable' }],
  ])('maps HTTP %i to a typed error', async (status, body, expected) => {
    const r = await api(vi.fn().mockResolvedValue(json(status, body))).get('abc')
    expect(r).toMatchObject({ ok: false, ...expected })
  })

  it('treats a 200 with the wrong shape as a bad response, not a crash', async () => {
    for (const body of [{}, null, [], { id: 'a', version: 1, name: 'n', nodes: [{}], links: [] }, { id: 'a', version: '1', name: 'n', nodes: [], links: [] }]) {
      expect(await api(vi.fn().mockResolvedValue(json(200, body))).get('a')).toMatchObject({ ok: false, kind: 'bad_response' })
    }
    expect(await api(vi.fn().mockResolvedValue(new Response('not json', { status: 200 }))).list()).toMatchObject({ ok: false, kind: 'bad_response' })
  })

  it('reports an unreachable backend and a timeout without throwing', async () => {
    expect(await api(vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))).list()).toMatchObject({ ok: false, kind: 'network', message: 'The backend is unreachable.' })
    const hang = vi.fn((_: unknown, init?: RequestInit) => new Promise((_res, rej) => init?.signal?.addEventListener('abort', () => rej(new DOMException('x', 'AbortError')))))
    expect(await api(hang as unknown as typeof fetch, 'tok', 20).list()).toMatchObject({ ok: false, kind: 'network', message: 'No answer after 20 ms.' })
  })
})

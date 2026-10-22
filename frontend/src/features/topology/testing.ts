/** Test support only: jsdom stubs React Flow needs, and an in-memory stand-in for the topology API. */
import type { ApiResult, Reason, TopologyApi, TopologySummary } from './api'
import { toRequest, type TopologyDoc } from './model'

export function stubReactFlowEnvironment(): void {
  class FakeResizeObserver {
    private cb: ResizeObserverCallback
    constructor(cb: ResizeObserverCallback) {
      this.cb = cb
    }
    observe(target: Element) {
      // like the real observer: report after layout, never synchronously inside observe()
      setTimeout(() => this.cb([{ target, contentRect: { width: 900, height: 600 } } as unknown as ResizeObserverEntry], this as unknown as ResizeObserver), 0)
    }
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = FakeResizeObserver as unknown as typeof ResizeObserver
  globalThis.DOMMatrixReadOnly = class {
    m22 = 1
  } as unknown as typeof DOMMatrixReadOnly
  Object.defineProperties(HTMLElement.prototype, {
    offsetHeight: { configurable: true, get: () => 40 },
    offsetWidth: { configurable: true, get: () => 90 },
  })
  ;(SVGElement.prototype as unknown as { getBBox: () => DOMRect }).getBBox = () => ({ x: 0, y: 0, width: 90, height: 40 }) as DOMRect
}

type Failure = Extract<ApiResult<never>, { ok: false }>

/** Behaves like the real server: ids, versions starting at 1, a stale version is a conflict. Counts calls. */
export class FakeApi implements TopologyApi {
  rows = new Map<string, TopologyDoc>()
  calls = { list: 0, get: 0, save: 0 }
  failNext: { list?: Failure; get?: Failure; save?: Failure } = {}
  /** Reasons to answer the next save with (as a 400). */
  rejectNextSave: Reason[] | null = null
  private n = 0

  async list(): Promise<ApiResult<TopologySummary[]>> {
    this.calls.list += 1
    const f = this.failNext.list
    if (f) {
      this.failNext.list = undefined
      return f
    }
    return {
      ok: true,
      data: [...this.rows.values()].map((d) => ({
        id: d.id as string, name: d.name, version: d.version as number, n_nodes: d.nodes.length, n_links: d.links.length, updated_at: 'now',
      })),
    }
  }

  async get(id: string): Promise<ApiResult<TopologyDoc>> {
    this.calls.get += 1
    const f = this.failNext.get
    if (f) {
      this.failNext.get = undefined
      return f
    }
    const d = this.rows.get(id)
    return d ? { ok: true, data: structuredClone(d) } : { ok: false, kind: 'not_found', message: 'That topology no longer exists.' }
  }

  async save(doc: TopologyDoc): Promise<ApiResult<TopologyDoc>> {
    this.calls.save += 1
    const f = this.failNext.save
    if (f) {
      this.failNext.save = undefined
      return f
    }
    if (this.rejectNextSave) {
      const reasons = this.rejectNextSave
      this.rejectNextSave = null
      return { ok: false, kind: 'invalid', message: 'The server rejected this topology.', reasons }
    }
    const body = toRequest(doc)
    if (doc.id === null) {
      const id = `t${++this.n}`
      const stored: TopologyDoc = { id, version: 1, name: body.name, nodes: body.nodes, links: body.links }
      this.rows.set(id, stored)
      return { ok: true, data: structuredClone(stored) }
    }
    const current = this.rows.get(doc.id)
    if (!current) return { ok: false, kind: 'not_found', message: 'That topology no longer exists.' }
    if (current.version !== doc.version) return { ok: false, kind: 'conflict', message: 'The topology was changed elsewhere.', currentVersion: current.version }
    const stored: TopologyDoc = { id: doc.id, version: (current.version as number) + 1, name: body.name, nodes: body.nodes, links: body.links }
    this.rows.set(doc.id, stored)
    return { ok: true, data: structuredClone(stored) }
  }
}

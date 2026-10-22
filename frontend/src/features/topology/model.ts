/** The editor's document and the pure operations on it. No React, no network: everything here is unit-tested. */

export type NodeKind = 'router' | 'host'

export interface TopoNode {
  id: string
  kind: NodeKind
  x: number
  y: number
}

export interface TopoLink {
  id: string
  source: string
  target: string
  capacity_mbps: number
  prop_delay_ms: number
  buffer_pkts: number
  weight: number
}

export interface TopologyDoc {
  /** Server id; null until the first save. */
  id: string | null
  /** Server version this document is based on; null until the first save. */
  version: number | null
  name: string
  nodes: TopoNode[]
  links: TopoLink[]
}

/** Same rule as the backend (`research.simulation.models.Ident`). */
export const ID_PATTERN = /^[A-Za-z0-9_-]{1,32}$/
export const NAME_MAX = 64
export const LINK_DEFAULTS = { capacity_mbps: 100, prop_delay_ms: 1, buffer_pkts: 50, weight: 1 } as const

export const EMPTY_DOC: TopologyDoc = { id: null, version: null, name: 'Untitled topology', nodes: [], links: [] }

const GRID = { columns: 3, dx: 180, dy: 120 }

export function gridPosition(index: number): { x: number; y: number } {
  return { x: (index % GRID.columns) * GRID.dx, y: Math.floor(index / GRID.columns) * GRID.dy }
}

/** First unused `r1, r2, ...` (routers) or `h1, h2, ...` (hosts). */
export function nextNodeId(doc: TopologyDoc, kind: NodeKind): string {
  const prefix = kind === 'router' ? 'r' : 'h'
  const used = new Set(doc.nodes.map((n) => n.id))
  for (let i = 1; ; i++) if (!used.has(`${prefix}${i}`)) return `${prefix}${i}`
}

export function addNode(doc: TopologyDoc, kind: NodeKind): { doc: TopologyDoc; id: string } {
  const id = nextNodeId(doc, kind)
  return { doc: { ...doc, nodes: [...doc.nodes, { id, kind, ...gridPosition(doc.nodes.length) }] }, id }
}

export function moveNode(doc: TopologyDoc, id: string, x: number, y: number): TopologyDoc {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return doc
  return { ...doc, nodes: doc.nodes.map((n) => (n.id === id ? { ...n, x, y } : n)) }
}

export function setNodeKind(doc: TopologyDoc, id: string, kind: NodeKind): TopologyDoc {
  return { ...doc, nodes: doc.nodes.map((n) => (n.id === id ? { ...n, kind } : n)) }
}

export type RenameResult = { ok: true; doc: TopologyDoc } | { ok: false; error: string }

/** Rename a node and every link end that points at it. Link ids are left alone. */
export function renameNode(doc: TopologyDoc, oldId: string, newId: string): RenameResult {
  if (oldId === newId) return { ok: true, doc }
  if (!ID_PATTERN.test(newId)) return { ok: false, error: 'Use 1-32 letters, digits, "_" or "-".' }
  if (doc.nodes.some((n) => n.id === newId)) return { ok: false, error: `A node called "${newId}" already exists.` }
  return {
    ok: true,
    doc: {
      ...doc,
      nodes: doc.nodes.map((n) => (n.id === oldId ? { ...n, id: newId } : n)),
      links: doc.links.map((l) => ({
        ...l,
        source: l.source === oldId ? newId : l.source,
        target: l.target === oldId ? newId : l.target,
      })),
    },
  }
}

/** Remove nodes together with every link that touches them. */
export function removeNodes(doc: TopologyDoc, ids: readonly string[]): TopologyDoc {
  const gone = new Set(ids)
  return {
    ...doc,
    nodes: doc.nodes.filter((n) => !gone.has(n.id)),
    links: doc.links.filter((l) => !gone.has(l.source) && !gone.has(l.target)),
  }
}

export function removeLinks(doc: TopologyDoc, ids: readonly string[]): TopologyDoc {
  const gone = new Set(ids)
  return { ...doc, links: doc.links.filter((l) => !gone.has(l.id)) }
}

/** `a-b`, or `a-b-2`, `a-b-3`... when taken; always a valid id (at most 32 characters). */
export function makeLinkId(doc: TopologyDoc, source: string, target: string): string {
  const used = new Set(doc.links.map((l) => l.id))
  const base = `${source}-${target}`.slice(0, 32)
  if (!used.has(base) && ID_PATTERN.test(base)) return base
  for (let i = 2; ; i++) {
    const suffix = `-${i}`
    const candidate = `${base.slice(0, 32 - suffix.length)}${suffix}`
    if (!used.has(candidate)) return candidate
  }
}

export type AddLinkResult = { ok: true; doc: TopologyDoc; id: string } | { ok: false; error: string }

export function addLink(doc: TopologyDoc, source: string, target: string): AddLinkResult {
  if (!doc.nodes.some((n) => n.id === source) || !doc.nodes.some((n) => n.id === target)) {
    return { ok: false, error: 'Both ends must be existing nodes.' }
  }
  if (source === target) return { ok: false, error: 'A link cannot start and end on the same node.' }
  const twin = doc.links.find((l) => l.source === source && l.target === target)
  if (twin) return { ok: false, error: `${source} -> ${target} already exists (link "${twin.id}").` }
  const id = makeLinkId(doc, source, target)
  return { ok: true, id, doc: { ...doc, links: [...doc.links, { id, source, target, ...LINK_DEFAULTS }] } }
}

export type LinkPatch = Partial<Pick<TopoLink, 'capacity_mbps' | 'prop_delay_ms' | 'buffer_pkts' | 'weight'>>

/** Values are stored as typed (even non-positive ones) so that validation can point at them. */
export function updateLink(doc: TopologyDoc, id: string, patch: LinkPatch): TopologyDoc {
  return { ...doc, links: doc.links.map((l) => (l.id === id ? { ...l, ...patch } : l)) }
}

/** Six routers in a ring plus one chord (r1-r4), every cable as two directed links. For a quick start; not a benchmark. */
export function sixRouterExample(): TopologyDoc {
  let doc: TopologyDoc = { ...EMPTY_DOC, name: 'Six-router ring' }
  const radius = 170
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI * 2 * i) / 6 - Math.PI / 2
    doc = {
      ...doc,
      nodes: [...doc.nodes, { id: `r${i + 1}`, kind: 'router', x: Math.round(radius * Math.cos(angle)), y: Math.round(radius * Math.sin(angle)) }],
    }
  }
  const cables: [string, string][] = [['r1', 'r2'], ['r2', 'r3'], ['r3', 'r4'], ['r4', 'r5'], ['r5', 'r6'], ['r6', 'r1'], ['r1', 'r4']]
  for (const [a, b] of cables) {
    for (const [s, t] of [[a, b], [b, a]] as const) {
      const added = addLink(doc, s, t)
      if (added.ok) doc = added.doc
    }
  }
  return doc
}

const round1 = (v: number) => Math.round(v * 10) / 10

/** The JSON the API expects. Positions are rounded so a drag does not create noise in the stored file. */
export function toRequest(doc: TopologyDoc) {
  return {
    name: doc.name.trim(),
    nodes: doc.nodes.map((n) => ({ id: n.id, kind: n.kind, x: round1(n.x), y: round1(n.y) })),
    links: doc.links.map((l) => ({ ...l })),
  }
}

/** What counts as "unsaved": everything the user can change, rounded the same way as on save. */
export function docKey(doc: TopologyDoc): string {
  return JSON.stringify(toRequest(doc))
}

export function isDirty(doc: TopologyDoc, savedKey: string): boolean {
  return docKey(doc) !== savedKey
}

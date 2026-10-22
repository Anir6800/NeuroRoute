/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  addLink,
  addNode,
  docKey,
  EMPTY_DOC,
  isDirty,
  makeLinkId,
  moveNode,
  nextNodeId,
  removeLinks,
  removeNodes,
  renameNode,
  sixRouterExample,
  toRequest,
  updateLink,
  type TopologyDoc,
} from './model'
import { components, issuesFromReasons, validateDoc } from './validate'

function withNodes(n: number): TopologyDoc {
  let doc = EMPTY_DOC
  for (let i = 0; i < n; i++) doc = addNode(doc, 'router').doc
  return doc
}
const codes = (doc: TopologyDoc) => validateDoc(doc).map((i) => i.code)
const must = <T extends { ok: boolean }>(r: T): Extract<T, { ok: true }> => {
  expect(r.ok).toBe(true)
  return r as Extract<T, { ok: true }>
}

describe('nodes', () => {
  it('numbers routers and hosts separately and reuses the first free number', () => {
    let doc = addNode(EMPTY_DOC, 'router').doc
    doc = addNode(doc, 'host').doc
    doc = addNode(doc, 'router').doc
    expect(doc.nodes.map((n) => n.id)).toEqual(['r1', 'h1', 'r2'])
    doc = removeNodes(doc, ['r1'])
    expect(nextNodeId(doc, 'router')).toBe('r1')
  })

  it('places new nodes on a grid without overlap', () => {
    const doc = withNodes(7)
    const spots = new Set(doc.nodes.map((n) => `${n.x},${n.y}`))
    expect(spots.size).toBe(7)
  })

  it('ignores a move to a non-finite position', () => {
    const doc = withNodes(1)
    expect(moveNode(doc, 'r1', Number.NaN, 5)).toBe(doc)
    expect(moveNode(doc, 'r1', 10, 20).nodes[0]).toMatchObject({ x: 10, y: 20 })
  })

  it('renames a node and the link ends that use it, and refuses bad or taken names', () => {
    let doc = withNodes(2)
    doc = must(addLink(doc, 'r1', 'r2')).doc
    const renamed = must(renameNode(doc, 'r1', 'core')).doc
    expect(renamed.nodes.map((n) => n.id)).toEqual(['core', 'r2'])
    expect(renamed.links[0]).toMatchObject({ source: 'core', target: 'r2', id: 'r1-r2' })
    expect(renameNode(doc, 'r1', 'r2')).toMatchObject({ ok: false })
    for (const bad of ['', 'has space', 'x'.repeat(33), 'a/b']) expect(renameNode(doc, 'r1', bad)).toMatchObject({ ok: false })
    expect(renameNode(doc, 'r1', 'r1')).toEqual({ ok: true, doc })
  })

  it('deleting a node deletes the links attached to it', () => {
    const doc = sixRouterExample()
    const after = removeNodes(doc, ['r1'])
    expect(after.nodes).toHaveLength(5)
    expect(after.links.every((l) => l.source !== 'r1' && l.target !== 'r1')).toBe(true)
    expect(after.links).toHaveLength(doc.links.length - doc.links.filter((l) => l.source === 'r1' || l.target === 'r1').length)
  })
})

describe('links', () => {
  it('adds a directed link with defaults and refuses self-loops, repeats and unknown ends', () => {
    const doc = withNodes(3)
    const first = must(addLink(doc, 'r1', 'r2'))
    expect(first.id).toBe('r1-r2')
    expect(first.doc.links[0]).toMatchObject({ capacity_mbps: 100, prop_delay_ms: 1, buffer_pkts: 50, weight: 1 })
    expect(addLink(first.doc, 'r1', 'r1')).toMatchObject({ ok: false })
    expect(addLink(first.doc, 'r1', 'r2')).toMatchObject({ ok: false, error: expect.stringContaining('already exists') })
    expect(addLink(first.doc, 'r1', 'ghost')).toMatchObject({ ok: false })
    expect(addLink(first.doc, 'r2', 'r1')).toMatchObject({ ok: true }) // the other direction is a different link
  })

  it('always produces a valid, unused link id, even for long node names', () => {
    const a = 'a'.repeat(32)
    const b = 'b'.repeat(32)
    let doc: TopologyDoc = { ...EMPTY_DOC, nodes: [a, b].map((id, i) => ({ id, kind: 'router' as const, x: i, y: 0 })) }
    doc = must(addLink(doc, a, b)).doc
    expect(doc.links[0].id).toHaveLength(32)
    const next = makeLinkId(doc, a, b)
    expect(next).toHaveLength(32)
    expect(next).not.toBe(doc.links[0].id)
    expect(next).toMatch(/^[A-Za-z0-9_-]{1,32}$/)
  })

  it('updates only the chosen link and removes links by id', () => {
    let doc = withNodes(2)
    doc = must(addLink(doc, 'r1', 'r2')).doc
    doc = must(addLink(doc, 'r2', 'r1')).doc
    const edited = updateLink(doc, 'r1-r2', { capacity_mbps: 5 })
    expect(edited.links.map((l) => l.capacity_mbps)).toEqual([5, 100])
    expect(removeLinks(edited, ['r1-r2']).links.map((l) => l.id)).toEqual(['r2-r1'])
  })
})

describe('six-router example', () => {
  it('has six routers, a ring plus one chord as 14 directed links, and passes validation', () => {
    const doc = sixRouterExample()
    expect(doc.nodes.map((n) => n.id)).toEqual(['r1', 'r2', 'r3', 'r4', 'r5', 'r6'])
    expect(doc.nodes.every((n) => n.kind === 'router')).toBe(true)
    expect(doc.links).toHaveLength(14)
    expect(codes(doc)).toEqual([])
    expect(components(doc)).toEqual([['r1', 'r2', 'r3', 'r4', 'r5', 'r6']])
    expect(new Set(doc.nodes.map((n) => `${n.x},${n.y}`)).size).toBe(6)
  })
})

describe('request and dirty tracking', () => {
  it('rounds positions to 0.1 and trims the name', () => {
    const doc: TopologyDoc = { ...withNodes(1), name: '  net  ' }
    const moved = moveNode(doc, 'r1', 10.04, -3.06)
    expect(toRequest(moved)).toMatchObject({ name: 'net', nodes: [{ id: 'r1', kind: 'router', x: 10, y: -3.1 }] })
  })

  it('is dirty after any user-visible change and clean again when it is undone', () => {
    const doc = sixRouterExample()
    const key = docKey(doc)
    expect(isDirty(doc, key)).toBe(false)
    expect(isDirty(moveNode(doc, 'r1', doc.nodes[0].x + 5, doc.nodes[0].y), key)).toBe(true)
    expect(isDirty(updateLink(doc, doc.links[0].id, { weight: 2 }), key)).toBe(true)
    expect(isDirty({ ...doc, name: 'other' }, key)).toBe(true)
    expect(isDirty(moveNode(doc, 'r1', doc.nodes[0].x + 0.01, doc.nodes[0].y), key)).toBe(false) // below the rounding step
    expect(isDirty({ ...doc, id: 'x', version: 4 }, key)).toBe(false) // identity is not content
  })
})

describe('local validation', () => {
  const base = () => sixRouterExample()

  it('reports an empty canvas as too few nodes and links', () => {
    expect(codes(EMPTY_DOC)).toEqual(['too_few_nodes', 'too_few_links'])
  })

  it('flags each numeric rule on the right link', () => {
    for (const [patch, code] of [
      [{ capacity_mbps: 0 }, 'non_positive_capacity'],
      [{ capacity_mbps: -1 }, 'non_positive_capacity'],
      [{ prop_delay_ms: 0 }, 'non_positive_delay'],
      [{ buffer_pkts: 0 }, 'non_positive_buffer'],
      [{ buffer_pkts: 2.5 }, 'non_positive_buffer'],
      [{ weight: -0.5 }, 'negative_weight'],
      [{ capacity_mbps: Number.NaN }, 'non_positive_capacity'],
    ] as const) {
      const doc = updateLink(base(), 'r1-r2', patch)
      const issues = validateDoc(doc)
      expect(issues.map((i) => i.code)).toEqual([code])
      expect(issues[0].ref).toEqual({ kind: 'link', id: 'r1-r2' })
    }
  })

  it('flags disconnected graphs, naming the parts, and ignores link direction', () => {
    const doc = base()
    const island = { ...doc, nodes: [...doc.nodes, { id: 'lonely', kind: 'host' as const, x: 0, y: 0 }] }
    const issues = validateDoc(island)
    expect(issues.map((i) => i.code)).toEqual(['disconnected'])
    expect(issues[0].message).toContain('lonely')
    const oneWay = must(addLink(must(addLink(withNodes(3), 'r1', 'r2')).doc, 'r3', 'r2')).doc
    expect(codes(oneWay)).toEqual([]) // r1 -> r2 <- r3: weakly connected, like the backend
  })

  it('flags self-loops, repeated links, duplicate and malformed ids, and unknown ends', () => {
    const doc = base()
    const link = doc.links[0]
    expect(codes({ ...doc, links: [...doc.links, { ...link, id: 'loop', target: link.source }] })).toEqual(['self_loop'])
    expect(codes({ ...doc, links: [...doc.links, { ...link, id: 'again' }] })).toEqual(['duplicate_link'])
    expect(codes({ ...doc, links: [...doc.links, { ...link, source: 'r2', target: 'r5' }] })).toEqual(['duplicate_link_id'])
    expect(codes({ ...doc, nodes: [...doc.nodes, { ...doc.nodes[0] }] })).toEqual(['duplicate_node_id'])
    expect(codes({ ...doc, nodes: doc.nodes.map((n, i) => (i === 0 ? { ...n, id: 'bad id' } : n)), links: [] }).includes('invalid_node_id')).toBe(true)
    expect(codes({ ...doc, links: [...doc.links, { ...link, id: 'ghost-link', source: 'ghost' }] })).toEqual(['unknown_endpoint'])
  })

  it('enforces the size limits and stops there', () => {
    const doc = withNodes(5)
    expect(validateDoc(doc, { maxNodes: 4, maxLinks: 10 }).map((i) => i.code)).toEqual(['too_many_nodes'])
  })

  it('requires a name of 1 to 64 characters', () => {
    expect(codes({ ...base(), name: '   ' })).toEqual(['invalid_name'])
    expect(codes({ ...base(), name: 'x'.repeat(65) })).toEqual(['invalid_name'])
  })

  it('every reason code the backend can return is also checked locally (drift guard)', () => {
    const backendRules = readFileSync(resolve(import.meta.dirname, '../../../../backend/app/services/topologies.py'), 'utf-8')
    const validateSource = readFileSync(resolve(import.meta.dirname, 'validate.ts'), 'utf-8')
    const backendCodes = new Set([...backendRules.matchAll(/\bbad\(\s*"([a-z_]+)"/g)].map((m) => m[1]))
    const frontendCodes = new Set([...validateSource.matchAll(/\bbad\(\s*'([a-z_]+)'/g)].map((m) => m[1]))
    expect(backendCodes.size).toBeGreaterThanOrEqual(15)
    expect([...backendCodes].filter((c) => !frontendCodes.has(c))).toEqual([])
  })
})

describe('server reasons', () => {
  it('map a path such as links[2].capacity_mbps to the element at that index', () => {
    const doc = sixRouterExample()
    const issues = issuesFromReasons(
      [
        { code: 'non_positive_capacity', message: 'bad', path: 'links[2].capacity_mbps' },
        { code: 'invalid_node_id', message: 'bad', path: 'nodes[1].id' },
        { code: 'disconnected', message: 'bad', path: 'links' },
        { code: 'self_loop', message: 'bad', path: 'links[999]' },
        { code: 'x', message: 'bad' },
      ],
      doc,
    )
    expect(issues.map((i) => i.ref)).toEqual([
      { kind: 'link', id: doc.links[2].id },
      { kind: 'node', id: 'r2' },
      { kind: 'graph' },
      { kind: 'graph' },
      { kind: 'graph' },
    ])
    expect(issues.every((i) => i.origin === 'server')).toBe(true)
  })
})

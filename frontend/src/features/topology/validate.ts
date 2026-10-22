import { ID_PATTERN, NAME_MAX, type TopologyDoc } from './model'

/** Which element a problem is about. `graph` = the topology as a whole. */
export type IssueRef = { kind: 'node'; id: string } | { kind: 'link'; id: string } | { kind: 'graph' }

export interface Issue {
  code: string
  message: string
  ref: IssueRef
  origin: 'local' | 'server'
}

/** Defaults of the backend settings; the server is the authority and may be configured differently. */
export const DEFAULT_LIMITS: { maxNodes: number; maxLinks: number } = { maxNodes: 64, maxLinks: 512 }

/**
 * Instant feedback that mirrors the backend rules and reason codes (docs/topology_api.md). The server still validates
 * every save; a local pass does not mean the server will accept it.
 */
export function validateDoc(doc: TopologyDoc, limits = DEFAULT_LIMITS): Issue[] {
  const out: Issue[] = []
  const bad = (code: string, message: string, ref: IssueRef) => out.push({ code, message, ref, origin: 'local' })

  if (doc.name.trim() === '' || doc.name.trim().length > NAME_MAX) {
    bad('invalid_name', `The name must be 1-${NAME_MAX} characters.`, { kind: 'graph' })
  }
  if (doc.nodes.length > limits.maxNodes) bad('too_many_nodes', `${doc.nodes.length} nodes exceeds the limit of ${limits.maxNodes}.`, { kind: 'graph' })
  if (doc.links.length > limits.maxLinks) bad('too_many_links', `${doc.links.length} links exceeds the limit of ${limits.maxLinks}.`, { kind: 'graph' })
  if (out.some((i) => i.code.startsWith('too_many'))) return out

  if (doc.nodes.length < 2) bad('too_few_nodes', 'A topology needs at least 2 nodes.', { kind: 'graph' })
  if (doc.links.length === 0) bad('too_few_links', 'A topology needs at least 1 link.', { kind: 'graph' })

  const nodeIds = new Set<string>()
  for (const n of doc.nodes) {
    if (!ID_PATTERN.test(n.id)) bad('invalid_node_id', `Node id "${n.id}" must use 1-32 letters, digits, "_" or "-".`, { kind: 'node', id: n.id })
    if (nodeIds.has(n.id)) bad('duplicate_node_id', `Node id "${n.id}" is used more than once.`, { kind: 'node', id: n.id })
    nodeIds.add(n.id)
  }

  const linkIds = new Set<string>()
  const pairs = new Map<string, string>()
  let endpointsOk = true
  for (const l of doc.links) {
    const ref: IssueRef = { kind: 'link', id: l.id }
    if (!ID_PATTERN.test(l.id)) bad('invalid_link_id', `Link id "${l.id}" must use 1-32 letters, digits, "_" or "-".`, ref)
    if (linkIds.has(l.id)) bad('duplicate_link_id', `Link id "${l.id}" is used more than once.`, ref)
    linkIds.add(l.id)
    for (const end of ['source', 'target'] as const) {
      if (!nodeIds.has(l[end])) {
        endpointsOk = false
        bad('unknown_endpoint', `Link "${l.id}": ${end} "${l[end]}" is not a node.`, ref)
      }
    }
    if (l.source === l.target) bad('self_loop', `Link "${l.id}" connects "${l.source}" to itself.`, ref)
    else {
      const key = `${l.source}\u0000${l.target}`
      const first = pairs.get(key)
      if (first === undefined) pairs.set(key, l.id)
      else if (first !== l.id) bad('duplicate_link', `Links "${first}" and "${l.id}" both go ${l.source} -> ${l.target}.`, ref)
    }
    if (!(l.capacity_mbps > 0)) bad('non_positive_capacity', `Link "${l.id}": capacity must be greater than 0.`, ref)
    if (!(l.prop_delay_ms > 0)) bad('non_positive_delay', `Link "${l.id}": delay must be greater than 0.`, ref)
    if (!(l.buffer_pkts > 0) || !Number.isInteger(l.buffer_pkts)) bad('non_positive_buffer', `Link "${l.id}": buffer must be a whole number greater than 0.`, ref)
    if (!(l.weight >= 0)) bad('negative_weight', `Link "${l.id}": weight cannot be negative.`, ref)
  }

  if (endpointsOk && nodeIds.size === doc.nodes.length && doc.nodes.length >= 2) {
    const parts = components(doc)
    if (parts.length > 1) {
      const lone = parts.slice(1).flat().slice(0, 4).join(', ')
      bad('disconnected', `The graph has ${parts.length} separate parts (link direction ignored); not connected to "${parts[0][0]}": ${lone}.`, { kind: 'graph' })
    }
  }
  return out
}

/** Weakly connected components, largest first (link direction ignored, like the backend). */
export function components(doc: TopologyDoc): string[][] {
  const parent = new Map(doc.nodes.map((n) => [n.id, n.id]))
  const find = (x: string): string => {
    let root = x
    while (parent.get(root) !== root) root = parent.get(root) as string
    parent.set(x, root)
    return root
  }
  for (const l of doc.links) {
    if (parent.has(l.source) && parent.has(l.target)) parent.set(find(l.source), find(l.target))
  }
  const groups = new Map<string, string[]>()
  for (const n of doc.nodes) groups.set(find(n.id), [...(groups.get(find(n.id)) ?? []), n.id])
  return [...groups.values()].map((g) => g.sort()).sort((a, b) => b.length - a.length || a[0].localeCompare(b[0]))
}

/** Server reasons carry a path like `links[2].capacity_mbps`; map it to the element at that index of what we sent. */
export function issuesFromReasons(reasons: { code: string; message: string; path?: string | null }[], doc: TopologyDoc): Issue[] {
  return reasons.map((r) => {
    const m = /^(nodes|links)\[(\d+)\]/.exec(r.path ?? '')
    let ref: IssueRef = { kind: 'graph' }
    if (m) {
      const index = Number(m[2])
      if (m[1] === 'nodes' && doc.nodes[index]) ref = { kind: 'node', id: doc.nodes[index].id }
      if (m[1] === 'links' && doc.links[index]) ref = { kind: 'link', id: doc.links[index].id }
    }
    return { code: r.code, message: r.message, ref, origin: 'server' as const }
  })
}

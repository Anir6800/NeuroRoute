import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeChange,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useCallback, useMemo, useState } from 'react'
import { FloatingEdge } from './FloatingEdge'
import type { Issue } from './validate'
import type { NodeKind, TopologyDoc } from './model'

export type Selection = { kind: 'node'; id: string } | { kind: 'link'; id: string }

interface DeviceData extends Record<string, unknown> {
  kind: NodeKind
  invalid: boolean
}
type DeviceNode = Node<DeviceData, 'device'>

/** A router (rounded box) or host (pill). The left handle receives links, the right handle sends them. */
function Device({ id, data }: NodeProps<DeviceNode>) {
  return (
    <div className={`topo-node topo-node--${data.kind}`} data-invalid={data.invalid || undefined}>
      <Handle type="target" position={Position.Left} />
      <span className="topo-node__kind">{data.kind === 'router' ? 'Router' : 'Host'}</span>
      <span className="topo-node__id">{id}</span>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

const nodeTypes = { device: Device }
const edgeTypes = { floating: FloatingEdge }
const DELETE_KEYS = ['Delete', 'Backspace']

type Size = { width: number; height: number }

function buildNodes(doc: TopologyDoc, sizes: Map<string, Size>, selected: Selection | null, flagged: Set<string>): DeviceNode[] {
  return doc.nodes.map((n) => ({
    id: n.id,
    type: 'device',
    position: { x: n.x, y: n.y },
    measured: sizes.get(n.id), // React Flow reports each node's size; without it the node stays hidden
    data: { kind: n.kind, invalid: flagged.has(n.id) },
    selected: selected?.kind === 'node' && selected.id === n.id,
    ariaLabel: `${n.kind === 'router' ? 'Router' : 'Host'} ${n.id}`,
  }))
}

interface Props {
  doc: TopologyDoc
  selected: Selection | null
  issues: Issue[]
  /** Changes when a different topology is loaded, so the view re-fits it. */
  fitKey: string
  onSelect: (selection: Selection | null) => void
  onMoveNode: (id: string, x: number, y: number) => void
  onConnect: (source: string, target: string) => void
  onDelete: (removed: { nodes: string[]; links: string[] }) => void
}

/**
 * Controlled canvas: `doc` is the single source of truth. Dragging reports positions, connecting a handle pair reports a link,
 * Delete/Backspace reports removals; none of it changes anything until the parent updates `doc`.
 */
export function TopologyCanvas({ doc, selected, issues, fitKey, onSelect, onMoveNode, onConnect, onDelete }: Props) {
  const flaggedNodes = useMemo(() => new Set(issues.flatMap((i) => (i.ref.kind === 'node' ? [i.ref.id] : []))), [issues])
  const flaggedLinks = useMemo(() => new Set(issues.flatMap((i) => (i.ref.kind === 'link' ? [i.ref.id] : []))), [issues])

  // React Flow measures nodes and reports sizes through onNodesChange; only those sizes live in state, the rest comes from `doc`.
  const [sizes, setSizes] = useState<Map<string, Size>>(() => new Map())
  const nodes = useMemo(() => buildNodes(doc, sizes, selected, flaggedNodes), [doc, sizes, selected, flaggedNodes])

  const edges: Edge[] = useMemo(
    () =>
      doc.links.map((l) => ({
        id: l.id,
        type: 'floating',
        source: l.source,
        target: l.target,
        label: `${l.capacity_mbps} Mbps`,
        markerEnd: { type: MarkerType.ArrowClosed },
        selected: selected?.kind === 'link' && selected.id === l.id,
        className: flaggedLinks.has(l.id) ? 'topo-edge--invalid' : undefined,
        ariaLabel: `Link ${l.id}: ${l.source} to ${l.target}`,
      })),
    [doc.links, selected, flaggedLinks],
  )

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      for (const c of changes) {
        if (c.type === 'position' && c.position) onMoveNode(c.id, c.position.x, c.position.y)
        if (c.type === 'dimensions' && c.dimensions) {
          const { width, height } = c.dimensions
          setSizes((prev) => {
            const old = prev.get(c.id)
            if (old?.width === width && old.height === height) return prev
            return new Map(prev).set(c.id, { width, height })
          })
        }
      }
    },
    [onMoveNode],
  )

  return (
    <div className="topo-canvas" role="group" aria-label="Topology canvas" aria-describedby="topo-canvas-help">
      <p id="topo-canvas-help" className="sr-only">
        Drag a node to move it. Drag from the right dot of one node to the left dot of another to add a link. Select an item and press
        Delete to remove it. You can also add links from the form beside the canvas.
      </p>
      <ReactFlow
        key={fitKey}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_, n) => onSelect({ kind: 'node', id: n.id })}
        onEdgeClick={(_, e) => onSelect({ kind: 'link', id: e.id })}
        onPaneClick={() => onSelect(null)}
        onConnect={(c) => onConnect(c.source, c.target)}
        isValidConnection={(c) => c.source !== c.target}
        onDelete={({ nodes: ns, edges: es }) => onDelete({ nodes: ns.map((n) => n.id), links: es.map((e) => e.id) })}
        deleteKeyCode={DELETE_KEYS}
        fitView
        fitViewOptions={{ padding: 0.25, maxZoom: 1.2 }}
        minZoom={0.2}
        maxZoom={2}
        nodesConnectable
        elementsSelectable
      >
        <Background gap={24} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}

import { BaseEdge, getStraightPath, useInternalNode, type EdgeProps, type InternalNode } from '@xyflow/react'
import { edgeEnds, type Box } from './geometry'

function boxOf(node: InternalNode): Box | null {
  const w = node.measured.width
  const h = node.measured.height
  if (!w || !h) return null // not measured yet
  const { x, y } = node.internals.positionAbsolute
  return { cx: x + w / 2, cy: y + h / 2, w, h }
}

/**
 * Edge that runs border to border along the line between the two node centres, shifted sideways by PAIR_OFFSET. The shift flips with
 * the direction, so the two directions of a cable end up on either side of the centre line. Handles are only where a drag starts.
 * (React Flow's own wrapper adds the edge's class, selection state and aria-label.)
 */
export function FloatingEdge({ id, source, target, markerEnd, label, interactionWidth }: EdgeProps) {
  const from = useInternalNode(source)
  const to = useInternalNode(target)
  const a = from && boxOf(from)
  const b = to && boxOf(to)
  if (!a || !b || (a.cx === b.cx && a.cy === b.cy)) return null

  const { sx, sy, tx, ty } = edgeEnds(a, b)
  const [path, labelX, labelY] = getStraightPath({ sourceX: sx, sourceY: sy, targetX: tx, targetY: ty })
  return (
    <BaseEdge
      id={id}
      path={path}
      labelX={labelX}
      labelY={labelY}
      label={label}
      markerEnd={markerEnd}
      interactionWidth={interactionWidth}
    />
  )
}

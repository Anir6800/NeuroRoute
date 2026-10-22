/** Edge geometry kept apart from the component so it can be unit-tested without React Flow. */

/** Gap between the two directions of one cable, so a -> b and b -> a do not draw on top of each other. */
export const PAIR_OFFSET = 7

export interface Box {
  cx: number
  cy: number
  w: number
  h: number
}

/** Where the straight line from this box's centre towards (tx, ty) leaves the box's rectangle. */
export function borderPoint(box: Box, tx: number, ty: number): { x: number; y: number } {
  const dx = tx - box.cx
  const dy = ty - box.cy
  if (dx === 0 && dy === 0) return { x: box.cx, y: box.cy }
  // how far along (dx, dy) each pair of sides is reached; an axis with no movement never reaches its sides
  const scale = Math.min(dx === 0 ? Infinity : box.w / 2 / Math.abs(dx), dy === 0 ? Infinity : box.h / 2 / Math.abs(dy))
  return { x: box.cx + dx * scale, y: box.cy + dy * scale }
}

/** Both ends of the edge a -> b, shifted sideways by PAIR_OFFSET. Reversing a and b shifts to the other side. */
export function edgeEnds(a: Box, b: Box): { sx: number; sy: number; tx: number; ty: number } {
  const start = borderPoint(a, b.cx, b.cy)
  const end = borderPoint(b, a.cx, a.cy)
  const length = Math.hypot(end.x - start.x, end.y - start.y) || 1
  const nx = (-(end.y - start.y) / length) * PAIR_OFFSET
  const ny = ((end.x - start.x) / length) * PAIR_OFFSET
  return { sx: start.x + nx, sy: start.y + ny, tx: end.x + nx, ty: end.y + ny }
}

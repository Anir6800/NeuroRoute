import { describe, expect, it } from 'vitest'
import { borderPoint, edgeEnds, PAIR_OFFSET, type Box } from './geometry'

const box = (cx: number, cy: number, w = 100, h = 40): Box => ({ cx, cy, w, h })

describe('borderPoint', () => {
  it('leaves through the side that faces the target', () => {
    expect(borderPoint(box(0, 0), 500, 0)).toEqual({ x: 50, y: 0 })
    expect(borderPoint(box(0, 0), -500, 0)).toEqual({ x: -50, y: 0 })
    expect(borderPoint(box(0, 0), 0, 500)).toEqual({ x: 0, y: 20 })
    expect(borderPoint(box(0, 0), 0, -500)).toEqual({ x: 0, y: -20 })
  })

  it('lands on the rectangle for diagonal directions, never inside or outside it', () => {
    for (const [tx, ty] of [[300, 200], [-300, 200], [300, -200], [-80, -400], [1, 1], [400, 5]]) {
      const p = borderPoint(box(10, 20), 10 + tx, 20 + ty)
      const onVerticalSide = Math.abs(Math.abs(p.x - 10) - 50) < 1e-9 && Math.abs(p.y - 20) <= 20 + 1e-9
      const onHorizontalSide = Math.abs(Math.abs(p.y - 20) - 20) < 1e-9 && Math.abs(p.x - 10) <= 50 + 1e-9
      expect(onVerticalSide || onHorizontalSide).toBe(true)
      expect((p.x - 10) * ty).toBeCloseTo((p.y - 20) * tx, 6) // and it is on the line towards the target
    }
  })

  it('stays at the centre when the target is the centre', () => {
    expect(borderPoint(box(5, 5), 5, 5)).toEqual({ x: 5, y: 5 })
  })
})

describe('edgeEnds', () => {
  const a = box(0, 0)
  const b = box(300, 0)

  it('runs border to border, shifted sideways by the pair offset', () => {
    const e = edgeEnds(a, b)
    expect(e.sx).toBeCloseTo(50)
    expect(e.tx).toBeCloseTo(250)
    expect(Math.abs(e.sy)).toBeCloseTo(PAIR_OFFSET)
    expect(e.sy).toBeCloseTo(e.ty)
  })

  it('puts the two directions of a cable on opposite sides, so they never overlap', () => {
    const forward = edgeEnds(a, b)
    const back = edgeEnds(b, a)
    expect(forward.sy).toBeCloseTo(-back.sy)
    expect(Math.abs(forward.sy - back.sy)).toBeCloseTo(2 * PAIR_OFFSET)
    const diagonal = edgeEnds(box(0, 0), box(200, 150))
    const reverse = edgeEnds(box(200, 150), box(0, 0))
    expect(Math.hypot(diagonal.sx - reverse.tx, diagonal.sy - reverse.ty)).toBeGreaterThan(PAIR_OFFSET)
  })
})

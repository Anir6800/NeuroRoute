import type { ReactNode } from 'react'

export type Status = 'healthy' | 'warning' | 'critical' | 'info' | 'neutral'

// Status is never conveyed by color alone: every pill carries a glyph and text.
const GLYPH: Record<Status, string> = { healthy: '●', warning: '▲', critical: '✕', info: '◌', neutral: '○' }

export function StatusPill({ status, children }: { status: Status; children: ReactNode }) {
  return (
    <span className={`pill pill--${status}`}>
      <span aria-hidden="true">{GLYPH[status]}</span>
      <span>{children}</span>
    </span>
  )
}

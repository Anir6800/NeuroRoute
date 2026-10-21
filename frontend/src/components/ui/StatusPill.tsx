import type { ReactNode } from 'react'

export type Status = 'healthy' | 'warning' | 'critical' | 'info' | 'neutral'

// Status is never conveyed by color alone: every pill carries a glyph and text.
const GLYPH: Record<Status, string> = { healthy: '●', warning: '▲', critical: '✕', info: '◌', neutral: '○' }

export function StatusPill({ status, pulse = false, children }: { status: Status; pulse?: boolean; children: ReactNode }) {
  return (
    <span className={`pill pill--${status}${pulse ? ' pill--pulse' : ''}`}>
      <span className="pill__glyph" aria-hidden="true">
        {GLYPH[status]}
      </span>
      <span>{children}</span>
    </span>
  )
}

import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResult } from '../../api/health'
import { StatusPill } from '../ui/StatusPill'

const defaultCheck = () => fetchHealth()

/** Live backend status from GET /health; never shows a status it has not measured. */
export function BackendPill({ check = defaultCheck }: { check?: () => Promise<HealthResult> }) {
  const [result, setResult] = useState<HealthResult | null>(null)

  useEffect(() => {
    let live = true
    void check().then((r) => {
      if (live) setResult(r)
    })
    return () => {
      live = false
    }
  }, [check])

  return (
    <span role="status" aria-live="polite">
      {!result ? (
        <StatusPill status="neutral" pulse>
          Backend: checking
        </StatusPill>
      ) : result.ok ? (
        <StatusPill status="healthy">Backend ok</StatusPill>
      ) : (
        <StatusPill status="critical">Backend unavailable</StatusPill>
      )}
      {result && !result.ok && <span className="sr-only">: {result.error}</span>}
    </span>
  )
}

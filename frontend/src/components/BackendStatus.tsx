import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResult } from '../api/health'

const defaultCheck = () => fetchHealth()

export function BackendStatus({ check = defaultCheck }: { check?: () => Promise<HealthResult> }) {
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

  if (!result) return <p role="status">Checking backend...</p>
  return result.ok ? (
    <p role="status" style={{ color: 'var(--color-ok)' }}>
      Backend {result.data.status} (v{result.data.version})
    </p>
  ) : (
    <p role="alert" style={{ color: 'var(--color-error)' }}>
      Backend unavailable: {result.error}
    </p>
  )
}

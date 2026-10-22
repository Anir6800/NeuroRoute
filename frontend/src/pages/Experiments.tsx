import { useEffect, useState } from 'react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { EmptyState, LoadingState } from '../components/ui/States'
import { API_BASE_URL } from '../config'
import { RunTable, type ExperimentRun } from '../features/experiments/RunTable'
import { getIdToken } from '../lib/session'

type Detail = ExperimentRun & {
  metadata: { scenario_config_hash?: string; env_config_hash?: string; seeds?: number[] }
  runs: Array<{ run_id: string; seed: number; episodes: number; timesteps: number; wall_clock_s: number }>
}

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null

async function api(path: string): Promise<unknown> {
  const token = await getIdToken()
  if (!token) throw new Error('Sign in with the local Auth emulator to view experiment history.')
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  const body: unknown = await response.json()
  if (!response.ok) throw new Error(isObject(body) && typeof body.detail === 'string' ? body.detail : `Experiment request failed (HTTP ${response.status}).`)
  return body
}

function exportRun(detail: Detail) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(detail, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `neuroroute-${detail.job_id}.json`
  link.click()
  URL.revokeObjectURL(url)
}

export function Experiments() {
  const [history, setHistory] = useState<ExperimentRun[]>([])
  const [detail, setDetail] = useState<Detail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { void loadHistory() }, [])

  async function loadHistory() {
    setLoading(true)
    setError(null)
    try {
      const body = await api('/experiments')
      if (!Array.isArray(body)) throw new Error('The experiment service returned an unexpected response.')
      setHistory(body as ExperimentRun[])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load experiment history.')
    } finally {
      setLoading(false)
    }
  }

  async function select(jobId: string) {
    setError(null)
    try {
      const body = await api(`/experiments/${jobId}/details`)
      if (!isObject(body)) throw new Error('The experiment service returned an unexpected response.')
      setDetail(body as unknown as Detail)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not load experiment details.')
    }
  }

  return (
    <>
      <PageHeader title="Experiments" icon="experiments" description="Durable local history of completed and active training runs." actions={<Button onClick={() => void loadHistory()}>Refresh</Button>} />
      {error && <p role="alert" className="msg msg--error">{error}</p>}
      {loading && <LoadingState label="Loading experiment history" />}
      {!loading && !error && history.length === 0 && <EmptyState icon="experiments" title="No experiments recorded yet" description="Completed local training runs appear here after their manifests are written." />}
      {!loading && history.length > 0 && <Card title="Run history"><p className="training-source"><strong>Source:</strong> local experiment manifests and tracker metrics</p><RunTable runs={history} selectedId={detail?.job_id ?? null} onSelect={(jobId) => void select(jobId)} /></Card>}
      {detail && <Card title="Run details" className="experiment-detail">
        <div className="experiment-detail__header"><p className="training-source"><strong>Source:</strong> simulated MaskablePPO training · local experiment tracker</p><Button onClick={() => exportRun(detail)}>Export JSON</Button></div>
        <dl className="experiment-detail__metadata"><div><dt>Job</dt><dd>{detail.job_id}</dd></div><div><dt>Scenario hash</dt><dd>{detail.metadata.scenario_config_hash ?? 'Unavailable'}</dd></div><div><dt>Environment hash</dt><dd>{detail.metadata.env_config_hash ?? 'Unavailable'}</dd></div><div><dt>Seeds</dt><dd>{detail.metadata.seeds?.join(', ') ?? 'Unavailable'}</dd></div></dl>
        <div className="run-table-wrap"><table className="run-table"><thead><tr><th scope="col">Seed</th><th scope="col">Episodes</th><th scope="col">Steps</th><th scope="col">Wall time</th></tr></thead><tbody>{detail.runs.map((run) => <tr key={run.run_id}><th scope="row">{run.seed}</th><td>{run.episodes}</td><td>{run.timesteps.toLocaleString()}</td><td>{run.wall_clock_s.toFixed(1)} s</td></tr>)}</tbody></table></div>
      </Card>}
    </>
  )
}

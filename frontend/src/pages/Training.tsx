import { useState } from 'react'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { StatusPill, type Status } from '../components/ui/StatusPill'
import { API_BASE_URL } from '../config'
import { TrainingForm, type TrainingRequest } from '../features/training/TrainingForm'
import { useRunEvents, type RunProgress, type RunStatus } from '../features/training/useRunEvents'
import { getIdToken } from '../lib/session'

type StartResult = { ok: true; progress: RunProgress } | { ok: false; error: string }

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null
const statuses: RunStatus[] = ['queued', 'running', 'cancelled', 'failed', 'done']

async function startTraining(request: TrainingRequest): Promise<StartResult> {
  const token = await getIdToken()
  if (!token) return { ok: false, error: 'Sign in with the local Auth emulator before starting training.' }
  try {
    const response = await fetch(`${API_BASE_URL}/experiments/train`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    const body: unknown = await response.json()
    if (!response.ok) {
      const detail = isObject(body) ? body.detail : null
      return { ok: false, error: typeof detail === 'string' ? detail : `Training request failed (HTTP ${response.status}).` }
    }
    if (!isObject(body) || typeof body.job_id !== 'string' || !statuses.includes(body.status as RunStatus)
      || typeof body.elapsed_s !== 'number' || typeof body.completed_runs !== 'number' || typeof body.total_runs !== 'number'
      || (body.error !== null && typeof body.error !== 'string')) {
      return { ok: false, error: 'The training service returned an unexpected response.' }
    }
    return { ok: true, progress: { type: 'progress', ...(body as Omit<RunProgress, 'type'>) } }
  } catch {
    return { ok: false, error: 'The training service is unreachable.' }
  }
}

const label: Record<RunStatus, string> = {
  queued: 'Queued', running: 'Running', cancelled: 'Cancelled', failed: 'Failed', done: 'Completed',
}
const tone: Record<RunStatus, Status> = {
  queued: 'neutral', running: 'info', cancelled: 'warning', failed: 'critical', done: 'healthy',
}

export function Training({ launch = startTraining }: { launch?: typeof startTraining }) {
  const [jobId, setJobId] = useState<string | null>(null)
  const [initial, setInitial] = useState<RunProgress | null>(null)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const live = useRunEvents(jobId)
  const progress = live.event ?? initial
  const active = progress?.status === 'queued' || progress?.status === 'running'

  async function start(request: TrainingRequest) {
    setStarting(true)
    setStartError(null)
    const result = await launch(request)
    setStarting(false)
    if (!result.ok) {
      setStartError(result.error)
      return
    }
    setInitial(result.progress)
    setJobId(result.progress.job_id)
  }

  return (
    <>
      <PageHeader title="Training Lab" icon="training" description="Launch bounded CPU training and monitor simulated progress." />
      <div className="training-grid">
        <Card title="Run configuration">
          <TrainingForm busy={starting || active} onStart={start} />
          {startError && <p role="alert" className="msg msg--error">{startError}</p>}
        </Card>
        <Card title="Run status">
          <p className="training-source"><strong>Source:</strong> simulated MaskablePPO training · local experiment tracker</p>
          {!progress && <p className="training-idle">No run launched in this browser session.</p>}
          {progress && (
            <div className="training-progress" aria-live="polite">
              <StatusPill status={tone[progress.status]} pulse={active}>{label[progress.status]}</StatusPill>
              <dl>
                <div><dt>Job</dt><dd>{progress.job_id}</dd></div>
                <div><dt>Completed seeds</dt><dd>{progress.completed_runs} of {progress.total_runs}</dd></div>
                <div><dt>Elapsed</dt><dd>{progress.elapsed_s.toFixed(1)} s</dd></div>
                <div><dt>Updates</dt><dd>{live.transport}</dd></div>
              </dl>
              <progress aria-label="Completed training seeds" value={progress.completed_runs} max={progress.total_runs || 1} />
              {(progress.error || live.error) && <p role="alert" className="msg msg--error">{progress.error ?? live.error}</p>}
            </div>
          )}
        </Card>
      </div>
    </>
  )
}

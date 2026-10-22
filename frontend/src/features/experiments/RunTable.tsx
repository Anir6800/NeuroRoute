import { StatusPill, type Status } from '../../components/ui/StatusPill'

export type RunStatus = 'queued' | 'running' | 'cancelled' | 'failed' | 'done'

export interface ExperimentRun {
  job_id: string
  status: RunStatus
  error: string | null
  created_at: number
  scenario: string
  seed_count: number
  completed_runs: number
  total_runs: number
  total_timesteps: number
  wall_clock_s: number
  elapsed_s: number
}

const labels: Record<RunStatus, string> = {
  queued: 'Queued', running: 'Running', cancelled: 'Cancelled', failed: 'Failed', done: 'Completed',
}
const tones: Record<RunStatus, Status> = {
  queued: 'neutral', running: 'info', cancelled: 'warning', failed: 'critical', done: 'healthy',
}

export function RunTable({ runs, selectedId, onSelect }: { runs: ExperimentRun[]; selectedId: string | null; onSelect: (jobId: string) => void }) {
  return (
    <div className="run-table-wrap">
      <table className="run-table">
        <thead><tr><th scope="col">Run</th><th scope="col">Scenario</th><th scope="col">Status</th><th scope="col">Seeds</th><th scope="col">Steps</th><th scope="col">Wall time</th></tr></thead>
        <tbody>{runs.map((run) => (
          <tr key={run.job_id} aria-current={selectedId === run.job_id ? 'true' : undefined}>
            <th scope="row"><button type="button" className="run-table__select" onClick={() => onSelect(run.job_id)}>View {run.job_id}</button></th>
            <td>{run.scenario}</td><td><StatusPill status={tones[run.status]}>{labels[run.status]}</StatusPill></td>
            <td>{run.completed_runs}/{run.total_runs}</td><td>{run.total_timesteps.toLocaleString()}</td><td>{run.wall_clock_s.toFixed(1)} s</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { ErrorState, LoadingState } from '../components/ui/States'
import { getIncident, type Incident } from '../features/incidents/api'

export function IncidentDetail() {
  const { incidentId = '' } = useParams()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    void getIncident(incidentId).then((value) => { if (active) setIncident(value) }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Could not load incident detail.')
    })
    return () => { active = false }
  }, [attempt, incidentId])

  return <>
    <PageHeader title="Incident detail" icon="incidents" description="Evidence and diagnosis supplied by the live local incident API." />
    {!incident && !error && <LoadingState label="Loading incident" />}
    {error && <ErrorState title="Could not load incident" message={error} onRetry={() => setAttempt((value) => value + 1)} />}
    {incident && <Card title={incident.title}>
      <p className="incident-detail__meta">{incident.severity} · {new Date(incident.created_at).toLocaleString()}</p>
      <h3>Diagnosis</h3><p>{incident.diagnosis}</p>
      <h3>Evidence</h3><ul>{incident.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
      <h3>Timeline</h3><ol>{incident.timeline.map((item) => <li key={item}>{item}</li>)}</ol>
      <Link className="incident-detail__back" to="/incidents">Back to incidents</Link>
    </Card>}
  </>
}

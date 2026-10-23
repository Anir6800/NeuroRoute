import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { EmptyState, LoadingState } from '../components/ui/States'
import { StatusPill, type Status } from '../components/ui/StatusPill'
import { listIncidents, triggerIncident, type Incident } from '../features/incidents/api'

const tone: Record<Incident['severity'], Status> = { info: 'info', warning: 'warning', critical: 'critical' }

export function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [triggering, setTriggering] = useState(false)

  useEffect(() => {
    let active = true
    void listIncidents().then((value) => { if (active) setIncidents(value) }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : 'Could not load incidents.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function trigger() {
    setTriggering(true); setError(null)
    try {
      const incident = await triggerIncident()
      setIncidents((current) => [incident, ...current])
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not trigger the incident.') } finally { setTriggering(false) }
  }

  return <>
    <PageHeader title="Incidents" icon="incidents" description="Live local incident records with source evidence and diagnosis." actions={<Button onClick={() => void trigger()} disabled={triggering}>{triggering ? 'Triggering…' : 'Trigger test incident'}</Button>} />
    {error && <p role="alert" className="msg msg--error">{error}</p>}
    {loading && <LoadingState label="Loading incidents" />}
    {!loading && !error && incidents.length === 0 && <EmptyState icon="incidents" title="No incidents recorded" description="Use the manual trigger to verify the local incident API and detail flow." />}
    {!loading && incidents.length > 0 && <Card title="Live incidents"><ul className="incident-list">{incidents.map((incident) => <li key={incident.id}><Link to={`/incidents/${incident.id}`}>{incident.title}</Link><StatusPill status={tone[incident.severity]}>{incident.severity}</StatusPill><span>{new Date(incident.created_at).toLocaleString()}</span></li>)}</ul></Card>}
  </>
}

import { API_BASE_URL } from '../../config'
import { getIdToken } from '../../lib/session'

export interface Incident {
  id: string
  created_at: string
  severity: 'info' | 'warning' | 'critical'
  title: string
  diagnosis: string
  evidence: string[]
  timeline: string[]
}

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const token = await getIdToken()
  if (!token) throw new Error('Sign in with the local Auth emulator to view incidents.')
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, ...init?.headers } })
  const body: unknown = await response.json()
  if (!response.ok) throw new Error(typeof body === 'object' && body !== null && typeof (body as { detail?: unknown }).detail === 'string' ? (body as { detail: string }).detail : `Incident request failed (HTTP ${response.status}).`)
  return body
}

export async function listIncidents(): Promise<Incident[]> {
  const body = await request('/incidents')
  if (!Array.isArray(body)) throw new Error('The incident service returned an unexpected response.')
  return body as Incident[]
}

export async function getIncident(id: string): Promise<Incident> {
  const body = await request(`/incidents/${id}`)
  if (typeof body !== 'object' || body === null) throw new Error('The incident service returned an unexpected response.')
  return body as Incident
}

export async function triggerIncident(): Promise<Incident> {
  const body = await request('/incidents/trigger', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
    title: 'Manual API connectivity check', severity: 'warning', diagnosis: 'User triggered this local verification incident.',
    evidence: ['Created by the Incidents screen trigger control.'],
  }) })
  if (typeof body !== 'object' || body === null) throw new Error('The incident service returned an unexpected response.')
  return body as Incident
}

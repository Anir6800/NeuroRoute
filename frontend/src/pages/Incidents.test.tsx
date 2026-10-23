import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { IncidentDetail } from './IncidentDetail'
import { Incidents } from './Incidents'

vi.mock('../lib/session', () => ({ getIdToken: vi.fn().mockResolvedValue('token') }))

const incident = { id: 'incident-1', created_at: '2026-10-23T00:00:00+00:00', severity: 'warning', title: 'Manual API connectivity check', diagnosis: 'User triggered this local verification incident.', evidence: ['Created by the Incidents screen trigger control.'], timeline: ['2026-10-23T00:00:00+00:00: incident triggered'] }

afterEach(() => vi.unstubAllGlobals())

describe('Incidents', () => {
  it('triggers a live record then opens its evidence and diagnosis', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify([]))).mockResolvedValueOnce(new Response(JSON.stringify(incident))).mockResolvedValueOnce(new Response(JSON.stringify(incident))))
    render(<MemoryRouter initialEntries={['/incidents']}><Routes><Route path="/incidents" element={<Incidents />} /><Route path="/incidents/:incidentId" element={<IncidentDetail />} /></Routes></MemoryRouter>)
    expect(await screen.findByText('No incidents recorded')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Trigger test incident' }))
    expect(await screen.findByRole('link', { name: incident.title })).toBeTruthy()
    fireEvent.click(screen.getByRole('link', { name: incident.title }))
    expect(await screen.findByText(incident.diagnosis)).toBeTruthy()
    expect(screen.getByText(incident.evidence[0])).toBeTruthy()
    expect(screen.getByText(incident.timeline[0])).toBeTruthy()
  })
})

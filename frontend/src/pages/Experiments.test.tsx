import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Experiments } from './Experiments'

vi.mock('../lib/session', () => ({ getIdToken: vi.fn().mockResolvedValue('token') }))

const history = [{ job_id: 'job-1', status: 'done', error: null, created_at: 1, scenario: 'normal', seed_count: 2, completed_runs: 2, total_runs: 2, total_timesteps: 16, wall_clock_s: 2.75, elapsed_s: 0 }]
const detail = { ...history[0], metadata: { scenario_config_hash: 'scenario-hash', env_config_hash: 'env-hash', seeds: [3, 4] }, runs: [{ run_id: 'one', seed: 3, episodes: 2, timesteps: 8, wall_clock_s: 1.25 }], research_summary: { observations: [], limitations: ['No paired baseline outcome metrics were recorded, so no comparative claim is made.'] } }

afterEach(() => vi.unstubAllGlobals())

describe('Experiments', () => {
  it('shows durable history, details and exports the selected run', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(history))).mockResolvedValueOnce(new Response(JSON.stringify(detail)))
    vi.stubGlobal('fetch', fetchMock)
    const createObjectURL = vi.fn().mockReturnValue('blob:run')
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL: vi.fn() })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    render(<Experiments />)
    expect(await screen.findByRole('button', { name: 'View job-1' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'View job-1' }))
    expect(await screen.findByText('scenario-hash')).toBeTruthy()
    expect(screen.getByText(/no comparative claim/i)).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }))
    expect(createObjectURL).toHaveBeenCalledOnce()
    expect(click).toHaveBeenCalledOnce()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
  })
})

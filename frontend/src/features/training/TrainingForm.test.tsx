import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Training } from '../../pages/Training'
import { TrainingForm } from './TrainingForm'

const mocks = vi.hoisted(() => ({ getToken: vi.fn() }))

vi.mock('../../lib/session', () => ({ getIdToken: mocks.getToken }))
vi.mock('./useRunEvents', () => ({
  useRunEvents: (jobId: string | null) => jobId
    ? {
        event: {
          type: 'progress', job_id: jobId, status: 'done', error: null,
          elapsed_s: 9.5, completed_runs: 3, total_runs: 3,
        },
        transport: 'stopped', error: null,
      }
    : { event: null, transport: 'stopped', error: null },
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('TrainingForm', () => {
  it('rejects out-of-budget seeds, episodes, paths, and timesteps', async () => {
    const onStart = vi.fn()
    render(<TrainingForm busy={false} onStart={onStart} />)
    fireEvent.change(screen.getByLabelText('Training seeds'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Maximum episodes per seed'), { target: { value: '1001' } })
    fireEvent.change(screen.getByLabelText('Candidate paths (K)'), { target: { value: '17' } })
    fireEvent.change(screen.getByLabelText('Maximum timesteps per seed'), { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: 'Start controlled run' }))
    expect(await screen.findByText(/Seed count must/)).toBeTruthy()
    expect(screen.getByText(/Episode cap must/)).toBeTruthy()
    expect(screen.getByText(/Candidate paths must/)).toBeTruthy()
    expect(screen.getByText(/Timesteps must/)).toBeTruthy()
    expect(onStart).not.toHaveBeenCalled()
  })
})

describe('Training Lab', () => {
  it('launches the controlled request and renders source-labelled completion', async () => {
    mocks.getToken.mockResolvedValue('token')
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      job_id: 'job-42', status: 'running', error: null,
      elapsed_s: 0.2, completed_runs: 0, total_runs: 3,
    }), { status: 202 }))
    vi.stubGlobal('fetch', fetchImpl)
    render(<Training />)
    fireEvent.click(screen.getByRole('button', { name: 'Start controlled run' }))

    await waitFor(() => expect(fetchImpl).toHaveBeenCalledOnce())
    const [, request] = fetchImpl.mock.calls[0]
    expect(JSON.parse(request.body)).toEqual({
      scenario: 'normal', seed_count: 3, timesteps: 1000, max_episodes: 10, path_count: 4,
    })
    expect(request.headers.Authorization).toBe('Bearer token')
    expect(await screen.findByText('Completed')).toBeTruthy()
    expect(screen.getByText('3 of 3')).toBeTruthy()
    expect(screen.getByText(/Source:/).parentElement?.textContent).toContain('simulated MaskablePPO training')
    expect(screen.getByText(/Source:/).parentElement?.textContent).toContain('local experiment tracker')
  })
})

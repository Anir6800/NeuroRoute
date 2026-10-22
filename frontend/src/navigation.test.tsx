import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { NAV_ITEMS } from './app/navigation'
import { routes } from './app/router'
import { stubReactFlowEnvironment } from './features/topology/testing'
import { Comparison } from './pages/Comparison'
import { Experiments } from './pages/Experiments'
import { Overview } from './pages/Overview'
import { Topology } from './pages/Topology'
import { Training } from './pages/Training'

// The sign-in page is lazy-loaded and uses Firebase; keep the SDK out of these tests.
vi.mock('./lib/firebase', () => ({ auth: {} }))
vi.mock('firebase/auth', () => ({ signInWithEmailAndPassword: vi.fn() }))

function renderApp(path = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(<RouterProvider router={router} />)
}

const SCREENS = [
  { Page: Overview, path: '/', title: 'Overview' },
  { Page: Topology, path: '/topology', title: 'Topology Studio' },
  { Page: Training, path: '/training', title: 'Training Lab' },
  { Page: Experiments, path: '/experiments', title: 'Experiments' },
  { Page: Comparison, path: '/comparison', title: 'Model Comparison' },
] as const

// Values that only exist in the Stitch sample data: none may appear in the app.
const SAMPLE_MARKERS = ['3.42', '5.88', '8.14', '15.92', 'EXP-14', 'ActorCritic', 'Actor-Critic', 'M3 Max', 'DPDK', 'CUDA',
  'Elena Vance', 'Lead Researcher', '64-Spine', '4208-BURST']

beforeAll(stubReactFlowEnvironment) // the Topology Studio draws with React Flow, which needs browser APIs jsdom lacks

beforeEach(() => {
  document.title = ''
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('routes and navigation config', () => {
  it('every sidebar item has a route and every MVP route has a sidebar item', () => {
    const children = routes[0].children ?? []
    const routePaths = children
      .filter((r) => r.path !== 'login' && r.path !== '*')
      .map((r) => (r.index ? '/' : `/${r.path}`))
    expect([...routePaths].sort()).toEqual(NAV_ITEMS.map((i) => i.path).sort())
    expect(NAV_ITEMS.map((i) => i.label)).toEqual(SCREENS.map((s) => s.title))
  })
})

describe('navigation smoke tests', () => {
  it('walks every sidebar link; each page renders inside the same, never-remounted shell', async () => {
    renderApp('/')
    const banner = screen.getByRole('banner')
    for (const [i, item] of NAV_ITEMS.entries()) {
      const main = screen.getByRole('navigation', { name: 'Main' })
      fireEvent.click(within(main).getByRole('link', { name: item.label }))
      expect(await screen.findByRole('heading', { level: 1, name: item.label })).toBeTruthy()
      expect(within(main).getByRole('link', { name: item.label }).getAttribute('aria-current')).toBe('page')
      await waitFor(() => expect(document.title).toBe(`${item.label} - NeuroRoute`))
      expect(within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByText(item.label).getAttribute('aria-current')).toBe('page')
      expect((document.querySelector('.dock__pill') as HTMLElement).style.transform).toBe(`translateX(${i * 100}%)`)
      expect(screen.getByRole('banner')).toBe(banner) // same DOM node: the shell was not rebuilt
      expect(screen.getAllByRole('main')).toHaveLength(1)
      expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(1)
    }
  })

  it.each(SCREENS)('opens $path directly with the shell around it', async ({ path, title }) => {
    renderApp(path)
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeTruthy()
    expect(screen.getByRole('banner')).toBeTruthy()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeTruthy()
  })

  it('tolerates a trailing slash', async () => {
    renderApp('/topology/')
    expect(await screen.findByRole('heading', { level: 1, name: 'Topology Studio' })).toBeTruthy()
    await waitFor(() => expect(document.title).toBe('Topology Studio - NeuroRoute'))
  })

  it('shows a not-found page inside the shell for unknown addresses', async () => {
    renderApp('/definitely-not-a-page')
    expect(await screen.findByRole('heading', { level: 1, name: 'Page not found' })).toBeTruthy()
    expect(screen.getByRole('banner')).toBeTruthy()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeTruthy()
  })

  it('shows a loading state, not a blank page, while the lazy sign-in route loads', async () => {
    renderApp('/login')
    expect(screen.getByRole('status').textContent).toContain('Loading page')
    expect(await screen.findByRole('heading', { name: 'Test login' })).toBeTruthy()
  })

  it('lazy-loads the sign-in page inside the shell', async () => {
    renderApp('/login')
    expect(await screen.findByRole('heading', { name: 'Test login' })).toBeTruthy()
    expect(screen.getByRole('banner')).toBeTruthy()
    await waitFor(() => expect(document.title).toBe('Sign in - NeuroRoute'))
  })
})

// Topology Studio is a working editor now (tested in features/topology); the others are still placeholders.
const SKELETONS = SCREENS.filter((s) => s.path !== '/topology')

describe('screen skeletons are honest', () => {
  it.each(SKELETONS)('$title: empty by default, one disabled action with a visible reason', async ({ path }) => {
    renderApp(path)
    await screen.findByRole('heading', { level: 1 })
    const blocked = screen.getAllByRole('button').filter((b) => b.getAttribute('aria-disabled') === 'true')
    expect(blocked.length).toBeGreaterThan(0)
    for (const button of blocked) {
      const reason = document.getElementById(button.getAttribute('aria-describedby') ?? '')
      expect(reason?.textContent?.trim().length).toBeGreaterThan(0)
    }
    expect(screen.queryByRole('status', { name: /loading/i })).toBeNull()
  })

  it.each(SCREENS)('$title: shows no Stitch sample data', async ({ path }) => {
    renderApp(path)
    await screen.findByRole('heading', { level: 1 })
    const text = screen.getByRole('main').textContent ?? ''
    for (const marker of SAMPLE_MARKERS) expect(text).not.toContain(marker)
  })

  it('Topology Studio starts empty and honest: no invented network, save blocked with a reason', async () => {
    renderApp('/topology')
    await screen.findByRole('toolbar', { name: 'Topology actions' })
    expect(screen.getByText(/Empty canvas/)).toBeTruthy()
    expect(document.querySelectorAll('.react-flow__node')).toHaveLength(0)
    const save = screen.getByRole('button', { name: 'Save' })
    expect(save.getAttribute('aria-disabled')).toBe('true')
    expect(document.getElementById(save.getAttribute('aria-describedby') ?? '')?.textContent?.trim().length).toBeGreaterThan(0)
  })

  it.each(SKELETONS)('$title: renders loading, error and empty states', ({ Page }) => {
    const { rerender } = render(<Page status="loading" />)
    expect(screen.getAllByRole('status').some((s) => /\.\.\.$/.test(s.textContent ?? ''))).toBe(true)
    rerender(<Page status="error" />)
    expect(screen.getByRole('alert').textContent).toMatch(/did not respond/)
    rerender(<Page status="empty" />)
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getAllByRole('heading', { level: 2 }).length).toBeGreaterThan(0)
  })
})

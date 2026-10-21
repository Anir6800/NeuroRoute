import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NAV_ITEMS } from './app/navigation'
import { AppShell } from './components/layout/AppShell'
import { BackendPill } from './components/layout/BackendPill'

function renderShell(path = '/') {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  const router = createMemoryRouter(
    [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <h1>Home page</h1> },
          { path: 'login', element: <h1>Login page</h1> },
        ],
      },
    ],
    { initialEntries: [path] },
  )
  return render(<RouterProvider router={router} />)
}

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('AppShell', () => {
  it('provides landmarks, a skip link and a breadcrumb for the current page', () => {
    renderShell()
    expect(screen.getByRole('banner')).toBeTruthy()
    expect(screen.getByRole('main')).toBeTruthy()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeTruthy()
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Skip to content' }).getAttribute('href')).toBe('#main')
    const crumb = within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByText('Overview')
    expect(crumb.getAttribute('aria-current')).toBe('page')
  })

  it('sets the document title from the route', () => {
    renderShell('/login')
    expect(document.title).toBe('Sign in - NeuroRoute')
  })

  it('moves focus to main when navigating, but not on first render', async () => {
    renderShell()
    expect(document.activeElement).not.toBe(screen.getByRole('main'))
    fireEvent.click(screen.getByRole('link', { name: 'Sign in' }))
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('main')))
  })

  it('replays the enter animation by remounting the page wrapper on navigation', async () => {
    renderShell()
    const before = document.querySelector('.page')
    expect(before).not.toBeNull()
    fireEvent.click(screen.getByRole('link', { name: 'Sign in' }))
    await screen.findByRole('heading', { name: 'Login page' })
    expect(document.querySelector('.page')).not.toBe(before)
  })

  it('has no hamburger/drawer button: navigation is the always-visible dock (regression)', () => {
    renderShell()
    expect(screen.queryByRole('button', { name: /navigation/i })).toBeNull()
    expect(document.querySelector('.sidebar, .topbar__menu, .shell__scrim')).toBeNull()
  })

  it('keeps the brand link named even when its text is hidden on narrow screens', () => {
    renderShell()
    expect(screen.getByRole('link', { name: 'NeuroRoute home' }).getAttribute('href')).toBe('/')
  })
})

describe('bottom pill dock', () => {
  it('lists every destination by its full name, in order', () => {
    renderShell()
    const links = within(screen.getByRole('navigation', { name: 'Main' })).getAllByRole('link')
    expect(links.map((l) => l.getAttribute('aria-label'))).toEqual(NAV_ITEMS.map((i) => i.label))
    expect(links.map((l) => l.textContent)).toEqual(NAV_ITEMS.map((i) => i.short))
  })

  it('marks the active item and places the sliding pill under it', () => {
    renderShell()
    const links = within(screen.getByRole('navigation', { name: 'Main' })).getAllByRole('link')
    expect(links[0].getAttribute('aria-current')).toBe('page')
    expect((document.querySelector('.dock__pill') as HTMLElement).style.transform).toBe('translateX(0%)')
  })

  it('hides the pill on pages outside the dock (sign in, not found)', () => {
    renderShell('/login')
    expect(document.querySelector('.dock__pill')).toBeNull()
    const links = within(screen.getByRole('navigation', { name: 'Main' })).getAllByRole('link')
    expect(links.every((l) => l.getAttribute('aria-current') === null)).toBe(true)
  })
})

describe('theme toggle', () => {
  it('switches theme, sets data-theme and persists the choice', () => {
    renderShell()
    // jsdom has no matchMedia: the default is dark, so the button offers light
    fireEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('neuroroute.theme')).toBe('light')
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('neuroroute.theme')).toBe('dark')
  })

  it('restores a saved choice', () => {
    localStorage.setItem('neuroroute.theme', 'light')
    renderShell()
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeTruthy()
  })

  it('still works when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    renderShell()
    fireEvent.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    expect(document.documentElement.dataset.theme).toBe('light')
    vi.restoreAllMocks()
  })
})

describe('BackendPill', () => {
  it('shows ok only after a successful health check', async () => {
    render(<BackendPill check={() => Promise.resolve({ ok: true, data: { status: 'ok', app: 'NeuroRoute', version: '0.1.0' } })} />)
    expect(screen.getByText('Backend: checking')).toBeTruthy()
    await waitFor(() => expect(screen.getByText('Backend ok')).toBeTruthy())
  })

  it('shows unavailable with the reason for assistive tech when the check fails', async () => {
    render(<BackendPill check={() => Promise.resolve({ ok: false, error: 'Timed out after 3000 ms' })} />)
    await waitFor(() => expect(screen.getByText('Backend unavailable')).toBeTruthy())
    expect(screen.getByRole('status').textContent).toContain('Timed out after 3000 ms')
  })
})

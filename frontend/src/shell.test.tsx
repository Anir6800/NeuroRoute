import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BackendPill } from './components/layout/BackendPill'
import { AppShell } from './components/layout/AppShell'

function renderShell(path = '/') {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<h1>Home page</h1>} />
          <Route path="login" element={<h1>Login page</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
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

  it('marks the active sidebar link with aria-current', () => {
    renderShell()
    const link = within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: 'Overview' })
    expect(link.getAttribute('aria-current')).toBe('page')
  })

  it('sets the document title from the route', () => {
    renderShell('/login')
    expect(document.title).toBe('Sign in - NeuroRoute')
  })

  it('moves focus to main when navigating, but not on first render', () => {
    renderShell()
    expect(document.activeElement).not.toBe(screen.getByRole('main'))
    fireEvent.click(screen.getByRole('link', { name: 'Sign in' }))
    expect(document.activeElement).toBe(screen.getByRole('main'))
  })

  it('toggles the mobile navigation drawer and closes it on navigation', () => {
    renderShell()
    const menu = screen.getByRole('button', { name: 'Open navigation' })
    expect(menu.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(menu)
    expect(screen.getByRole('button', { name: 'Close navigation' }).getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(screen.getByRole('link', { name: 'Sign in' }))
    expect(screen.getByRole('button', { name: 'Open navigation' }).getAttribute('aria-expanded')).toBe('false')
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

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchMe } from './api/me'
import { Login } from './pages/Login'

const signIn = vi.fn()
vi.mock('./lib/firebase', () => ({ auth: {} }))
vi.mock('firebase/auth', () => ({ signInWithEmailAndPassword: (...a: unknown[]) => signIn(...a) }))

afterEach(() => {
  cleanup()
  signIn.mockReset()
})

const resp = (status: number, body: unknown = {}) =>
  vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })) as unknown as typeof fetch

describe('fetchMe', () => {
  it('sends the bearer token and parses the user', async () => {
    const f = resp(200, { uid: 'u1', email: 'a@b.c', role: 'researcher' })
    const r = await fetchMe('tok', f, '/api')
    expect(r).toEqual({ ok: true, data: { uid: 'u1', email: 'a@b.c', role: 'researcher' } })
    const init = (f as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok')
  })
  it('maps 401 and 403 to explicit errors', async () => {
    expect((await fetchMe('t', resp(401), '/api')).ok).toBe(false)
    expect(await fetchMe('t', resp(403), '/api')).toEqual({
      ok: false,
      error: 'Forbidden: role or project not allowed (403)',
    })
  })
  it('rejects a malformed body', async () => {
    expect((await fetchMe('t', resp(200, { uid: 1 }), '/api')).ok).toBe(false)
  })
})

describe('Login page', () => {
  function fill() {
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'dev@neuroroute.test' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'devpass123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  }

  it('shows an error when sign-in fails', async () => {
    signIn.mockRejectedValue(new Error('auth/invalid-credential'))
    render(<Login />)
    fill()
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Sign-in failed'))
  })

  it('shows the signed-in user after a successful /me', async () => {
    signIn.mockResolvedValue({ user: { getIdToken: () => Promise.resolve('tok') } })
    vi.stubGlobal('fetch', resp(200, { uid: 'u1', email: 'dev@neuroroute.test', role: 'researcher' }))
    render(<Login />)
    fill()
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('researcher'))
    vi.unstubAllGlobals()
  })
})

describe('Login layout', () => {
  it('is a centered auth panel with exactly one h1', () => {
    const { container } = render(<Login />)
    expect(container.querySelector('.auth > .auth__panel')).not.toBeNull()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })
})

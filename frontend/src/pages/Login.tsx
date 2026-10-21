import { signInWithEmailAndPassword } from 'firebase/auth'
import { useState, type FormEvent } from 'react'
import { fetchMe, type MeResult } from '../api/me'
import { auth } from '../lib/firebase'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<MeResult | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setResult(null)
    setAuthError(null)
    try {
      const cred = await signInWithEmailAndPassword(auth, email, password)
      setResult(await fetchMe(await cred.user.getIdToken()))
    } catch {
      setAuthError('Sign-in failed (is the Auth emulator running on 127.0.0.1:9099?)')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <h1>Test login</h1>
      <p style={{ color: 'var(--color-muted)' }}>Local Firebase Auth emulator only.</p>
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 'var(--space)', maxWidth: 320 }}>
        <label>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
      {authError && (
        <p role="alert" style={{ color: 'var(--color-error)' }}>
          {authError}
        </p>
      )}
      {result?.ok && (
        <p role="status" style={{ color: 'var(--color-ok)' }}>
          Signed in as {result.data.email ?? result.data.uid} (role: {result.data.role})
        </p>
      )}
      {result && !result.ok && (
        <p role="alert" style={{ color: 'var(--color-error)' }}>
          /me rejected: {result.error}
        </p>
      )}
    </section>
  )
}

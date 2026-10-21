import { signInWithEmailAndPassword } from 'firebase/auth'
import { useState, type FormEvent } from 'react'
import { fetchMe, type MeResult } from '../api/me'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
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
    <>
      <PageHeader title="Test login" description="Local Firebase Auth emulator only." />
      <Card>
        <form onSubmit={onSubmit} className="form">
          <label className="field">
            Email
            <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            Password
            <input
              type="password"
              required
              minLength={6}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        {authError && (
          <p role="alert" className="msg msg--error">
            {authError}
          </p>
        )}
        {result?.ok && (
          <p role="status" className="msg msg--ok">
            Signed in as {result.data.email ?? result.data.uid} (role: {result.data.role})
          </p>
        )}
        {result && !result.ok && (
          <p role="alert" className="msg msg--error">
            /me rejected: {result.error}
          </p>
        )}
      </Card>
    </>
  )
}

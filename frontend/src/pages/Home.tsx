import { BackendStatus } from '../components/BackendStatus'

export function Home() {
  return (
    <section className="card">
      <h1>NeuroRoute</h1>
      <p style={{ color: 'var(--color-muted)' }}>
        Local research console. No results are shown until real runs exist.
      </p>
      <BackendStatus />
    </section>
  )
}

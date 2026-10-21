import { NavLink, Outlet } from 'react-router-dom'

export function Layout() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: 'var(--space)' }}>
      <nav aria-label="Main" style={{ display: 'flex', gap: 'var(--space)', alignItems: 'center' }}>
        <strong style={{ color: 'var(--color-accent)' }}>NeuroRoute</strong>
        <NavLink to="/">Home</NavLink>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  )
}

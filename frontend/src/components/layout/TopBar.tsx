import { NavLink, useLocation } from 'react-router-dom'
import { titleFor } from '../../app/navigation'
import { Icon } from '../ui/Icon'
import { BackendPill } from './BackendPill'
import { ThemeToggle } from './ThemeToggle'

export function TopBar({ menuOpen, onMenu }: { menuOpen: boolean; onMenu: () => void }) {
  const { pathname } = useLocation()
  return (
    <header className="topbar">
      <div className="topbar__left">
        <button
          type="button"
          className="btn btn--ghost btn--icon topbar__menu"
          aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={menuOpen}
          aria-controls="sidebar"
          onClick={onMenu}
        >
          <Icon name="menu" />
        </button>
        <nav aria-label="Breadcrumb">
          <ol className="crumbs">
            <li>NeuroRoute</li>
            <li aria-current="page">{titleFor(pathname)}</li>
          </ol>
        </nav>
      </div>
      <div className="topbar__right">
        <BackendPill />
        <ThemeToggle />
        <NavLink to="/login" className="topbar__signin">
          Sign in
        </NavLink>
      </div>
    </header>
  )
}

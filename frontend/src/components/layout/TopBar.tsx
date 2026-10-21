import { Link, NavLink, useLocation } from 'react-router-dom'
import { titleFor } from '../../app/navigation'
import { Icon } from '../ui/Icon'
import { BackendPill } from './BackendPill'
import { ThemeToggle } from './ThemeToggle'

export function TopBar() {
  const { pathname } = useLocation()
  return (
    <header className="topbar">
      <nav aria-label="Breadcrumb">
        <ol className="crumbs">
          <li>
            <Link to="/" className="brand" aria-label="NeuroRoute home">
              <span className="brand__logo" aria-hidden="true">
                <Icon name="topology" />
              </span>
              <span className="brand__name">NeuroRoute</span>
            </Link>
          </li>
          <li aria-current="page">{titleFor(pathname)}</li>
        </ol>
      </nav>
      <div className="topbar__right">
        <BackendPill />
        <ThemeToggle />
        <NavLink to="/login" className="btn btn--ghost">
          Sign in
        </NavLink>
      </div>
    </header>
  )
}

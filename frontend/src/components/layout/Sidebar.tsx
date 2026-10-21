import { NavLink } from 'react-router-dom'
import { NAV_ITEMS } from '../../app/navigation'
import { Icon } from '../ui/Icon'

export function Sidebar({ open }: { open: boolean }) {
  return (
    <aside id="sidebar" className={`sidebar${open ? ' is-open' : ''}`}>
      <div className="sidebar__brand">
        <span className="sidebar__logo" aria-hidden="true">
          <Icon name="topology" />
        </span>
        <div>
          <strong>NeuroRoute</strong>
          <span className="sidebar__sub">Local workspace</span>
        </div>
      </div>
      <nav aria-label="Main">
        <ul>
          {NAV_ITEMS.map((item) => (
            <li key={item.path}>
              <NavLink to={item.path} end={item.path === '/'} className="sidebar__link">
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <p className="sidebar__foot">Services bind to 127.0.0.1 only</p>
    </aside>
  )
}

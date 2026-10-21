import { NavLink, useLocation } from 'react-router-dom'
import { activeIndex, NAV_ITEMS } from '../../app/navigation'
import { Icon } from '../ui/Icon'

/** Floating, pill-shaped bottom navigation. The highlight slides to the active item. */
export function Dock() {
  const index = activeIndex(useLocation().pathname)
  return (
    <nav aria-label="Main" className="dock">
      <div className="dock__track">
        {index >= 0 && (
          <span className="dock__pill" aria-hidden="true" style={{ transform: `translateX(${index * 100}%)` }} />
        )}
        <ul className="dock__list">
          {NAV_ITEMS.map((item) => (
            <li key={item.path}>
              <NavLink to={item.path} end={item.path === '/'} className="dock__link" aria-label={item.label} title={item.label}>
                <Icon name={item.icon} />
                <span className="dock__label">{item.short}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}

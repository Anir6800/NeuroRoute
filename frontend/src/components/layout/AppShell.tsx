import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { titleFor } from '../../app/navigation'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

/** The one shell every route renders inside: sidebar, top bar, skip link, main landmark. */
export function AppShell() {
  const { pathname } = useLocation()
  // The drawer is open only for the page it was opened on, so navigating closes it without an effect.
  const [openAt, setOpenAt] = useState<string | null>(null)
  const menuOpen = openAt === pathname
  const mainRef = useRef<HTMLElement>(null)
  const firstRender = useRef(true)

  useEffect(() => {
    document.title = `${titleFor(pathname)} - NeuroRoute`
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    mainRef.current?.focus() // announce the new page to keyboard and screen-reader users
  }, [pathname])

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar open={menuOpen} />
      <div className="shell__body">
        <TopBar menuOpen={menuOpen} onMenu={() => setOpenAt(menuOpen ? null : pathname)} />
        <main id="main" ref={mainRef} tabIndex={-1} className="shell__main">
          <div className="shell__content">
            <Outlet />
          </div>
        </main>
      </div>
      {menuOpen && <div className="shell__scrim" aria-hidden="true" onClick={() => setOpenAt(null)} />}
    </div>
  )
}

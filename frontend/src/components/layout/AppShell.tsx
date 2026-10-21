import { useEffect, useRef } from 'react'
import { Outlet, ScrollRestoration, useLocation } from 'react-router-dom'
import { titleFor } from '../../app/navigation'
import { Dock } from './Dock'
import { TopBar } from './TopBar'

/** The one shell every route renders inside: top bar, bottom dock, skip link, main landmark. */
export function AppShell() {
  const { pathname } = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  const firstRender = useRef(true)

  useEffect(() => {
    document.title = `${titleFor(pathname)} - NeuroRoute`
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    mainRef.current?.focus({ preventScroll: true }) // announce the new page to keyboard and screen-reader users
  }, [pathname])

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <TopBar />
      <main id="main" ref={mainRef} tabIndex={-1} className="shell__main">
        <div className="shell__content">
          {/* keyed by address so each navigation replays the enter animation */}
          <div key={pathname} className="page">
            <Outlet />
          </div>
        </div>
      </main>
      <Dock />
      <ScrollRestoration />
    </div>
  )
}

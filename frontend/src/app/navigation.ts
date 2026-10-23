import type { IconName } from '../components/ui/Icon'

export interface NavItem {
  path: string
  /** Full name: accessible name, breadcrumb and document title. */
  label: string
  /** Short name shown under the icon in the bottom dock. */
  short: string
  icon: IconName
}

/** Single source of truth for the dock, breadcrumbs and document titles (router.tsx must match). */
export const NAV_ITEMS: readonly NavItem[] = [
  { path: '/', label: 'Overview', short: 'Overview', icon: 'overview' },
  { path: '/topology', label: 'Topology Studio', short: 'Topology', icon: 'topology' },
  { path: '/training', label: 'Training Lab', short: 'Training', icon: 'training' },
  { path: '/experiments', label: 'Experiments', short: 'Experiments', icon: 'experiments' },
  { path: '/incidents', label: 'Incidents', short: 'Incidents', icon: 'incidents' },
  { path: '/comparison', label: 'Model Comparison', short: 'Compare', icon: 'comparison' },
]

const OTHER_TITLES: Record<string, string> = { '/login': 'Sign in' }

function normalize(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
}

/** Index of the dock item for this address, or -1 for pages outside the dock (sign in, not found). */
export function activeIndex(pathname: string): number {
  const path = normalize(pathname)
  return NAV_ITEMS.findIndex((i) => i.path === path)
}

export function titleFor(pathname: string): string {
  const path = normalize(pathname)
  if (path.startsWith('/incidents/')) return 'Incident detail'
  return NAV_ITEMS.find((i) => i.path === path)?.label ?? OTHER_TITLES[path] ?? 'Page not found'
}

import type { IconName } from '../components/ui/Icon'

export interface NavItem {
  path: string
  label: string
  icon: IconName
}

/** Single source of truth for the sidebar, breadcrumbs and document titles (router.tsx must match). */
export const NAV_ITEMS: readonly NavItem[] = [
  { path: '/', label: 'Overview', icon: 'overview' },
  { path: '/topology', label: 'Topology Studio', icon: 'topology' },
  { path: '/training', label: 'Training Lab', icon: 'training' },
  { path: '/experiments', label: 'Experiments', icon: 'experiments' },
  { path: '/comparison', label: 'Model Comparison', icon: 'comparison' },
]

const OTHER_TITLES: Record<string, string> = { '/login': 'Sign in' }

export function titleFor(pathname: string): string {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
  return NAV_ITEMS.find((i) => i.path === path)?.label ?? OTHER_TITLES[path] ?? 'Page not found'
}

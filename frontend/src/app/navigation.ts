import type { IconName } from '../components/ui/Icon'

export interface NavItem {
  path: string
  label: string
  icon: IconName
}

/** Single source of truth for the sidebar, breadcrumbs and document titles. */
export const NAV_ITEMS: readonly NavItem[] = [{ path: '/', label: 'Overview', icon: 'overview' }]

const OTHER_TITLES: Record<string, string> = { '/login': 'Sign in' }

export function titleFor(pathname: string): string {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
  return NAV_ITEMS.find((i) => i.path === path)?.label ?? OTHER_TITLES[path] ?? 'Page not found'
}

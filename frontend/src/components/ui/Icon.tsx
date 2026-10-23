import type { ReactNode } from 'react'

export type IconName =
  | 'overview'
  | 'topology'
  | 'training'
  | 'experiments'
  | 'comparison'
  | 'incidents'
  | 'sun'
  | 'moon'
  | 'menu'

// Inline SVG instead of an icon font or package: no hosted assets, no dependency.
const PATHS: Record<IconName, ReactNode> = {
  overview: (
    <>
      <rect x="3" y="3" width="8" height="8" rx="2" />
      <rect x="13" y="3" width="8" height="8" rx="2" />
      <rect x="3" y="13" width="8" height="8" rx="2" />
      <rect x="13" y="13" width="8" height="8" rx="2" />
    </>
  ),
  topology: (
    <>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <circle cx="12" cy="18" r="2.5" />
      <path d="M8.5 6h7M7.2 8.2l3.6 7.6M16.8 8.2l-3.6 7.6" />
    </>
  ),
  training: <path d="M3 17l6-6 4 4 8-8M15 7h6v6" />,
  experiments: <path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3" />,
  comparison: <path d="M6 20V10M12 20V4M18 20v-7" />,
  incidents: <path d="M12 3 3 20h18L12 3Zm0 6v4m0 4h.01" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: <path d="M21 13a8 8 0 1 1-10-10 6 6 0 0 0 10 10z" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
}

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}

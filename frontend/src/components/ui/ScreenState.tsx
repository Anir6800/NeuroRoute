import type { ReactNode } from 'react'
import type { IconName } from './Icon'
import { EmptyState, ErrorState, LoadingState } from './States'

export type ScreenStatus = 'loading' | 'empty' | 'error' | 'ready'

interface Props {
  status: ScreenStatus
  loadingLabel?: string
  empty: { title: string; description: string; icon?: IconName; action?: ReactNode }
  error?: { title?: string; message: string; onRetry?: () => void }
  children?: ReactNode
}

/** One place that decides loading / empty / error / ready, so every screen handles all four. */
export function ScreenState({ status, loadingLabel, empty, error, children }: Props) {
  switch (status) {
    case 'loading':
      return <LoadingState label={loadingLabel} />
    case 'error':
      return <ErrorState {...(error ?? { message: 'Unknown error' })} />
    case 'empty':
      return (
        <EmptyState title={empty.title} description={empty.description} icon={empty.icon}>
          {empty.action}
        </EmptyState>
      )
    default:
      return <>{children}</>
  }
}

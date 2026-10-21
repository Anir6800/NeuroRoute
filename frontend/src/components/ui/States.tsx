import type { ReactNode } from 'react'
import { Button } from './Button'

export function EmptyState({ title, description, children }: { title: string; description: string; children?: ReactNode }) {
  return (
    <div className="state state--empty">
      <h2 className="state__title">{title}</h2>
      <p className="state__text">{description}</p>
      {children}
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <h2 className="state__title">{title}</h2>
      <p className="state__text">{message}</p>
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
    </div>
  )
}

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="state state--loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}...</span>
    </div>
  )
}

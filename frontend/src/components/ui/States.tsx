import type { ReactNode } from 'react'
import { Button } from './Button'
import { Icon, type IconName } from './Icon'

interface EmptyProps {
  title: string
  description: string
  icon?: IconName
  children?: ReactNode
}

export function EmptyState({ title, description, icon, children }: EmptyProps) {
  return (
    <div className="state state--empty">
      {icon && (
        <span className="state__icon" aria-hidden="true">
          <Icon name={icon} size={24} />
        </span>
      )}
      <div className="state__body">
        <h2 className="state__title">{title}</h2>
        <p className="state__text">{description}</p>
        {children}
      </div>
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <div className="state__body">
        <h2 className="state__title">{title}</h2>
        <p className="state__text">{message}</p>
        {onRetry && <Button onClick={onRetry}>Try again</Button>}
      </div>
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

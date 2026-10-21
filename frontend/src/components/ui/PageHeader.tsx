import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

interface Props {
  title: string
  description?: string
  icon?: IconName
  actions?: ReactNode
}

export function PageHeader({ title, description, icon, actions }: Props) {
  return (
    <div className="page-header">
      <div className="page-header__main">
        {icon && (
          <span className="page-header__icon" aria-hidden="true">
            <Icon name={icon} size={22} />
          </span>
        )}
        <div>
          <h1>{title}</h1>
          {description && <p>{description}</p>}
        </div>
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </div>
  )
}

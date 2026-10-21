import { useId, type ButtonHTMLAttributes, type ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'type'> {
  variant?: Variant
  /**
   * Why the action is unavailable. The button stays focusable (aria-disabled), ignores clicks,
   * and the reason is shown as visible text and linked with aria-describedby.
   */
  disabledReason?: string
  children: ReactNode
}

export function Button({ variant = 'secondary', disabledReason, className, onClick, children, ...rest }: Props) {
  const reasonId = useId()
  const blocked = Boolean(disabledReason)
  return (
    <span className="btn-wrap">
      <button
        type="button"
        {...rest}
        className={`btn btn--${variant}${className ? ` ${className}` : ''}`}
        aria-disabled={blocked || rest.disabled ? true : undefined}
        aria-describedby={blocked ? reasonId : rest['aria-describedby']}
        onClick={blocked ? (e) => e.preventDefault() : onClick}
      >
        {children}
      </button>
      {blocked && (
        <span id={reasonId} className="btn-reason">
          {disabledReason}
        </span>
      )}
    </span>
  )
}

import { useTheme } from '../../lib/theme'
import { Icon } from '../ui/Icon'

export function ThemeToggle() {
  const { effective, toggle } = useTheme()
  const next = effective === 'dark' ? 'light' : 'dark'
  return (
    <button type="button" className="btn btn--ghost btn--icon" onClick={toggle} aria-label={`Switch to ${next} theme`}>
      <Icon name={effective === 'dark' ? 'sun' : 'moon'} />
    </button>
  )
}

import { Sun, Moon, MonitorCog } from 'lucide-react'
import { useTheme } from '../lib/theme'

const THEME_META = {
  light: { icon: Sun, label: 'Light theme' },
  dark: { icon: Moon, label: 'Dark theme' },
  system: { icon: MonitorCog, label: 'System theme' },
}

// Cycles light -> dark -> system -> light. Used in both the public navbar
// and the shared Sidebar so the preference (persisted in localStorage) is
// reachable whether the visitor is logged out or inside any portal.
const ThemeToggle = ({ className = '' }) => {
  const { theme, cycleTheme } = useTheme()
  const { icon: Icon, label } = THEME_META[theme]

  return (
    <button
      type="button"
      className={`theme-toggle ${className}`.trim()}
      onClick={cycleTheme}
      title={`${label} (click to change)`}
      aria-label={`${label}. Click to change.`}
    >
      <Icon size={16} />
    </button>
  )
}

export default ThemeToggle

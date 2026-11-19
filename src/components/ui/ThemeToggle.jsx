import { useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { applyTheme, effectiveTheme } from '../../lib/viewTransition'

// Light / dark switch for the top bar. Starts from the system setting; a
// choice is remembered per browser (src/lib/viewTransition.js).
export default function ThemeToggle({ className = 'topbar-icon-btn' }) {
  const [dark, setDark] = useState(() => (typeof document === 'undefined' ? false : effectiveTheme() === 'dark'))
  const toggle = () => {
    const next = !dark
    applyTheme(next ? 'dark' : 'light')
    setDark(next)
  }
  return (
    <button type="button" className={className} onClick={toggle} aria-pressed={dark} title={dark ? 'Use light mode' : 'Use dark mode'}>
      {dark ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
      <span className="sr-only">Dark mode</span>
    </button>
  )
}

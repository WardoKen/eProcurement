// Light/dark theme preference, shared by every page via a tiny custom hook
// instead of a context provider - there's no existing app-wide state
// container to hook into, and this keeps the addition self-contained.
//
// Preference is one of 'light' | 'dark' | 'system' and is persisted to
// localStorage. 'system' means "no explicit choice" - the CSS in index.css
// then follows the OS-level prefers-color-scheme media query. An explicit
// 'light' or 'dark' is applied via a data-theme attribute on <html>, which
// takes priority over the OS setting in the CSS.
import { useEffect, useState } from 'react'

const STORAGE_KEY = 'eProcureTheme'

function applyTheme(theme) {
  const root = document.documentElement
  if (theme === 'light' || theme === 'dark') {
    root.setAttribute('data-theme', theme)
  } else {
    root.removeAttribute('data-theme')
  }
}

function readStoredTheme() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  } catch {
    // Storage may be unavailable (private mode) - fall back to system.
  }
  return 'system'
}

export function useTheme() {
  const [theme, setThemeState] = useState(readStoredTheme)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    const onStorage = (event) => {
      if (event.key === STORAGE_KEY) {
        setThemeState(readStoredTheme())
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const setTheme = (next) => {
    setThemeState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Storage may be unavailable (private mode) - the in-memory state
      // above still applies the theme for the rest of this session.
    }
  }

  const cycleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light')
  }

  return { theme, setTheme, cycleTheme }
}

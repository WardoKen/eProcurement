import { flushSync } from 'react-dom'

// Runs a state update inside a View Transition, so the content area
// cross-fades between pages (DESIGN.md, "Motion"). Falls back to a plain
// update where the API is missing or the user prefers reduced motion.
export function withViewTransition(update) {
  const reduced = typeof window !== 'undefined'
    && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (typeof document === 'undefined' || !document.startViewTransition || reduced) {
    update()
    return
  }
  // The names that pair old and new views (base.css, shell.css) are only
  // set while a transition runs: a view-transition-name makes a stacking
  // context, which would otherwise trap dialogs under the sticky top bar.
  const root = document.documentElement
  root.classList.add('vt-active')
  const transition = document.startViewTransition(() => {
    flushSync(update)
  })
  transition.finished.finally(() => root.classList.remove('vt-active'))
}

// Theme: 'light' | 'dark' | null (follow the system). Stored per browser.
const THEME_KEY = 'eprocure-theme'

export function readTheme() {
  try {
    const value = window.localStorage.getItem(THEME_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

export function applyTheme(theme) {
  const root = document.documentElement
  if (theme) root.setAttribute('data-theme', theme)
  else root.removeAttribute('data-theme')
  try {
    if (theme) window.localStorage.setItem(THEME_KEY, theme)
    else window.localStorage.removeItem(THEME_KEY)
  } catch {
    // Storage blocked: the choice lasts for this page only.
  }
}

export function effectiveTheme() {
  const forced = document.documentElement.getAttribute('data-theme')
  if (forced === 'light' || forced === 'dark') return forced
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

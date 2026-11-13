import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom gaps the app touches during normal rendering.
if (!window.URL.createObjectURL) window.URL.createObjectURL = () => 'blob:mock'
if (!window.URL.revokeObjectURL) window.URL.revokeObjectURL = () => {}
window.scrollTo = () => {}
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
  })
}
if (!HTMLElement.prototype.scrollIntoView) HTMLElement.prototype.scrollIntoView = () => {}

afterEach(() => {
  cleanup()
  window.sessionStorage.clear()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

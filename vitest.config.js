import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Test-only config. Kept separate from vite.config.js so the production build
// configuration is untouched.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.test.{js,jsx}'],
    css: false,
    testTimeout: 20000,
  },
})

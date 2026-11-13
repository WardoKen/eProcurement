// Contract-test harness: renders the real <App /> at a route with a fake API,
// and records every request (method, path, body) the UI sends. Flow tests
// snapshot those records, so any change to an endpoint, method or payload
// during the UI refactor fails the suite.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { createElement } from 'react'
import App from '../App.jsx'

const API_BASE = 'http://127.0.0.1:8000'

// Strips the API origin and the cache-busting `t=` param so recorded paths are
// stable across runs.
function normalizePath(url) {
  const parsed = new URL(url, API_BASE)
  parsed.searchParams.delete('t')
  const query = parsed.searchParams.toString()
  return `${parsed.pathname}${query ? `?${query}` : ''}`
}

function describeBody(body) {
  if (body === undefined || body === null) return null
  if (typeof body === 'string') {
    try { return JSON.parse(body) } catch { return body }
  }
  if (body instanceof FormData) {
    return [...body.entries()].map(([key, value]) => (
      [key, value instanceof File ? `file:${value.name}` : value]
    ))
  }
  return String(body)
}

function makeResponse({ status = 200, json = {} } = {}) {
  const text = JSON.stringify(json)
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: async () => JSON.parse(text),
    text: async () => text,
    blob: async () => new Blob([text]),
  }
}

// `routes` maps "METHOD /path" (optionally with query) to either a response
// spec `{ status, json }` or a function receiving the recorded call.
export function installApi(routes = {}) {
  const calls = []
  const resolve = (method, path) => {
    const bare = path.split('?')[0]
    return routes[`${method} ${path}`] ?? routes[`${method} ${bare}`]
  }

  globalThis.fetch = vi.fn(async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input.url
    const method = (init.method || 'GET').toUpperCase()
    const call = { method, path: normalizePath(url), body: describeBody(init.body) }
    calls.push(call)
    const handler = resolve(method, call.path)
    const spec = typeof handler === 'function' ? handler(call) : handler
    return makeResponse(spec || { status: 404, json: { message: 'not mocked' } })
  })

  // The supplier registration wizard uploads with XMLHttpRequest for progress.
  class FakeXHR {
    constructor() { this.upload = {}; this.status = 0; this.responseText = '' }
    open(method, url) { this.method = method.toUpperCase(); this.url = url }
    setRequestHeader() {}
    send(body) {
      const call = { method: this.method, path: normalizePath(this.url), body: describeBody(body), transport: 'xhr' }
      calls.push(call)
      const handler = resolve(this.method, call.path)
      const spec = (typeof handler === 'function' ? handler(call) : handler) || { status: 404, json: {} }
      setTimeout(() => {
        this.status = spec.status ?? 200
        this.responseText = JSON.stringify(spec.json ?? {})
        this.onload?.()
      }, 0)
    }
  }
  globalThis.XMLHttpRequest = FakeXHR

  return {
    calls,
    // Requests that change server state, in the order they were sent.
    mutations: () => calls.filter((call) => call.method !== 'GET'),
    find: (method, path) => calls.filter((call) => call.method === method && call.path === path),
  }
}

export function signIn(user) {
  window.sessionStorage.setItem('eProcureUser', JSON.stringify(user))
  if (user.supplier_id) window.sessionStorage.setItem('supplier_id', String(user.supplier_id))
  if (user.supplier_status) window.sessionStorage.setItem('supplier_status', user.supplier_status)
}

export function renderAt(path) {
  window.history.pushState({}, '', path)
  vi.spyOn(window, 'alert').mockImplementation(() => {})
  vi.spyOn(window, 'confirm').mockImplementation(() => true)
  const user = userEvent.setup()
  const utils = render(createElement(App))
  return { user, ...utils }
}

// Irreversible actions may ask for confirmation in an in-app dialog. When one
// is open, accept it with its confirming button; when the action confirms
// some other way (or not at all), this is a no-op. This keeps the payload
// assertions valid whether or not a confirmation step sits in front.
export async function acceptConfirmation(user, confirmName = /^confirm|^send|^assign|^create|^reject|^approve|^delete|^change/i) {
  const dialog = screen.queryByRole('alertdialog')
  if (!dialog) return false
  const button = within(dialog).getAllByRole('button').find((candidate) => confirmName.test(candidate.textContent.trim()))
  if (!button) throw new Error('Confirmation dialog has no confirming button')
  await user.click(button)
  return true
}

export const pdfFile = (name = 'document.pdf') => new File(['%PDF-1.4 test'], name, { type: 'application/pdf' })

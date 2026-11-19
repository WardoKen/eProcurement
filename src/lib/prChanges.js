import React from 'react'
import { apiFetch } from './apiClient'

// Client side of the PR change history API (GET /api/pr/<id>/changes/).
// See src/components/PRChangeHistory.jsx for the UI.

export const EMPTY_PR_CHANGES = Object.freeze({ changes: {}, events: [], changed_count: 0, original_available: true })

/** Key used by the API for a field: "<item id | 'pr'>:<field>". */
export const prChangeKey = (itemId, field) => `${itemId ?? 'pr'}:${field}`

/**
 * Loads a PR's change history. `enabled` lets callers defer the request
 * (e.g. until a panel is opened). Returns { data, loading, error, reload }.
 */
export function usePrChanges(apiBase, prId, { enabled = true } = {}) {
  const [nonce, setNonce] = React.useState(0)
  const [result, setResult] = React.useState({ prId: null, nonce: -1, data: EMPTY_PR_CHANGES, error: '' })
  const active = Boolean(enabled && prId)

  React.useEffect(() => {
    if (!active) return undefined
    let cancelled = false
    apiFetch(`${String(apiBase || '').replace(/\/$/, '')}/api/pr/${prId}/changes/`)
      .then(async (res) => {
        const body = await res.json().catch(() => null)
        if (!res.ok) throw new Error(body?.message || 'Could not load the change history.')
        return body
      })
      .then((body) => {
        if (!cancelled) setResult({ prId, nonce, data: { ...EMPTY_PR_CHANGES, ...body }, error: '' })
      })
      .catch((error) => {
        if (!cancelled) setResult({ prId, nonce, data: EMPTY_PR_CHANGES, error: error?.message || 'Could not load the change history.' })
      })
    return () => { cancelled = true }
  }, [apiBase, prId, active, nonce])

  const reload = React.useCallback(() => setNonce((value) => value + 1), [])
  const current = active && result.prId === prId
  return {
    data: current ? result.data : EMPTY_PR_CHANGES,
    error: current ? result.error : '',
    loading: active && (result.prId !== prId || result.nonce !== nonce),
    reload,
  }
}

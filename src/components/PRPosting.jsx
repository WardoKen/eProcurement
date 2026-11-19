import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Globe, History } from 'lucide-react'
import { apiFetch } from '../lib/apiClient'
import Modal from './ui/Modal'
import ConfirmDialog from './ui/ConfirmDialog'

// The BAC's explicit posting of a Purchase Request as a procurement
// opportunity (backend: api/pr_posting.py, GET/POST /api/pr/<id>/posting/).
// A posted PR appears on the public Opportunities page and in the supplier
// portal; unposting needs a reason. Every post/unpost is in the history.

const formatWhen = (iso) => {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
}

function UnpostDialog({ minLength, busy, error, onSubmit, onCancel }) {
  const titleId = useId()
  const fieldId = useId()
  const fieldRef = useRef(null)
  const [reason, setReason] = useState('')
  const [touched, setTouched] = useState(false)
  const length = reason.trim().split(/\s+/).filter(Boolean).join(' ').length
  const tooShort = length < minLength

  const submit = (event) => {
    event.preventDefault()
    setTouched(true)
    if (tooShort) { fieldRef.current?.focus(); return }
    onSubmit(reason)
  }

  return (
    <Modal role="alertdialog" labelledBy={titleId} onClose={busy ? undefined : onCancel} dismissible={!busy}
      className="modal-content confirm-dialog" initialFocusRef={fieldRef}>
      <form onSubmit={submit}>
        <div className="modal-header"><h3 id={titleId}>Take Down Posting</h3></div>
        <div className="modal-body">
          <p>The Purchase Request will no longer appear on the public Opportunities page or in the supplier portal.
            RFQs already issued are not affected.</p>
          {error && <div className="alert alert-error" role="alert">{error}</div>}
          <div className="form-group">
            <label htmlFor={fieldId}>Reason (required, at least {minLength} characters)</label>
            <textarea id={fieldId} ref={fieldRef} rows={3} value={reason} disabled={busy}
              onChange={(event) => setReason(event.target.value)}
              aria-invalid={touched && tooShort ? true : undefined} aria-describedby={`${fieldId}-hint`} />
            <p id={`${fieldId}-hint`} className={touched && tooShort ? 'field-error' : 'helper-text'}>
              {touched && tooShort ? `Enter at least ${minLength} characters (${length} so far).` : 'Saved in the posting history with your name and the time.'}
            </p>
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="submit" className="btn btn-danger" disabled={busy} aria-busy={busy || undefined}>
            {busy ? 'Taking down…' : 'Take Down Posting'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function PRPosting({ apiBase, prId, onChange }) {
  const [posting, setPosting] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmingPost, setConfirmingPost] = useState(false)
  const [unposting, setUnposting] = useState(false)
  const base = apiBase.replace(/\/$/, '')

  const apply = useCallback((data) => {
    setPosting(data)
    onChange?.(data)
  }, [onChange])

  useEffect(() => {
    let cancelled = false
    apiFetch(`${base}/api/pr/${prId}/posting/`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('load'))))
      .then((data) => { if (!cancelled) setPosting(data) })
      .catch(() => { if (!cancelled) setLoadError('Posting status could not be loaded.') })
    return () => { cancelled = true }
  }, [base, prId])

  const act = async (body) => {
    setBusy(true)
    setError('')
    try {
      const response = await apiFetch(`${base}/api/pr/${prId}/posting/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'The posting could not be changed.')
      apply(data)
      setConfirmingPost(false)
      setUnposting(false)
    } catch (actError) {
      setError(actError.message)
    } finally {
      setBusy(false)
    }
  }

  if (loadError) return <p className="field-error" role="status">{loadError}</p>
  if (!posting) return <p className="change-muted" aria-busy="true">Loading posting status…</p>

  return (
    <section className="pr-posting" aria-label="Public posting">
      <div className="pr-posting-row">
        <Globe size={16} aria-hidden="true" />
        {posting.is_posted ? (
          <span><span className="status-badge tone-success">Posted</span> {formatWhen(posting.posted_at)}{posting.posted_by ? ` by ${posting.posted_by}` : ''}. Visible on the public Opportunities page and to category-matched suppliers.</span>
        ) : (
          <span><span className="status-badge tone-neutral">Not posted</span> Not visible to the public or to suppliers.</span>
        )}
        {posting.is_posted ? (
          <button type="button" className="btn-sm btn-outline" onClick={() => { setError(''); setUnposting(true) }} disabled={busy}>Take down</button>
        ) : (
          <button type="button" className="btn-sm btn-primary" onClick={() => { setError(''); setConfirmingPost(true) }} disabled={busy || !posting.can_post}>
            Post as opportunity
          </button>
        )}
      </div>
      {!posting.is_posted && posting.post_problem && <p className="helper-text">{posting.post_problem}</p>}
      {error && !unposting && <p className="field-error" role="alert">{error}</p>}
      {posting.history?.length > 0 && (
        <details className="pr-posting-history">
          <summary><History size={14} aria-hidden="true" /> Posting history ({posting.history.length})</summary>
          <ol>
            {posting.history.map((row) => (
              <li key={row.id}>
                <strong>{row.action === 'posted' ? 'Posted' : 'Taken down'}</strong>{' '}
                {formatWhen(row.changed_at)} · {row.changed_by || (row.automatic ? 'System' : 'Unknown')}
                {row.reason && <div className="change-muted">{row.reason}</div>}
              </li>
            ))}
          </ol>
        </details>
      )}
      {confirmingPost && (
        <ConfirmDialog
          title="Post as Procurement Opportunity?"
          confirmLabel="Post"
          busy={busy}
          consequence="It becomes visible to the public on the Opportunities page and to category-matched suppliers in their portal."
          onConfirm={() => act({ action: 'post' })}
          onCancel={() => setConfirmingPost(false)}
        >
          <p>The posting is recorded with your name and the time. You can take it down later with a reason.</p>
          {error && <p className="field-error" role="alert">{error}</p>}
        </ConfirmDialog>
      )}
      {unposting && (
        <UnpostDialog
          minLength={posting.min_reason_length || 10}
          busy={busy}
          error={error}
          onSubmit={(reason) => act({ action: 'unpost', reason })}
          onCancel={() => setUnposting(false)}
        />
      )}
    </section>
  )
}

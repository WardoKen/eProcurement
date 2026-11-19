import { useId, useRef, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import Modal from './ui/Modal'

// Possible contract splitting (backend: api/rfq/procurement_checks.py).
//
// Issuing a Small Value Procurement RFQ returns 409 with
//   { code: 'possible_contract_splitting', message, min_justification_length,
//     splitting: { mode, office_section, category, year, ceiling, this_pr,
//                  related: [{ pr_no, amount, issued_at, rfq_no }],
//                  combined_total, advise_competitive_bidding } }
// when other SVP PRs from the same office, for the same category, this year
// bring the combined amount over the ceiling. The BAC may still issue it, but
// only with a justification, which is recorded on the RFQ.

export const SPLITTING_CODE = 'possible_contract_splitting'

const peso = (value) => `₱${Number(value || 0).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const formatDate = (iso) => {
  if (!iso) return '—'
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleDateString('en-PH', { dateStyle: 'medium' })
}
const normalized = (text) => text.trim().split(/\s+/).filter(Boolean).join(' ')

function SplittingTable({ check, caption }) {
  return (
    <div className="table-shell">
      <table className="enterprise-table splitting-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr><th scope="col">PR No.</th><th scope="col">Issued</th><th scope="col" className="num">Amount ({check.category})</th></tr>
        </thead>
        <tbody>
          {(check.related || []).map((row) => (
            <tr key={row.pr_id || row.pr_no}>
              <td>{row.pr_no}</td>
              <td>{formatDate(row.issued_at)}</td>
              <td className="num">{peso(row.amount)}</td>
            </tr>
          ))}
          {check.this_pr && (
            <tr>
              <td>{check.this_pr.pr_no} <span className="change-muted">(this RFQ)</span></td>
              <td>—</td>
              <td className="num">{peso(check.this_pr.amount)}</td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr><th scope="row" colSpan={2}>Combined total</th><td className="num"><strong>{peso(check.combined_total)}</strong></td></tr>
        </tfoot>
      </table>
    </div>
  )
}

/** Asks the BAC to justify issuing an RFQ flagged as possible splitting. */
export function SplittingJustificationDialog({ prompt, busy = false, onSubmit, onCancel }) {
  const titleId = useId()
  const bodyId = useId()
  const fieldId = useId()
  const fieldRef = useRef(null)
  const [text, setText] = useState('')
  const [touched, setTouched] = useState(false)
  const { splitting: check, message, min_justification_length: minLength = 20 } = prompt
  const length = normalized(text).length
  const tooShort = length < minLength

  const submit = (event) => {
    event.preventDefault()
    setTouched(true)
    if (tooShort) {
      fieldRef.current?.focus()
      return
    }
    onSubmit(normalized(text))
  }

  return (
    <Modal
      role="alertdialog"
      labelledBy={titleId}
      describedBy={bodyId}
      onClose={busy ? undefined : onCancel}
      dismissible={!busy}
      className="modal-content confirm-dialog splitting-dialog"
      initialFocusRef={fieldRef}
    >
      <form onSubmit={submit}>
        <div className="modal-header">
          <h3 id={titleId}>Possible Contract Splitting</h3>
        </div>
        <div className="modal-body" id={bodyId}>
          <p className="confirm-consequence">
            <AlertTriangle size={16} aria-hidden="true" />
            <span>{message}</span>
          </p>
          <SplittingTable check={check} caption={`${check.mode} Purchase Requests from ${check.office_section} for ${check.category} in ${check.year}`} />
          <div className="form-group">
            <label htmlFor={fieldId}>Justification (required, at least {minLength} characters)</label>
            <textarea
              id={fieldId}
              ref={fieldRef}
              rows={4}
              value={text}
              onChange={(event) => setText(event.target.value)}
              aria-invalid={touched && tooShort ? true : undefined}
              aria-describedby={`${fieldId}-hint`}
              disabled={busy}
            />
            <p id={`${fieldId}-hint`} className={touched && tooShort ? 'field-error' : 'helper-text'}>
              {touched && tooShort
                ? `Enter at least ${minLength} characters (${length} so far).`
                : 'Explain why these are separate procurements. It is saved on the RFQ with your name and the time.'}
            </p>
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy} aria-busy={busy || undefined}>
            {busy ? 'Issuing…' : 'Issue with Justification'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

/** The recorded justification, shown on the RFQ record (BAC only). */
export function SplittingReviewNote({ review }) {
  if (!review?.justification) return null
  const check = review.check || {}
  return (
    <div className="alert alert-warning splitting-review">
      <strong>Issued despite possible contract splitting.</strong>
      <p>
        Justified by <strong>{review.justified_by || 'Unknown'}</strong> on{' '}
        {review.justified_at ? new Date(review.justified_at).toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' }) : '—'}:
      </p>
      <blockquote>{review.justification}</blockquote>
      {check.related && (
        <details>
          <summary>Purchase Requests and total at that moment ({peso(check.combined_total)})</summary>
          <SplittingTable check={check} caption="Purchase Requests counted when the justification was given" />
        </details>
      )}
    </div>
  )
}

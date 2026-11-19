import React from 'react'
import { ChevronDown, ChevronRight, History } from 'lucide-react'
import Modal from './ui/Modal'

// Purchase Request change history (BAC edits made during review).
//
// The backend (GET /api/pr/<id>/changes/) returns:
//   changes: { "<item_id|'pr'>:<field>": { label, original, current, history: [{ old, new, by, by_username, by_role, at, reason }] } }
//   events:  [{ type: 'item_added'|'item_removed', item_id, item_label, value, by, by_username, by_role, at, reason }]
//   editors: [{ name, username, role, edit_count, first_at, last_at }]
// `by_username` identifies the account that made the edit.
// compared against the PR as originally uploaded, so a field edited and
// later changed back is not listed. Works in every status, including locked
// (numbered) PRs.

const displayValue = (value) => {
  const text = value == null ? '' : String(value)
  return text.trim() ? text : '(blank)'
}

const formatWhen = (iso) => {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
}

/** Date on one line, time under it, so the Date column stays narrow and aligned. */
const When = ({ iso }) => {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return (
    <time dateTime={iso}>
      <span className="change-when-date">{date.toLocaleDateString('en-PH', { dateStyle: 'medium' })}</span>
      <span className="change-when-time">{date.toLocaleTimeString('en-PH', { timeStyle: 'short' })}</span>
    </time>
  )
}

const itemSummary = (value = {}) => {
  const qty = value.quantity ? `${value.quantity} ${value.unit || ''}`.trim() : ''
  const cost = value.unit_cost ? `@ ${value.unit_cost}` : ''
  return [value.item_description || '(no description)', [qty, cost].filter(Boolean).join(' ')].filter(Boolean).join(' · ')
}

/** "Juan Dela Cruz (@bac-secretariat)" - the account behind an edit. */
const editorLabel = (entry) => {
  if (!entry) return ''
  const name = entry.by ?? entry.name ?? ''
  const username = entry.by_username ?? entry.username ?? ''
  if (!username || username === name) return name || 'Unknown account'
  return `${name} (@${username})`
}

/** Name, account username and role of whoever made an edit. */
export function EditorAccount({ entry }) {
  if (!entry) return <span className="change-muted">Not recorded</span>
  const name = entry.by ?? entry.name
  const username = entry.by_username ?? entry.username
  const role = entry.by_role ?? entry.role
  const active = entry.by_account_active ?? entry.account_active
  return (
    <span className="editor-account">
      <span className="editor-account-name">{name || 'Unknown account'}</span>
      {username && <span className="editor-account-username">@{username}</span>}
      {(role || active === false) && (
        <span className="editor-account-meta">
          {[role, active === false ? 'account inactive' : ''].filter(Boolean).join(' · ')}
        </span>
      )}
    </span>
  )
}

/** "Edited by A (@a), B (@b)" summary of every account that edited the PR. */
export function EditedBySummary({ editors, className = 'pr-edited-by' }) {
  if (!editors?.length) return null
  return (
    <p className={className}>
      <span className="pr-edited-by-label">Edited by</span>{' '}
      {editors.map((editor, index) => (
        <React.Fragment key={editor.username || index}>
          {index > 0 && ', '}
          <strong>{editor.name}</strong>
          {editor.username && editor.username !== editor.name && <span className="editor-account-username"> (@{editor.username})</span>}
          {editor.role && <span className="editor-account-meta"> · {editor.role}</span>}
        </React.Fragment>
      ))}
    </p>
  )
}

/**
 * Wraps a PR field or item cell. When `change` is set (the field differs from
 * the original upload) it gets the edited highlight and an "Edited" badge whose
 * tooltip shows the original value and the account that last changed it.
 */
export function FieldValue({ change, children, full = false, inline = false, className = '' }) {
  const tooltipId = React.useId()
  if (!change) {
    if (!full && !className) return children
    return <div className={['field-value', full ? 'field-value-full' : '', className].filter(Boolean).join(' ')}>{children}</div>
  }
  const Tag = inline ? 'span' : 'div'
  const original = displayValue(change.original)
  const last = change.history?.[change.history.length - 1]
  return (
    <Tag className={['field-value', 'is-edited', inline ? 'field-value-inline' : '', full ? 'field-value-full' : '', className].filter(Boolean).join(' ')}>
      {children}
      <span className="field-value-badge" tabIndex={0} aria-describedby={tooltipId}>
        Edited
        <span id={tooltipId} role="tooltip" className="field-value-tooltip">
          <span className="field-value-tooltip-label">Original (from upload)</span>
          {original}
          <span className="field-value-tooltip-label field-value-tooltip-by">Changed by</span>
          {last ? `${editorLabel(last)}${last.by_role ? ` · ${last.by_role}` : ''}, ${formatWhen(last.at)}` : 'Not recorded (changed outside the review form)'}
        </span>
      </span>
    </Tag>
  )
}

/** "View changes (n)" - renders nothing when there are no changes. */
export function ViewChangesButton({ count, onClick, className = 'btn-sm btn-secondary' }) {
  if (!count) return null
  return (
    <button type="button" className={`${className} view-changes-btn`} onClick={onClick}>
      <History size={14} aria-hidden="true" />
      View changes ({count})
    </button>
  )
}

const ChangeRow = ({ change }) => {
  const [open, setOpen] = React.useState(false)
  const steps = change.history || []
  const last = steps[steps.length - 1]
  const expandable = steps.length > 1
  return (
    <>
      <tr className={open ? 'is-expanded' : undefined}>
        <td className="change-field">
          {expandable ? (
            <button type="button" className="change-row-toggle" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
              {open ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
              <span>{change.label}</span>
            </button>
          ) : (
            <span className="change-field-label">{change.label}</span>
          )}
          {change.item_label && <small className="change-item-label">{change.item_label}</small>}
          {expandable && <small className="change-step-count">{steps.length} edits</small>}
        </td>
        <td className="change-original">{displayValue(change.original)}</td>
        <td className="change-current">{displayValue(change.current)}</td>
        <td><EditorAccount entry={last} /></td>
        <td className="change-when"><When iso={last?.at} /></td>
        <td>{last ? last.reason : <span className="change-muted">Changed outside the review form</span>}</td>
      </tr>
      {open && steps.map((step, index) => (
        <tr key={`${step.at}-${index}`} className="change-step-row">
          <td className="change-field"><span className="change-step-label">Edit {index + 1}</span></td>
          <td>{displayValue(step.old)}</td>
          <td>{displayValue(step.new)}</td>
          <td><EditorAccount entry={step} /></td>
          <td className="change-when"><When iso={step.at} /></td>
          <td>{step.reason}</td>
        </tr>
      ))}
    </>
  )
}

const EventRow = ({ event }) => {
  const added = event.type === 'item_added'
  return (
    <tr className={added ? 'change-event-added' : 'change-event-removed'}>
      <td className="change-field">
        <span className={`status-badge ${added ? 'tone-success' : 'tone-danger'}`}>{added ? 'Item added' : 'Item removed'}</span>
      </td>
      <td>{added ? <span className="change-muted">Not in upload</span> : itemSummary(event.value)}</td>
      <td>{added ? itemSummary(event.value) : <span className="change-muted">Removed</span>}</td>
      <td><EditorAccount entry={event} /></td>
      <td className="change-when"><When iso={event.at} /></td>
      <td>{event.reason}</td>
    </tr>
  )
}

/** The change table: Field | Original (from upload) | Current | Edited by | Date | Reason. */
export function ChangeHistoryTable({ data }) {
  const changes = Object.entries(data?.changes || {})
  const events = data?.events || []
  if (!changes.length && !events.length) {
    return <p className="change-muted">No fields differ from the original upload.</p>
  }
  // Interleave field changes and item events by their latest timestamp.
  const rows = [
    ...changes.map(([key, change]) => ({ key, at: change.history?.at(-1)?.at || '', node: <ChangeRow key={key} change={change} /> })),
    ...events.map((event, index) => ({ key: `event-${index}`, at: event.at, node: <EventRow key={`event-${index}`} event={event} /> })),
  ].sort((a, b) => String(a.at).localeCompare(String(b.at)))
  return (
    <div className="table-shell change-history-shell" tabIndex={0} role="region" aria-label="Change history">
      <table className="enterprise-table change-history-table">
        <colgroup>
          <col className="col-field" />
          <col className="col-original" />
          <col className="col-current" />
          <col className="col-editor" />
          <col className="col-date" />
          <col className="col-reason" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" className="change-field">Field</th>
            <th scope="col">Original (from upload)</th>
            <th scope="col">Current</th>
            <th scope="col">Edited by (account)</th>
            <th scope="col">Date</th>
            <th scope="col">Reason</th>
          </tr>
        </thead>
        <tbody>{rows.map((row) => row.node)}</tbody>
      </table>
    </div>
  )
}

export function ChangeHistoryModal({ data, prLabel, onClose }) {
  return (
    <Modal labelledBy="pr-change-history-title" className="modal-content change-history-modal" onClose={onClose}>
      <div className="modal-header">
        <div className="pr-sheet-title">
          <h3 id="pr-change-history-title">Change history · {prLabel}</h3>
          <p className="pr-sheet-meta">
            {data?.locked ? 'Locked: PR number assigned. Read-only record of BAC edits.' : 'Edits made by the BAC during review, compared with the original upload.'}
          </p>
        </div>
        <button type="button" className="modal-close" onClick={onClose} aria-label="Close change history">×</button>
      </div>
      <div className="modal-body">
        <EditedBySummary editors={data?.editors} />
        {data?.original_available === false && (
          <p className="change-history-note">
            This Purchase Request was uploaded before change history was recorded, so the original values shown are the
            values from before the first recorded edit.
          </p>
        )}
        <ChangeHistoryTable data={data} />
      </div>
      <div className="modal-actions">
        <button type="button" className="btn btn-secondary" onClick={onClose}>Close</button>
      </div>
    </Modal>
  )
}

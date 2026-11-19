import { History } from 'lucide-react'

// Supplier account change log, shown in the BAC's supplier review.
//
// The backend (GET /api/suppliers/<id>/profile/ as admin, `change_log`) returns
// rows newest first:
//   { id, event_type, field_name, field_label, old_value, new_value, note,
//     changed_by, changed_by_role, changed_at }
// event_type: field_edit | categories_changed | document_resubmitted | status_changed.
// Rows written by one save share `changed_at`, so they are shown as one entry.
// Entries after the BAC's most recent decision are marked "New" - that is what
// the BAC has not reviewed yet.

const displayValue = (value) => (value && String(value).trim() ? value : '(blank)')

const formatWhen = (iso) => {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' })
}

const actorLabel = (row) => {
  const role = row.changed_by_role === 'admin' ? 'BAC' : row.changed_by_role === 'supplier' ? 'Supplier' : ''
  if (row.changed_by && role) return `${row.changed_by} (${role})`
  return row.changed_by || role || 'Unknown'
}

const isBacDecision = (row) => row.event_type === 'status_changed' && row.changed_by_role === 'admin'

// Consecutive rows from one save (same time and actor) form one entry.
const groupEntries = (rows) => {
  const entries = []
  for (const row of rows) {
    const last = entries[entries.length - 1]
    if (last && last.changed_at === row.changed_at && last.changed_by === row.changed_by) {
      last.rows.push(row)
    } else {
      entries.push({ key: row.id, changed_at: row.changed_at, changed_by: row.changed_by, actor: actorLabel(row), rows: [row] })
    }
  }
  return entries
}

const ChangeLine = ({ row, documentLabel }) => {
  if (row.event_type === 'status_changed') {
    return (
      <li className="supplier-log-line">
        <span className="supplier-log-field">Status</span>
        <span className="supplier-log-values">
          <span className="supplier-log-old">{displayValue(row.old_value)}</span>
          <span aria-hidden="true"> → </span><span className="sr-only"> changed to </span>
          <span className="supplier-log-new">{displayValue(row.new_value)}</span>
        </span>
        {row.note && <span className="supplier-log-note">{isBacDecision(row) ? `Remarks: ${row.note}` : row.note}</span>}
      </li>
    )
  }
  if (row.event_type === 'document_resubmitted') {
    return (
      <li className="supplier-log-line">
        <span className="supplier-log-field">Document resubmitted: {documentLabel(row.field_name)}</span>
        <span className="supplier-log-values">
          {row.old_value && <><span className="supplier-log-old">{row.old_value}</span><span aria-hidden="true"> → </span><span className="sr-only"> replaced by </span></>}
          <span className="supplier-log-new">{displayValue(row.new_value)}</span>
        </span>
      </li>
    )
  }
  return (
    <li className="supplier-log-line">
      <span className="supplier-log-field">{row.field_label}</span>
      {row.event_type === 'categories_changed' && row.note ? (
        <span className="supplier-log-values supplier-log-new">{row.note}</span>
      ) : (
        <span className="supplier-log-values">
          <span className="supplier-log-old">{displayValue(row.old_value)}</span>
          <span aria-hidden="true"> → </span><span className="sr-only"> changed to </span>
          <span className="supplier-log-new">{displayValue(row.new_value)}</span>
        </span>
      )}
    </li>
  )
}

export default function SupplierChangeLog({ rows = [], documentLabel = (key) => key }) {
  const entries = groupEntries(rows)
  // Rows are newest first: everything before the latest BAC decision is new.
  const lastDecisionIndex = rows.findIndex(isBacDecision)
  const newRowIds = new Set((lastDecisionIndex === -1 ? rows : rows.slice(0, lastDecisionIndex)).map((row) => row.id))
  const newCount = entries.filter((entry) => entry.rows.some((row) => newRowIds.has(row.id) && !isBacDecision(row))).length

  return (
    <div className="supplier-detail-panel supplier-change-log">
      <div className="supplier-category-heading">
        <div>
          <div className="supplier-panel-title">Change Log</div>
          <div className="supplier-subtext">
            Profile edits, category changes, document resubmissions and status decisions, newest first.
          </div>
        </div>
        {newCount > 0 && <span className="status-badge status-review">{newCount} new since last BAC decision</span>}
      </div>
      {entries.length === 0 ? (
        <div className="supplier-subtext">
          <History size={14} aria-hidden="true" /> No changes recorded yet.
        </div>
      ) : (
        <ol className="supplier-log-list">
          {entries.map((entry) => {
            const isNew = entry.rows.some((row) => newRowIds.has(row.id)) && !entry.rows.some(isBacDecision)
            return (
              <li key={entry.key} className={`supplier-log-entry${isNew ? ' is-new' : ''}`}>
                <div className="supplier-log-meta">
                  <time dateTime={entry.changed_at}>{formatWhen(entry.changed_at)}</time>
                  <span> · {entry.actor}</span>
                  {isNew && <span className="supplier-log-new-badge">New</span>}
                </div>
                <ul className="supplier-log-lines">
                  {entry.rows.map((row) => <ChangeLine key={row.id} row={row} documentLabel={documentLabel} />)}
                </ul>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

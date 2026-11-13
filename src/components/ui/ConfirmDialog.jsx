import { useId, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'
import Modal from './Modal'

// Confirmation step for irreversible actions. `consequence` states in plain
// language what will happen and what can't be undone. Focus starts on Cancel,
// so a stray Enter never confirms.
export default function ConfirmDialog({
  title,
  children,
  consequence,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'primary',
  busy = false,
  busyLabel,
  onConfirm,
  onCancel,
}) {
  const titleId = useId()
  const bodyId = useId()
  const cancelRef = useRef(null)

  return (
    <Modal
      role="alertdialog"
      labelledBy={titleId}
      describedBy={bodyId}
      onClose={busy ? undefined : onCancel}
      dismissible={!busy}
      className={`modal-content confirm-dialog tone-${tone}`}
      initialFocusRef={cancelRef}
    >
      <div className="modal-header">
        <h3 id={titleId}>{title}</h3>
      </div>
      <div className="modal-body" id={bodyId}>
        {children}
        {consequence && (
          <p className="confirm-consequence">
            <AlertTriangle size={16} aria-hidden="true" />
            <span>{consequence}</span>
          </p>
        )}
      </div>
      <div className="modal-actions">
        <button ref={cancelRef} type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </button>
        <button
          type="button"
          className={`btn ${tone === 'danger' ? 'btn-danger' : 'btn-primary'}`}
          onClick={onConfirm}
          disabled={busy}
          aria-busy={busy || undefined}
        >
          {busy ? (busyLabel || `${confirmLabel}…`) : confirmLabel}
        </button>
      </div>
    </Modal>
  )
}

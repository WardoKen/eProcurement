import { useEffect, useRef, useState } from 'react'
import {
  Plus,
  Save,
  LoaderCircle,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from 'lucide-react'

import { apiFetch } from '../lib/apiClient'
import { UPLOAD_KINDS, acceptAttr, acceptedTypesLabel, fileTypeLabel, formatFileSize, validateFile } from '../lib/fileValidation'

const normalizeNumberInput = (value) => (value || '').toString().replace(/,/g, '').trim()

// Textarea that grows with its content so the visible box always matches what
// has been typed. Modern browsers get this natively via `field-sizing: content`
// (see index.css); this keeps the rest in sync and caps the height at `maxRows`.
function AutoGrowTextarea({ value, maxRows = 12, className, ...rest }) {
  const ref = useRef(null)

  const resize = () => {
    const el = ref.current
    if (!el || CSS.supports?.('field-sizing', 'content')) return
    const style = window.getComputedStyle(el)
    const lineHeight = parseFloat(style.lineHeight) || 20
    const verticalPadding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
    const verticalBorder = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth)
    const maxHeight = lineHeight * maxRows + verticalPadding + verticalBorder
    el.style.height = 'auto'
    const nextHeight = Math.min(el.scrollHeight + verticalBorder, maxHeight)
    el.style.height = `${nextHeight}px`
    el.style.overflowY = el.scrollHeight + verticalBorder > maxHeight ? 'auto' : 'hidden'
  }

  useEffect(() => {
    resize()
    const onResize = () => resize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  return (
    <textarea
      {...rest}
      ref={ref}
      className={className}
      value={value}
      onInput={resize}
      rows={1}
    />
  )
}

const getCurrentDate = () => {
  const date = new Date()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

const PR_NUMBER_PATTERN = /^\d{4}-\d{2}-\d{3}$/

function normalizeOcrDate(value, rawText = '') {
  const source = String(value || '').trim() || String(rawText || '')
  const match = source.match(/\b(\d{1,2})\s*[\/-]\s*(\d{1,2})\s*[\/-]\s*(\d{4})\b/)
  if (!match) return String(value || '').trim()
  const month = Number(match[1])
  const day = Number(match[2])
  const year = Number(match[3])
  if (month < 1 || month > 12 || day < 1 || day > 31) return ''
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

const FieldShell = ({
  id,
  label,
  value,
  onChange,
  type = 'text',
  helper,
  full,
  isTextarea,
  editedByUser,
}) => {
  const wrapperClass = [
    'floating-field',
    full ? 'full' : '',
    editedByUser ? 'manual-edited' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={wrapperClass}>
      {isTextarea ? (
        <textarea id={id} value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder=" " rows={4} />
      ) : (
        <input id={id} value={value || ''} onChange={(e) => onChange(e.target.value)} type={type} placeholder=" " />
      )}
      <label htmlFor={id}>{label}</label>
      {helper && <small>{helper}</small>}
      {editedByUser && (
        <div className="field-flags" aria-label="Field indicators">
          {editedByUser && <span className="field-flag manual">Edited</span>}
        </div>
      )}
    </div>
  )
}

// Maps each signatory block to the key used by the backend signature detector.
const SIGNATURE_KEY_BY_BLOCK = {
  requested_by_name: 'requested_by',
  funds_available_name: 'funds_available',
  approved_by_name: 'approved_by',
  twg_name: 'twg',
}

const SIGNATURE_STATUS_META = {
  present: { label: 'With Signature', className: 'sig-status-present', Icon: CheckCircle },
  absent: { label: 'Without Signature', className: 'sig-status-absent', Icon: XCircle },
  unverifiable: { label: 'Unable to Verify', className: 'sig-status-unverifiable', Icon: AlertTriangle },
}

const signatureStatusMeta = (state) => SIGNATURE_STATUS_META[state] || SIGNATURE_STATUS_META.unverifiable

const SignatureStatusChip = ({ state }) => {
  const meta = signatureStatusMeta(state)
  const { Icon } = meta
  return (
    <span className={`sig-status-chip ${meta.className}`}>
      <Icon size={13} aria-hidden="true" />
      {meta.label}
    </span>
  )
}

const SignatureBlock = ({ title, designationKey, nameKey, fields, onFieldChange, editedFieldKeys, signatureState }) => (
  <section className={`signature-card ${signatureState ? signatureStatusMeta(signatureState.state).className : ''}`}>
    <div className="signature-card-head">
      <h4>
        {title}
        {signatureState && !signatureState.required && <span className="sig-optional-note"> (optional)</span>}
      </h4>
      {signatureState
        ? <SignatureStatusChip state={signatureState.state} />
        : <span className="sig-status-chip sig-status-pending">Not checked</span>}
    </div>
    <FieldShell
      id={designationKey}
      label="Designation"
      value={fields[designationKey]}
      onChange={(value) => onFieldChange(designationKey, value)}
      editedByUser={editedFieldKeys.has(designationKey)}
    />
    <FieldShell
      id={nameKey}
      label="Name"
      value={fields[nameKey]}
      onChange={(value) => onFieldChange(nameKey, value)}
      editedByUser={editedFieldKeys.has(nameKey)}
    />
  </section>
)

const SignatureValidationPanel = ({ validation, onRecheck, rechecking, hasDocument }) => {
  const summary = validation?.summary
  const signatories = validation?.signatories || {}
  const order = ['requested_by', 'funds_available', 'approved_by', 'twg']
  const rows = order.map((key) => signatories[key]).filter(Boolean)

  const statusTone = summary?.status === 'complete'
    ? 'sig-panel-complete'
    : summary?.status === 'unverifiable'
      ? 'sig-panel-unverifiable'
      : 'sig-panel-incomplete'

  return (
    <section className={`card signature-validation-panel ${statusTone}`}>
      <div className="signature-validation-head">
        <h4>Signature Validation</h4>
        <button
          type="button"
          className="btn btn-outline btn-sm"
          onClick={onRecheck}
          disabled={rechecking || !hasDocument}
        >
          {rechecking ? <LoaderCircle size={14} className="spin" /> : <RefreshCw size={14} />}
          {rechecking ? 'Rechecking…' : 'Recheck Signatures'}
        </button>
      </div>

      {!validation ? (
        <p className="helper-text">Upload a Purchase Request to check its signatures.</p>
      ) : (
        <>
          <ul className="signature-validation-list">
            {rows.map((row) => {
              const meta = signatureStatusMeta(row.state)
              const { Icon } = meta
              return (
                <li key={row.key} className={meta.className}>
                  <Icon size={16} aria-hidden="true" />
                  <div>
                    <strong>{row.label}{!row.required ? ' (optional)' : ''}</strong>
                    <span>
                      {row.name ? row.name : 'Name not extracted'}
                      {' — '}
                      {row.state === 'present' && 'signature detected'}
                      {row.state === 'absent' && 'no signature detected'}
                      {row.state === 'unverifiable' && 'signature could not be verified'}
                    </span>
                  </div>
                </li>
              )
            })}
          </ul>

          {summary && (
            <div className="signature-validation-summary">
              <strong>
                {summary.required_detected} of {summary.required_total} required signatures detected
              </strong>
              <p>{summary.message}</p>
              {summary.missing_signatures?.length > 0 && (
                <p className="sig-missing">
                  Missing signatures:
                  <span> {summary.missing_signatures.join(', ')}</span>
                </p>
              )}
              {summary.unverifiable_signatures?.length > 0 && (
                <p className="sig-missing">
                  Could not verify:
                  <span> {summary.unverifiable_signatures.join(', ')}</span>
                </p>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}

const DECLARATION_POINTS = [
  'The information submitted is true, accurate, and complete to the best of my knowledge.',
  'This Purchase Request represents a legitimate procurement requirement of the requesting office/unit and is not fictitious or submitted for an unauthorized purpose.',
  'The uploaded Purchase Request is the correct document intended for this transaction and has not been intentionally altered or falsified.',
  'The names and signatures appearing in the Purchase Request belong to the respective authorized signatories, to the best of my knowledge, and I have no knowledge of any unauthorized or falsified signature.',
  'I understand that the Purchase Request may be reviewed and validated by the appropriate university personnel before proceeding to the succeeding procurement stages.',
  'I accept responsibility for the accuracy and authenticity of the information and document I have submitted.',
]

const SubmissionCheckPanel = ({ checks }) => (
  <section className="card submission-check-panel">
    <h4>Submission Check</h4>
    <ul className="submission-check-list">
      {checks.map((check) => (
        <li key={check.key} className={check.ok ? 'submission-check-ok' : 'submission-check-fail'}>
          {check.ok
            ? <CheckCircle size={16} aria-hidden="true" />
            : <XCircle size={16} aria-hidden="true" />}
          <span>{check.label}</span>
        </li>
      ))}
    </ul>
    {checks.some((c) => !c.ok) && (
      <p className="submission-check-note">
        <AlertTriangle size={14} aria-hidden="true" />
        Please resolve the items above before submitting.
      </p>
    )}
  </section>
)

const SubmissionDeclaration = ({ acknowledged, onToggle, checksPass }) => (
  <section className="card submission-declaration">
    <h4>Purchase Request Submission Declaration</h4>
    <p className="submission-declaration-lead">By submitting this Purchase Request, I certify and acknowledge that:</p>
    <ol className="submission-declaration-points">
      {DECLARATION_POINTS.map((point, index) => <li key={index}>{point}</li>)}
    </ol>
    <label className="submission-declaration-ack">
      <input
        type="checkbox"
        checked={acknowledged}
        onChange={(event) => onToggle(event.target.checked)}
      />
      <span>I have read and understood this declaration.</span>
    </label>
    {acknowledged && !checksPass && (
      <p className="helper-text" style={{ margin: '6px 0 0' }}>
        The submission checks above must also pass before the Purchase Request can be saved.
      </p>
    )}
  </section>
)

export default function DragDropUpload({ apiBase = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'), onSaved = null, reviewOnly = false, submittedBy = '' }) {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState(false)
  const [uploadSuccessModalOpen, setUploadSuccessModalOpen] = useState(false)
  const [saveSuccessModalOpen, setSaveSuccessModalOpen] = useState(false)
  const [savedPr, setSavedPr] = useState(null)
  const [fields, setFields] = useState({})
  const [rawText, setRawText] = useState('')
  const [editedFieldKeys, setEditedFieldKeys] = useState(new Set())
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [signatureValidation, setSignatureValidation] = useState(null)
  const [rechecking, setRechecking] = useState(false)
  const [saveBlockedMessage, setSaveBlockedMessage] = useState('')
  const [declarationAcknowledged, setDeclarationAcknowledged] = useState(false)
  const [numberingMode, setNumberingMode] = useState('automatic')
  const [suggestedPrNumber, setSuggestedPrNumber] = useState('')
  const [customPrNumber, setCustomPrNumber] = useState('')
  const [numberError, setNumberError] = useState('')
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [pendingDeleteIndex, setPendingDeleteIndex] = useState(null)
  const [removingRowIndex, setRemovingRowIndex] = useState(null)

  const fileInputRef = useRef(null)
  const [previewUrl, setPreviewUrl] = useState('')

  // The document preview is purely a client-side convenience - it reads the
  // already-selected File object directly, no extra request or backend
  // change needed. Revoke the previous object URL whenever it changes so we
  // don't leak memory across repeated uploads.
  useEffect(() => {
    if (!file) {
      setPreviewUrl('')
      return undefined
    }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  useEffect(() => {
    let cancelled = false
    apiFetch(`${apiBase.replace(/\/$/, '')}/api/pr/next-number/`)
      .then((res) => {
        if (!res.ok) throw new Error('Unable to load PR number preview')
        return res.json()
      })
      .then((data) => {
        if (!cancelled) setSuggestedPrNumber(data?.pr_no || '')
      })
      .catch(() => {
        if (!cancelled) setSuggestedPrNumber('')
      })

    return () => {
      cancelled = true
    }
  }, [apiBase])

  useEffect(() => {
    if (!hasUnsavedChanges) return undefined

    const handleBeforeUnload = (event) => {
      event.preventDefault()
      event.returnValue = 'You have unsaved changes. Do you want to leave without saving?'
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedChanges])

  function markEditedField(key) {
    setEditedFieldKeys((prev) => {
      const next = new Set(prev)
      next.add(key)
      return next
    })
    setHasUnsavedChanges(true)
  }

  function onFieldChange(key, value) {
    markEditedField(key)
    setFields((prev) => ({ ...prev, [key]: value }))
  }

  function normalizeLineItems(items) {
    if (!Array.isArray(items)) return []

    return items.map((item) => {
      const quantity = parseFloat(normalizeNumberInput(item.quantity || '0')) || 0
      const unitCost = parseFloat(normalizeNumberInput(item.unitCost || '0')) || 0
      const computedTotal = quantity * unitCost
      const nextTotal = Number.isFinite(computedTotal) ? computedTotal.toFixed(2) : ''

      return {
        ...item,
        quantity: item.quantity ?? '',
        unitCost: item.unitCost ?? '',
        totalCost: nextTotal,
      }
    })
  }

  function setLineItems(nextItems, { markDirty = true } = {}) {
    const normalizedItems = normalizeLineItems(nextItems)
    setFields((prev) => ({ ...prev, lineItems: normalizedItems }))

    if (markDirty) {
      setHasUnsavedChanges(true)
    }
  }

  function openDeleteModal(index) {
    setPendingDeleteIndex(index)
    setDeleteModalOpen(true)
  }

  function closeDeleteModal() {
    setDeleteModalOpen(false)
    setPendingDeleteIndex(null)
    setRemovingRowIndex(null)
  }

  function confirmDeleteItem() {
    if (pendingDeleteIndex === null || pendingDeleteIndex === undefined) return

    const currentItems = Array.isArray(fields.lineItems) ? fields.lineItems : []
    const nextItems = currentItems.filter((_, idx) => idx !== pendingDeleteIndex)

    setRemovingRowIndex(pendingDeleteIndex)
    window.setTimeout(() => {
      setLineItems(nextItems)
      setRemovingRowIndex(null)
      setDeleteModalOpen(false)
      setPendingDeleteIndex(null)
    }, 180)
  }

  function handleFile(nextFile) {
    const check = validateFile(nextFile, UPLOAD_KINDS.PR)
    if (!check.ok) {
      setFile(null)
      setUploadMessage(check.error)
      setUploadSuccess(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setFile(nextFile)
    setFields({})
    setRawText('')
    setUploadMessage('')
    setUploadSuccess(false)
    setUploadSuccessModalOpen(false)
    setEditedFieldKeys(new Set())
    setHasUnsavedChanges(false)
    setCustomPrNumber('')
    setNumberError('')
    // Signature results and the declaration always belong to a specific
    // uploaded document - never carry them across a new upload.
    setSignatureValidation(null)
    setSaveBlockedMessage('')
    setDeclarationAcknowledged(false)
  }

  function onChooseClick() {
    fileInputRef.current?.click()
  }

  function onFileInputChange(e) {
    const selected = e.target.files && e.target.files[0]
    if (selected) handleFile(selected)
  }

  function onDrop(e) {
    e.preventDefault()
    setDragOver(false)
    const selected = e.dataTransfer.files && e.dataTransfer.files[0]
    if (selected) handleFile(selected)
  }

  async function uploadFile(nextFile) {
    const check = validateFile(nextFile, UPLOAD_KINDS.PR)
    if (!check.ok) {
      setUploadMessage(check.error)
      return
    }

    setUploading(true)
    setUploadMessage('')
    setUploadSuccess(false)

    try {
      const form = new FormData()
      form.append('file', nextFile)
      const res = await apiFetch(`${apiBase}/api/upload/`, { method: 'POST', body: form })

      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.message || 'Upload failed')
      }

      const data = await res.json()
      const incoming = data?.fields || {}
      const extractedFields = {
        ...incoming,
        date: normalizeOcrDate(incoming.date, data?.rawText) || getCurrentDate(),
      }
      const requested = (incoming.requested_items || []).map((item) => ({
        stockPropertyNumber: item.stock_no || '',
        unit: item.unit || '',
        description: item.description || '',
        quantity: item.quantity || '',
        unitCost: normalizeNumberInput(item.unit_cost),
        totalCost: normalizeNumberInput(item.total_cost),
      }))

      setFields({ ...extractedFields, sourceFilename: data?.filename || '', lineItems: normalizeLineItems(requested) })
      setRawText(data?.rawText || '')
      setUploadMessage(`Uploaded: ${data?.filename || nextFile.name}`)
      setSignatureValidation(data?.signature_validation || null)
      setSaveBlockedMessage('')

      setUploadSuccess(true)
      setUploadSuccessModalOpen(true)
      setHasUnsavedChanges(false)
    } catch (err) {
      setUploadMessage(err?.message || 'Upload failed')
      setUploadSuccess(false)
    } finally {
      setUploading(false)
    }
  }

  function removeFile() {
    setFile(null)
    setFields({})
    setRawText('')
    setUploadMessage('')
    setUploadSuccess(false)
    setUploadSuccessModalOpen(false)
    setEditedFieldKeys(new Set())
    setHasUnsavedChanges(false)
    setSignatureValidation(null)
    setSaveBlockedMessage('')
    setDeclarationAcknowledged(false)

    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function recheckSignatures() {
    const sourceFilename = fields.sourceFilename || ''
    if (!sourceFilename) {
      setSaveBlockedMessage('No uploaded document is associated with this form yet. Upload the PR first.')
      return
    }
    setRechecking(true)
    setSaveBlockedMessage('')
    try {
      const res = await apiFetch(`${apiBase}/api/pr/recheck-signatures/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: sourceFilename, fields }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) {
        const detail = data?.message || data?.error
        throw new Error(
          detail
            ? `Signature recheck failed: ${detail}`
            : `Signature recheck failed (HTTP ${res.status}). Make sure the backend is running the latest code.`,
        )
      }
      if (data?.signature_validation) {
        setSignatureValidation(data.signature_validation)
      } else {
        throw new Error('Signature recheck returned no result.')
      }
    } catch (err) {
      setSaveBlockedMessage(err?.message || 'Signature recheck failed')
    } finally {
      setRechecking(false)
    }
  }

  async function savePurchaseRequest() {
    if (numberingMode === 'custom' && !PR_NUMBER_PATTERN.test(customPrNumber.trim())) {
      setNumberError('Use the format YYYY-MM-NNN.')
      return
    }
    if (!systemChecksPass) {
      setSaveBlockedMessage('Please resolve the submission checks before submitting the Purchase Request.')
      return
    }
    if (!declarationAcknowledged) {
      setSaveBlockedMessage('Please acknowledge the Purchase Request Submission Declaration before submitting.')
      return
    }

    setSaving(true)
    setSaveBlockedMessage('')

    try {
      const items = (fields.lineItems || []).map((it) => {
        const qty = parseFloat(normalizeNumberInput(it.quantity || '0')) || 0
        const unit = parseFloat(normalizeNumberInput(it.unitCost || '0')) || 0
        const total = qty * unit
        return {
          stock_no: it.stockPropertyNumber || '',
          unit: it.unit || '',
          description: it.description || '',
          quantity: qty,
          unit_cost: unit,
          total_cost: total,
        }
      })

      const grand = items.reduce((sum, item) => sum + (parseFloat(item.total_cost) || 0), 0)

      const payload = {
        fields: {
          ...fields,
          prNumberMode: numberingMode,
          prNumber: numberingMode === 'custom' ? customPrNumber.trim() : '',
          reviewOnly,
          sourceFilename: fields.sourceFilename || '',
          submittedBy,
          requested_items: items,
          grand_total: grand.toFixed(2),
          declaration_acknowledged: declarationAcknowledged === true,
        },
      }

      const res = await apiFetch(`${apiBase}/api/pr/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => null)
        if (err?.signature_validation) {
          setSignatureValidation(err.signature_validation)
        }
        if (err?.declaration_required) {
          setSaveBlockedMessage(err.error || 'Please acknowledge the Purchase Request Submission Declaration before submitting.')
          return
        }
        if (err?.error && (err.missing_signatures || err.unverifiable_signatures)) {
          const missing = err.missing_signatures || []
          setSaveBlockedMessage(
            missing.length
              ? `Purchase Request cannot be saved yet. Missing signatures: ${missing.join(', ')}.`
              : err.error,
          )
          return
        }
        window.alert(err?.message || err?.error || 'Failed to save PR')
        return
      }

      const result = await res.json()
      setFields((prev) => ({ ...prev, prNumber: result.pr_no || prev.prNumber }))
      setHasUnsavedChanges(false)
      setNumberError('')
      setSavedPr(result)
      setSaveSuccessModalOpen(true)
    } catch {
      window.alert('Network error while saving PR')
    } finally {
      setSaving(false)
    }
  }

  const hasExtractedData = Object.keys(fields).length > 0
  // Block the save only when we have a validation result that says the required
  // signatures are not all present. If the check produced no result at all, let
  // the backend guard be the gate (it re-verifies on save) rather than trapping
  // the user behind a permanently-disabled button.
  const signaturesChecked = Boolean(signatureValidation?.summary)
  const signaturesComplete = !signaturesChecked || signatureValidation.summary.can_save === true

  const lineItems = Array.isArray(fields.lineItems) ? fields.lineItems : []
  const requiredInfoComplete = Boolean(
    (fields.entityName || '').trim()
    && lineItems.length > 0
    && lineItems.every((item) => (item.description || '').trim()),
  )
  const documentAccepted = Boolean(fields.sourceFilename)
  const sigSummary = signatureValidation?.summary
  const systemChecks = [
    { key: 'info', label: 'Required information completed', ok: requiredInfoComplete },
    { key: 'file', label: 'Supported document accepted', ok: documentAccepted },
    {
      key: 'sig',
      label: sigSummary
        ? `${sigSummary.required_detected} of ${sigSummary.required_total} required signatures detected`
        : 'Required signatures detected',
      ok: signaturesComplete && (!sigSummary || sigSummary.can_save === true),
    },
  ]
  const systemChecksPass = systemChecks.every((check) => check.ok)
  const canSubmit = systemChecksPass && declarationAcknowledged && !saving

  const signatureBlockState = (nameKey) => {
    const key = SIGNATURE_KEY_BY_BLOCK[nameKey]
    return signatureValidation?.signatories?.[key] || null
  }

  return (
    <div className="pr-upload-page">
      <div className="pr-upload-intro card">
        <div>
          <h2>
            <Upload size={20} />
            Purchase Request Upload Workspace
          </h2>
          <p>Upload a PR file, review OCR output, and save validated details without leaving the page.</p>
        </div>

        <div className="dropzone card"
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => {
            if (!file) onChooseClick()
          }}
          role="button"
          tabIndex={0}
          aria-label="Upload Purchase Request file"
          data-drag={dragOver ? 'true' : 'false'}
        >
          <input ref={fileInputRef} type="file" accept={acceptAttr(UPLOAD_KINDS.PR)} style={{ display: 'none' }} onChange={onFileInputChange} />

          {!file && (
            <div className="dropzone-inner">
              <Upload size={36} />
              <strong>Drop PR document here</strong>
              <span>Click to browse local files.</span>
              <span className="dropzone-accepted">Accepted file types: {acceptedTypesLabel(UPLOAD_KINDS.PR)}</span>
            </div>
          )}

          {file && (
            <div className="dropzone-file-row">
              <div className="file-meta">
                <CheckCircle size={18} className="file-meta-ok" />
                <div>
                  <strong>{file.name}</strong>
                  <span>{fileTypeLabel(file)} • {formatFileSize(file.size)}</span>
                </div>
              </div>

              <div className="file-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={(e) => {
                    e.stopPropagation()
                    uploadFile(file)
                  }}
                  disabled={uploading || uploadSuccess}
                >
                  {uploading ? <LoaderCircle size={16} className="spin" /> : <Upload size={16} />}
                  {uploading ? 'Uploading...' : uploadSuccess ? 'Uploaded' : 'Confirm Upload'}
                </button>

                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeFile()
                  }}
                  disabled={uploading}
                >
                  <Trash2 size={16} />
                  Remove
                </button>
              </div>
            </div>
          )}
        </div>

        {uploadMessage && (
          <div className={`alert ${uploadSuccess ? 'alert-success' : 'alert-error'}`}>
            {uploadMessage}
          </div>
        )}
      </div>

      {uploadSuccessModalOpen && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="upload-success-title"
          onClick={() => setUploadSuccessModalOpen(false)}
        >
          <div className="modal-content" style={{ maxWidth: '440px' }} onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3 id="upload-success-title">Purchase Request Uploaded</h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setUploadSuccessModalOpen(false)}
                aria-label="Close upload success message"
              >
                ×
              </button>
            </div>

            <div className="modal-body upload-success-modal-body">
              <CheckCircle size={42} aria-hidden="true" />
              <p>Your Purchase Request was uploaded and its details were extracted successfully.</p>
              <p className="helper-text">Review the extracted fields below before saving the Purchase Request.</p>
            </div>

            <div className="modal-actions">
              <button type="button" className="btn btn-success" onClick={() => setUploadSuccessModalOpen(false)}>
                Continue Reviewing
              </button>
            </div>
          </div>
        </div>
      )}

      {saveSuccessModalOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="save-success-title">
          <div className="modal-content save-success-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3 id="save-success-title">Purchase Request Submitted</h3>
            </div>
            <div className="modal-body upload-success-modal-body">
              <CheckCircle size={42} aria-hidden="true" />
              <p>Purchase Request submitted successfully.</p>
              <dl className="save-success-facts">
                <div>
                  <dt>PR No.</dt>
                  <dd>{savedPr?.pr_no || 'Assigned after BAC review'}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{savedPr?.status ? savedPr.status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : 'Submitted'}</dd>
                </div>
                <div>
                  <dt>Submission date</dt>
                  <dd>{savedPr?.created_at ? new Date(savedPr.created_at).toLocaleString() : new Date().toLocaleString()}</dd>
                </div>
              </dl>
              <p className="helper-text" style={{ margin: '4px 0 0' }}>
                The Purchase Request can now proceed to the next stage of the procurement workflow.
              </p>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-success" onClick={() => {
                setSaveSuccessModalOpen(false)
                if (typeof onSaved === 'function') onSaved(savedPr?.id)
                else removeFile()
              }}>Continue</button>
            </div>
          </div>
        </div>
      )}

      <div className="pr-review-split">
        <aside className="pr-review-preview-pane card">
          <header className="panel-header">
            <h3>Document</h3>
          </header>
          {!file && (
            <div className="empty-state pr-review-preview-empty">
              <Upload size={28} aria-hidden="true" />
              <p>No document selected yet.</p>
            </div>
          )}
          {file && previewUrl && (
            file.type === 'application/pdf' ? (
              <iframe src={previewUrl} title="Uploaded Purchase Request document" />
            ) : (
              <img src={previewUrl} alt="Uploaded Purchase Request document" />
            )
          )}
        </aside>

        <div className="pr-upload-grid">
        {!reviewOnly && <section className="card form-panel pr-numbering-section">
          <header className="panel-header">
            <h3>PR Numbering</h3>
          </header>
          <div className="numbering-options">
            <label>
              <input
                type="radio"
                name="pr-numbering-mode"
                value="automatic"
                checked={numberingMode === 'automatic'}
                onChange={() => {
                  setNumberingMode('automatic')
                  setNumberError('')
                }}
              />
              Automatic
            </label>
            <label>
              <input
                type="radio"
                name="pr-numbering-mode"
                value="custom"
                checked={numberingMode === 'custom'}
                onChange={() => {
                  setNumberingMode('custom')
                  setNumberError('')
                }}
              />
              Custom
            </label>
          </div>
          {numberingMode === 'automatic' ? (
            <div className="number-preview" aria-live="polite">
              <span>Suggested PR Number</span>
              <strong>{suggestedPrNumber || 'Loading...'}</strong>
              <small>This is a preview. The final number is assigned when you save.</small>
            </div>
          ) : (
            <div className="custom-number-field">
              <label htmlFor="custom-pr-number">PR Number</label>
              <input
                id="custom-pr-number"
                value={customPrNumber}
                onChange={(event) => {
                  setCustomPrNumber(event.target.value)
                  setNumberError('')
                }}
                placeholder="YYYY-MM-NNN"
                inputMode="numeric"
              />
              <small>Use the format YYYY-MM-NNN.</small>
            </div>
          )}
          {numberError && <div className="field-error">{numberError}</div>}
        </section>}

        <section className="card form-panel">
          <header className="panel-header">
            <h3>
              <Search size={18} />
              Purchase Request Details
            </h3>
          </header>

          <div className="floating-grid">
            <FieldShell
              id="entityName"
              label="Entity Name"
              value={fields.entityName}
              onChange={(value) => onFieldChange('entityName', value)}
              full
              editedByUser={editedFieldKeys.has('entityName')}
            />

            <FieldShell
              id="fundCluster"
              label="Fund Cluster"
              value={fields.fundCluster}
              onChange={(value) => onFieldChange('fundCluster', value)}
              editedByUser={editedFieldKeys.has('fundCluster')}
            />

            <FieldShell
              id="officeSection"
              label="Office / Section"
              value={fields.officeSection}
              onChange={(value) => onFieldChange('officeSection', value)}
              editedByUser={editedFieldKeys.has('officeSection')}
            />

            <FieldShell
              id="date"
              label="Date"
              value={fields.date}
              onChange={(value) => onFieldChange('date', value)}
              type="date"
              editedByUser={editedFieldKeys.has('date')}
            />

            <FieldShell
              id="responsibilityCenterCode"
              label="Responsibility Center Code"
              value={fields.responsibilityCenterCode}
              onChange={(value) => onFieldChange('responsibilityCenterCode', value)}
              full
              editedByUser={editedFieldKeys.has('responsibilityCenterCode')}
            />

            <FieldShell
              id="purpose"
              label="Purpose"
              value={fields.purpose}
              onChange={(value) => onFieldChange('purpose', value)}
              full
              isTextarea
              editedByUser={editedFieldKeys.has('purpose')}
            />
          </div>

          <div className="signature-grid">
            <SignatureBlock
              title="Requested By"
              designationKey="requested_by_designation"
              nameKey="requested_by_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
              signatureState={signatureBlockState('requested_by_name')}
            />
            <SignatureBlock
              title="Funds Available"
              designationKey="funds_available_designation"
              nameKey="funds_available_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
              signatureState={signatureBlockState('funds_available_name')}
            />
            <SignatureBlock
              title="Approved By"
              designationKey="approved_by_designation"
              nameKey="approved_by_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
              signatureState={signatureBlockState('approved_by_name')}
            />
            <SignatureBlock
              title="Technical Working Group"
              designationKey="twg_designation"
              nameKey="twg_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
              signatureState={signatureBlockState('twg_name')}
            />
          </div>

          {(signatureValidation || hasExtractedData) && (
            <SignatureValidationPanel
              validation={signatureValidation}
              onRecheck={recheckSignatures}
              rechecking={rechecking}
              hasDocument={Boolean(fields.sourceFilename)}
            />
          )}

          <div className="requested-items-block">
            <div className="items-header">
              <h4>Requested Items</h4>
              <div className="items-header-actions">
                {hasUnsavedChanges && <span className="helper-pill unsaved-pill">Unsaved changes</span>}
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    const current = Array.isArray(fields.lineItems) ? fields.lineItems : []
                    setLineItems([
                      ...current,
                      {
                        stockPropertyNumber: '',
                        unit: '',
                        description: '',
                        quantity: '',
                        unitCost: '',
                        totalCost: '',
                      },
                    ])
                  }}
                >
                  <Plus size={16} />
                  Add Item
                </button>
              </div>
            </div>

            <div className="table-shell">
              <table className="enterprise-table items-table requested-items-table">
                <thead>
                  <tr>
                    <th style={{ width: '56px' }}>Item No.</th>
                    <th style={{ width: '140px' }}>Stock/Property No.</th>
                    <th className="requested-item-unit-cell" style={{ width: '120px' }}>Unit</th>
                    <th className="requested-item-description-cell">Description</th>
                    <th style={{ width: '90px' }}>Qty</th>
                    <th style={{ width: '140px' }}>Unit Cost</th>
                    <th style={{ width: '140px' }}>Total</th>
                    <th style={{ width: '60px' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(fields.lineItems && fields.lineItems.length > 0) ? (
                    fields.lineItems.map((item, idx) => (
                      <tr key={`item-${idx}`} className={removingRowIndex === idx ? 'item-row-removing' : ''}>
                        <td>{idx + 1}</td>
                        <td>
                          <input
                            value={item.stockPropertyNumber || ''}
                            onChange={(e) => {
                              const updated = [...(fields.lineItems || [])]
                              updated[idx] = { ...updated[idx], stockPropertyNumber: e.target.value }
                              setLineItems(updated)
                            }}
                            aria-label={`Stock number for item ${idx + 1}`}
                          />
                        </td>
                        <td className="requested-item-unit-cell">
                          <input
                            value={item.unit || ''}
                            onChange={(e) => {
                              const updated = [...(fields.lineItems || [])]
                              updated[idx] = { ...updated[idx], unit: e.target.value }
                              setLineItems(updated)
                            }}
                            aria-label={`Unit for item ${idx + 1}`}
                          />
                        </td>
                        <td className="requested-item-description-cell">
                          <AutoGrowTextarea
                            value={item.description || ''}
                            onChange={(e) => {
                              const updated = [...(fields.lineItems || [])]
                              updated[idx] = { ...updated[idx], description: e.target.value }
                              setLineItems(updated)
                            }}
                            className="requested-item-description"
                            aria-label={`Description for item ${idx + 1}`}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            value={item.quantity || ''}
                            onChange={(e) => {
                              const updated = [...(fields.lineItems || [])]
                              updated[idx] = { ...updated[idx], quantity: e.target.value }
                              setLineItems(updated)
                            }}
                            aria-label={`Quantity for item ${idx + 1}`}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            step="0.01"
                            value={item.unitCost || ''}
                            onChange={(e) => {
                              const updated = [...(fields.lineItems || [])]
                              updated[idx] = { ...updated[idx], unitCost: e.target.value }
                              setLineItems(updated)
                            }}
                            aria-label={`Unit cost for item ${idx + 1}`}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            step="0.01"
                            value={item.totalCost || ''}
                            onChange={(e) => {
                              const updated = [...(fields.lineItems || [])]
                              updated[idx] = { ...updated[idx], totalCost: e.target.value }
                              setLineItems(updated)
                            }}
                            aria-label={`Total cost for item ${idx + 1}`}
                          />
                        </td>
                        <td>
                          <button
                            type="button"
                            className="icon-action-btn delete-icon-btn"
                            onClick={() => openDeleteModal(idx)}
                            title="Delete Item"
                            aria-label={`Delete item ${idx + 1}`}
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8}>
                        <div className="table-empty-state">
                          <p>No purchase request items available.</p>
                          <span>Upload another Purchase Request or manually add items.</span>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => {
                              const current = Array.isArray(fields.lineItems) ? fields.lineItems : []
                              setLineItems([
                                ...current,
                                {
                                  stockPropertyNumber: '',
                                  unit: '',
                                  description: '',
                                  quantity: '',
                                  unitCost: '',
                                  totalCost: '',
                                },
                              ])
                            }}
                          >
                            <Plus size={16} />
                            Add Item
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {hasExtractedData && (
              <>
                <SubmissionCheckPanel checks={systemChecks} />
                <SubmissionDeclaration
                  acknowledged={declarationAcknowledged}
                  onToggle={(value) => { setDeclarationAcknowledged(value); if (value) setSaveBlockedMessage('') }}
                  checksPass={systemChecksPass}
                />
              </>
            )}

            <div className="save-row">
              <button
                type="button"
                className="btn btn-success"
                onClick={savePurchaseRequest}
                disabled={saving || (hasExtractedData && !canSubmit)}
                title={hasExtractedData && !canSubmit
                  ? 'Complete the submission checks and acknowledge the declaration to enable saving'
                  : undefined}
              >
                {saving ? <LoaderCircle size={16} className="spin" /> : <Save size={16} />}
                {saving ? 'Saving...' : 'Save Purchase Request'}
              </button>
              {hasExtractedData && !canSubmit && (
                <p className="save-blocked-note">
                  <AlertTriangle size={14} aria-hidden="true" />
                  {saveBlockedMessage
                    || (!systemChecksPass
                      ? 'Resolve the submission checks above before submitting.'
                      : 'Check the acknowledgement box to submit the Purchase Request.')}
                </p>
              )}
              {saveBlockedMessage && canSubmit && (
                <p className="save-blocked-note">
                  <AlertTriangle size={14} aria-hidden="true" />
                  {saveBlockedMessage}
                </p>
              )}
            </div>
          </div>

          {deleteModalOpen && pendingDeleteIndex !== null && (
            <div className="modal-overlay" role="dialog" aria-modal="true">
              <div className="modal-content" style={{ maxWidth: '440px' }}>
                <div className="modal-header">
                  <h3>Delete Purchase Request Item</h3>
                  <button type="button" className="modal-close" onClick={closeDeleteModal} aria-label="Close delete confirmation">
                    ×
                  </button>
                </div>

                <div className="modal-body">
                  <p>Are you sure you want to remove this item?</p>
                  <p className="helper-text">This action only removes the item from the current Purchase Request before it is saved.</p>
                </div>

                <div className="modal-actions">
                  <button type="button" className="btn btn-outline" onClick={closeDeleteModal}>Cancel</button>
                  <button type="button" className="btn btn-danger" onClick={confirmDeleteItem}>Delete Item</button>
                </div>
              </div>
            </div>
          )}

          {rawText && (
            <details className="raw-text-panel">
              <summary>View OCR Raw Text</summary>
              <pre>{rawText.slice(0, 4000)}</pre>
            </details>
          )}
        </section>
        </div>
      </div>
    </div>
  )
}

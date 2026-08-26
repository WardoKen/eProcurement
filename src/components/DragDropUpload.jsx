import { useEffect, useRef, useState } from 'react'
import {
  FileText,
  Plus,
  Save,
  LoaderCircle,
  CheckCircle,
  Search,
  Trash2,
  Upload,
} from 'lucide-react'

const normalizeNumberInput = (value) => (value || '').toString().replace(/,/g, '').trim()

const getCurrentDate = () => {
  const date = new Date()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

const PR_NUMBER_PATTERN = /^\d{4}-\d{2}-\d{3}$/

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

const SignatureBlock = ({ title, designationKey, nameKey, fields, onFieldChange, editedFieldKeys }) => (
  <section className="signature-card">
    <h4>{title}</h4>
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

export default function DragDropUpload({ apiBase = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'), onSaved = null, reviewOnly = false, submittedBy = '' }) {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState(false)
  const [uploadSuccessModalOpen, setUploadSuccessModalOpen] = useState(false)
  const [fields, setFields] = useState({})
  const [rawText, setRawText] = useState('')
  const [editedFieldKeys, setEditedFieldKeys] = useState(new Set())
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [numberingMode, setNumberingMode] = useState('automatic')
  const [suggestedPrNumber, setSuggestedPrNumber] = useState('')
  const [customPrNumber, setCustomPrNumber] = useState('')
  const [numberError, setNumberError] = useState('')
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [pendingDeleteIndex, setPendingDeleteIndex] = useState(null)
  const [removingRowIndex, setRemovingRowIndex] = useState(null)

  const fileInputRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    fetch(`${apiBase.replace(/\/$/, '')}/api/pr/next-number/`)
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
    setUploading(true)
    setUploadMessage('')
    setUploadSuccess(false)

    try {
      const form = new FormData()
      form.append('file', nextFile)
      const res = await fetch(`${apiBase}/api/upload/`, { method: 'POST', body: form })

      if (!res.ok) {
        const err = await res.json().catch(() => null)
        throw new Error(err?.message || 'Upload failed')
      }

      const data = await res.json()
      const incoming = data?.fields || {}
      const extractedFields = {
        ...incoming,
        date: incoming.date || getCurrentDate(),
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

    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function savePurchaseRequest() {
    if (numberingMode === 'custom' && !PR_NUMBER_PATTERN.test(customPrNumber.trim())) {
      setNumberError('Use the format YYYY-MM-NNN.')
      return
    }

    setSaving(true)

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
        },
      }

      const res = await fetch(`${apiBase}/api/pr/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => null)
        window.alert(err?.message || 'Failed to save PR')
        return
      }

      const result = await res.json()
      setFields((prev) => ({ ...prev, prNumber: result.pr_no || prev.prNumber }))
      setHasUnsavedChanges(false)
      setNumberError('')
      if (typeof onSaved === 'function') {
        onSaved(result.id)
      } else {
        window.alert(`Purchase Request saved (id: ${result.id})`)
        removeFile()
      }
    } catch {
      window.alert('Network error while saving PR')
    } finally {
      setSaving(false)
    }
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
          <input ref={fileInputRef} type="file" accept=".pdf,image/*" style={{ display: 'none' }} onChange={onFileInputChange} />

          {!file && (
            <div className="dropzone-inner">
              <Upload size={36} />
              <strong>Drop PR document here</strong>
              <span>PDF or image files supported. Click to browse local files.</span>
            </div>
          )}

          {file && (
            <div className="dropzone-file-row">
              <div className="file-meta">
                <FileText size={18} />
                <div>
                  <strong>{file.name}</strong>
                  <span>{(file.size / 1024).toFixed(1)} KB</span>
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
            />
            <SignatureBlock
              title="Funds Available"
              designationKey="funds_available_designation"
              nameKey="funds_available_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
            />
            <SignatureBlock
              title="Approved By"
              designationKey="approved_by_designation"
              nameKey="approved_by_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
            />
            <SignatureBlock
              title="Technical Working Group"
              designationKey="twg_designation"
              nameKey="twg_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
            />
          </div>

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
                    <th style={{ width: '70px' }}>Item No.</th>
                    <th style={{ width: '15%' }}>Stock/Property No.</th>
                    <th style={{ width: '8%' }}>Unit</th>
                    <th style={{ width: '48%' }}>Description</th>
                    <th style={{ width: '7%' }}>Qty</th>
                    <th style={{ width: '10%' }}>Unit Cost</th>
                    <th style={{ width: '10%' }}>Total</th>
                    <th style={{ width: '70px' }}>Actions</th>
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
                        <td>
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
                          <textarea
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

            <div className="save-row">
              <button type="button" className="btn btn-success" onClick={savePurchaseRequest} disabled={saving}>
                {saving ? <LoaderCircle size={16} className="spin" /> : <Save size={16} />}
                {saving ? 'Saving...' : 'Save Purchase Request'}
              </button>
              <span className="helper-text">Uploads and OCR extraction remain unchanged. Only UI presentation was improved.</span>
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
  )
}

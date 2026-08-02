import React, { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import {
  Eye,
  FileText,
  LoaderCircle,
  Plus,
  Save,
  Search,
  Trash2,
  Upload,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'

try {
  pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()
} catch {
  pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`
}

class PdfRenderErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || 'Unable to render PDF preview.' }
  }

  componentDidCatch(error) {
    if (this.props.onError) {
      this.props.onError(error)
    }
  }

  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false, message: '' })
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback(this.state.message)
    }
    return this.props.children
  }
}

const normalizeNumberInput = (value) => (value || '').toString().replace(/,/g, '').trim()

const FieldShell = ({
  id,
  label,
  value,
  onChange,
  type = 'text',
  helper,
  full,
  isTextarea,
  modifiedByOCR,
  editedByUser,
}) => {
  const wrapperClass = [
    'floating-field',
    full ? 'full' : '',
    modifiedByOCR ? 'ocr-modified' : '',
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
      {(modifiedByOCR || editedByUser) && (
        <div className="field-flags" aria-label="Field indicators">
          {modifiedByOCR && <span className="field-flag ocr">OCR</span>}
          {editedByUser && <span className="field-flag manual">Edited</span>}
        </div>
      )}
    </div>
  )
}

const SignatureBlock = ({ title, designationKey, nameKey, fields, onFieldChange, editedFieldKeys, ocrFieldKeys }) => (
  <section className="signature-card">
    <h4>{title}</h4>
    <FieldShell
      id={designationKey}
      label="Designation"
      value={fields[designationKey]}
      onChange={(value) => onFieldChange(designationKey, value)}
      modifiedByOCR={ocrFieldKeys.has(designationKey)}
      editedByUser={editedFieldKeys.has(designationKey)}
    />
    <FieldShell
      id={nameKey}
      label="Name"
      value={fields[nameKey]}
      onChange={(value) => onFieldChange(nameKey, value)}
      modifiedByOCR={ocrFieldKeys.has(nameKey)}
      editedByUser={editedFieldKeys.has(nameKey)}
    />
  </section>
)

export default function DragDropUpload({ apiBase = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'), onSaved = null }) {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState(false)
  const [fields, setFields] = useState({})
  const [rawText, setRawText] = useState('')
  const [documentViewUrl, setDocumentViewUrl] = useState('')
  const [pdfPageCount, setPdfPageCount] = useState(0)
  const [pdfError, setPdfError] = useState('')
  const [pdfLoading, setPdfLoading] = useState(false)
  const [viewerWidth, setViewerWidth] = useState(640)
  const [renderWidth, setRenderWidth] = useState(640)
  const [pdfZoom, setPdfZoom] = useState(1.1)
  const [editedFieldKeys, setEditedFieldKeys] = useState(new Set())
  const [ocrFieldKeys, setOcrFieldKeys] = useState(new Set())
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [pendingDeleteIndex, setPendingDeleteIndex] = useState(null)
  const [removingRowIndex, setRemovingRowIndex] = useState(null)

  const fileInputRef = useRef(null)
  const viewerContainerRef = useRef(null)

  useEffect(() => {
    if (!viewerContainerRef.current) return undefined

    const target = viewerContainerRef.current
    const updateWidth = () => {
      const width = Math.max(320, Math.floor(target.clientWidth - 40))
      setViewerWidth(width)
    }

    updateWidth()

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateWidth)
      return () => window.removeEventListener('resize', updateWidth)
    }

    const observer = new ResizeObserver(() => updateWidth())
    observer.observe(target)

    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setRenderWidth(viewerWidth)
    }, 120)
    return () => window.clearTimeout(timer)
  }, [viewerWidth])

  useEffect(() => {
    if (!hasUnsavedChanges) return undefined

    const handleBeforeUnload = (event) => {
      event.preventDefault()
      event.returnValue = 'You have unsaved changes. Do you want to leave without saving?'
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedChanges])

  const isPdfDocument = Boolean(documentViewUrl) && /\.pdf($|\?)/i.test(documentViewUrl)

  function isImageFile(nextFile) {
    return nextFile.type.startsWith('image/')
  }

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
    setDocumentViewUrl('')
    setUploadMessage('')
    setUploadSuccess(false)
    setPdfPageCount(0)
    setPdfError('')
    setPdfLoading(false)
    setEditedFieldKeys(new Set())
    setOcrFieldKeys(new Set())
    setHasUnsavedChanges(false)

    try {
      if (isImageFile(nextFile)) {
        const objectUrl = URL.createObjectURL(nextFile)
        setPreviewUrl(objectUrl)
      } else {
        setPreviewUrl('')
      }
    } catch {
      setPreviewUrl('')
    }
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
      const requested = (incoming.requested_items || []).map((item) => ({
        stockPropertyNumber: item.stock_no || '',
        unit: item.unit || '',
        description: item.description || '',
        quantity: item.quantity || '',
        unitCost: normalizeNumberInput(item.unit_cost),
        totalCost: normalizeNumberInput(item.total_cost),
      }))

      setFields({ ...incoming, lineItems: normalizeLineItems(requested) })
      setOcrFieldKeys(new Set([...Object.keys(incoming), 'lineItems']))
      setRawText(data?.rawText || '')
      setUploadMessage(`Uploaded: ${data?.filename || nextFile.name}`)

      const resolvedFileUrl = data?.fileUrl || (data?.filename ? `${apiBase.replace(/\/$/, '')}/uploads/${data.filename}` : '')
      if (resolvedFileUrl) {
        setDocumentViewUrl(resolvedFileUrl)
        setPdfError('')
        if (/\.pdf($|\?)/i.test(resolvedFileUrl)) {
          setPdfLoading(true)
        }
      }

      setUploadSuccess(true)
      setHasUnsavedChanges(false)

      if (resolvedFileUrl) {
        if (previewUrl && previewUrl.startsWith('blob:')) {
          try {
            URL.revokeObjectURL(previewUrl)
          } catch {
            // Ignore cleanup errors for stale object URLs.
          }
        }
        setPreviewUrl(resolvedFileUrl)
      }
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
    setDocumentViewUrl('')
    setUploadMessage('')
    setUploadSuccess(false)
    setPdfPageCount(0)
    setPdfError('')
    setPdfLoading(false)
    setEditedFieldKeys(new Set())
    setOcrFieldKeys(new Set())
    setHasUnsavedChanges(false)

    if (fileInputRef.current) fileInputRef.current.value = ''
    if (previewUrl && previewUrl.startsWith('blob:')) {
      try {
        URL.revokeObjectURL(previewUrl)
      } catch {
        // Ignore cleanup errors for stale object URLs.
      }
    }
    setPreviewUrl('')
  }

  function onPdfLoadSuccess(info) {
    setPdfLoading(false)
    setPdfError('')
    setPdfPageCount(info?.numPages || 0)
  }

  function onPdfLoadError(err) {
    setPdfLoading(false)
    setPdfPageCount(0)
    setPdfError(err?.message || 'Unable to render PDF document.')
  }

  function onPdfPageRenderError(err) {
    setPdfError(err?.message || 'Unable to render one or more PDF pages.')
  }

  function zoomOutPdf() {
    setPdfZoom((prev) => Math.max(0.8, Number((prev - 0.1).toFixed(2))))
  }

  function zoomInPdf() {
    setPdfZoom((prev) => Math.min(2.2, Number((prev + 0.1).toFixed(2))))
  }

  function resetPdfZoom() {
    setPdfZoom(1.0)
  }

  function renderPdfError(message) {
    return <div className="alert alert-error">{message || 'Unable to render PDF document.'}</div>
  }

  async function savePurchaseRequest() {
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
      setHasUnsavedChanges(false)
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

  const zoomLabel = `${Math.round(pdfZoom * 100)}%`

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

      <div className="pr-upload-grid">
        <section className="card document-panel sticky-panel">
          <header className="panel-header">
            <h3>
              <Eye size={18} />
              Document Viewer
            </h3>
            <div className="zoom-controls" role="group" aria-label="PDF zoom controls">
              <button type="button" className="btn btn-outline btn-icon" onClick={zoomOutPdf} title="Zoom out">
                <ZoomOut size={16} />
              </button>
              <span>{zoomLabel}</span>
              <button type="button" className="btn btn-outline btn-icon" onClick={zoomInPdf} title="Zoom in">
                <ZoomIn size={16} />
              </button>
              <button type="button" className="btn btn-outline" onClick={resetPdfZoom}>Fit Width</button>
            </div>
          </header>

          <div ref={viewerContainerRef} className="document-scroller">
            {documentViewUrl ? (
              isPdfDocument ? (
                <div className="pdf-viewer-wrap">
                  {pdfLoading && (
                    <div className="skeleton-stack" aria-label="Loading PDF preview">
                      <div className="skeleton-line tall" />
                      <div className="skeleton-line tall" />
                    </div>
                  )}

                  {pdfError && renderPdfError(pdfError)}

                  <PdfRenderErrorBoundary
                    resetKey={documentViewUrl}
                    onError={onPdfLoadError}
                    fallback={renderPdfError}
                  >
                    <Document
                      file={documentViewUrl}
                      loading={null}
                      onLoadSuccess={onPdfLoadSuccess}
                      onLoadError={onPdfLoadError}
                      onSourceError={onPdfLoadError}
                      options={{ cMapPacked: true }}
                    >
                      {Array.from({ length: pdfPageCount || 0 }, (_, idx) => (
                        <div key={`pdf-page-${idx + 1}`} className="pdf-page-card">
                          <Page
                            pageNumber={idx + 1}
                            width={Math.max(320, Math.floor(renderWidth * pdfZoom))}
                            renderTextLayer={false}
                            renderAnnotationLayer={false}
                            devicePixelRatio={Math.min(1.75, window.devicePixelRatio || 1)}
                            onRenderError={onPdfPageRenderError}
                          />
                          <p>Page {idx + 1}</p>
                        </div>
                      ))}
                    </Document>
                  </PdfRenderErrorBoundary>
                </div>
              ) : (
                <img src={documentViewUrl} alt="Uploaded document" className="doc-image-preview" />
              )
            ) : (
              <div className="viewer-empty-state">
                <FileText size={40} />
                <strong>No document preview yet</strong>
                <span>Upload a PR to keep the document visible while editing details.</span>
              </div>
            )}
          </div>
        </section>

        <section className="card form-panel">
          <header className="panel-header">
            <h3>
              <Search size={18} />
              Purchase Request Details
            </h3>
            <span className="helper-pill">Fields auto-filled by OCR are tagged</span>
          </header>

          <div className="floating-grid">
            <FieldShell
              id="entityName"
              label="Entity Name"
              value={fields.entityName}
              onChange={(value) => onFieldChange('entityName', value)}
              full
              modifiedByOCR={ocrFieldKeys.has('entityName')}
              editedByUser={editedFieldKeys.has('entityName')}
            />

            <FieldShell
              id="fundCluster"
              label="Fund Cluster"
              value={fields.fundCluster}
              onChange={(value) => onFieldChange('fundCluster', value)}
              modifiedByOCR={ocrFieldKeys.has('fundCluster')}
              editedByUser={editedFieldKeys.has('fundCluster')}
            />

            <FieldShell
              id="officeSection"
              label="Office / Section"
              value={fields.officeSection}
              onChange={(value) => onFieldChange('officeSection', value)}
              modifiedByOCR={ocrFieldKeys.has('officeSection')}
              editedByUser={editedFieldKeys.has('officeSection')}
            />

            <FieldShell
              id="prNumber"
              label="PR Number"
              value={fields.prNumber}
              onChange={(value) => onFieldChange('prNumber', value)}
              helper="Format: YYYY-MM-NNN"
              modifiedByOCR={ocrFieldKeys.has('prNumber')}
              editedByUser={editedFieldKeys.has('prNumber')}
            />

            <FieldShell
              id="date"
              label="Date"
              value={fields.date}
              onChange={(value) => onFieldChange('date', value)}
              type="date"
              modifiedByOCR={ocrFieldKeys.has('date')}
              editedByUser={editedFieldKeys.has('date')}
            />

            <FieldShell
              id="responsibilityCenterCode"
              label="Responsibility Center Code"
              value={fields.responsibilityCenterCode}
              onChange={(value) => onFieldChange('responsibilityCenterCode', value)}
              full
              modifiedByOCR={ocrFieldKeys.has('responsibilityCenterCode')}
              editedByUser={editedFieldKeys.has('responsibilityCenterCode')}
            />

            <FieldShell
              id="purpose"
              label="Purpose"
              value={fields.purpose}
              onChange={(value) => onFieldChange('purpose', value)}
              full
              isTextarea
              modifiedByOCR={ocrFieldKeys.has('purpose')}
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
              ocrFieldKeys={ocrFieldKeys}
            />
            <SignatureBlock
              title="Funds Available"
              designationKey="funds_available_designation"
              nameKey="funds_available_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
              ocrFieldKeys={ocrFieldKeys}
            />
            <SignatureBlock
              title="Approved By"
              designationKey="approved_by_designation"
              nameKey="approved_by_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
              ocrFieldKeys={ocrFieldKeys}
            />
            <SignatureBlock
              title="Technical Working Group"
              designationKey="twg_designation"
              nameKey="twg_name"
              fields={fields}
              onFieldChange={onFieldChange}
              editedFieldKeys={editedFieldKeys}
              ocrFieldKeys={ocrFieldKeys}
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
              <table className="enterprise-table items-table">
                <thead>
                  <tr>
                    <th style={{ width: '70px' }}>Item No.</th>
                    <th>Stock/Property No.</th>
                    <th>Unit</th>
                    <th>Description</th>
                    <th>Qty</th>
                    <th>Unit Cost</th>
                    <th>Total</th>
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
                        <td>
                          <input
                            value={item.description || ''}
                            onChange={(e) => {
                              const updated = [...(fields.lineItems || [])]
                              updated[idx] = { ...updated[idx], description: e.target.value }
                              setLineItems(updated)
                            }}
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

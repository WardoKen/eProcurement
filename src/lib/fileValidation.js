// Shared, context-aware upload validation for every eProcure upload control.
//
// The browser can only check the extension, the size and whether the file is
// empty — the Django backend re-validates the actual file content and is the
// authoritative check. This module keeps the client rules in one place so every
// upload area behaves identically.

export const UPLOAD_KINDS = {
  PR: 'pr',
  SUPPLIER_REQUIREMENT: 'supplier_requirement',
  COMPLETED_RFQ: 'completed_rfq',
}

export const MAX_UPLOAD_SIZE = 10 * 1024 * 1024
const MAX_UPLOAD_SIZE_MB = Math.round(MAX_UPLOAD_SIZE / (1024 * 1024))

const DOC_AND_IMAGE = ['.pdf', '.jpg', '.jpeg', '.png']

const RULES = {
  [UPLOAD_KINDS.PR]: {
    extensions: DOC_AND_IMAGE,
    accept: '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png',
    acceptedLabel: 'PDF, JPG, JPEG, PNG',
    typeError: 'Unsupported file type. Please upload a PDF, JPG, JPEG, or PNG file.',
  },
  [UPLOAD_KINDS.SUPPLIER_REQUIREMENT]: {
    extensions: DOC_AND_IMAGE,
    accept: '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png',
    acceptedLabel: 'PDF, JPG, JPEG, PNG',
    typeError: 'Unsupported file type. Please upload a PDF, JPG, JPEG, or PNG file.',
  },
  [UPLOAD_KINDS.COMPLETED_RFQ]: {
    extensions: ['.pdf'],
    accept: '.pdf,application/pdf',
    acceptedLabel: 'PDF only',
    typeError: 'Completed RFQ submissions must be uploaded as a PDF.',
  },
}

const SIZE_ERROR = `File is too large. Please upload a file no larger than ${MAX_UPLOAD_SIZE_MB} MB.`
const EMPTY_ERROR = 'The uploaded file is empty.'

export function acceptAttr(kind) {
  return (RULES[kind] || RULES[UPLOAD_KINDS.PR]).accept
}

export function acceptedTypesLabel(kind) {
  return (RULES[kind] || RULES[UPLOAD_KINDS.PR]).acceptedLabel
}

function extensionOf(name) {
  const lower = String(name || '').toLowerCase()
  const dot = lower.lastIndexOf('.')
  return dot >= 0 ? lower.slice(dot) : ''
}

export function formatFileSize(bytes) {
  const value = Number(bytes || 0)
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export function fileTypeLabel(file) {
  const ext = extensionOf(file?.name).replace('.', '').toUpperCase()
  return ext || 'FILE'
}

// Returns { ok: true, meta: {...} } or { ok: false, error: '...' }.
export function validateFile(file, kind) {
  const rule = RULES[kind] || RULES[UPLOAD_KINDS.PR]
  if (!file) return { ok: false, error: 'Please choose a file to upload.' }

  if (typeof file.size === 'number' && file.size <= 0) {
    return { ok: false, error: EMPTY_ERROR }
  }
  if (typeof file.size === 'number' && file.size > MAX_UPLOAD_SIZE) {
    return { ok: false, error: SIZE_ERROR }
  }

  const ext = extensionOf(file.name)
  if (!rule.extensions.includes(ext)) {
    return { ok: false, error: rule.typeError }
  }

  return {
    ok: true,
    meta: {
      name: file.name,
      type: fileTypeLabel(file),
      size: formatFileSize(file.size),
    },
  }
}

// Validate a list, returning { valid: [File], errors: [{ name, error }] }.
export function validateFiles(files, kind) {
  const valid = []
  const errors = []
  Array.from(files || []).forEach((file) => {
    const result = validateFile(file, kind)
    if (result.ok) valid.push(file)
    else errors.push({ name: file?.name || 'file', error: result.error })
  })
  return { valid, errors }
}

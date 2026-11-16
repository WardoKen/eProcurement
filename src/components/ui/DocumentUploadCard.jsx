import React from 'react'
import { CloudUpload, FileCheck2, FileText, RefreshCw, Trash2 } from 'lucide-react'
import { FieldError } from './FormParts'
import { fileTypeLabel, formatFileSize } from '../../lib/fileValidation'

// One document slot in the supplier registration checklist: a drop zone
// (click or drag a file onto it) until a file is attached, then a file row
// with Replace / Remove. The real <input type="file"> stays in the DOM,
// visually hidden, so keyboard users, screen readers and tests reach it
// directly; the zone is its <label>.
//
// With `multiple`, the slot holds a list (`files`): each file gets its own
// row with Remove, and the zone stays below the list to add more until
// `maxFiles` is reached. `onSelect` then receives an array of files and
// `onRemove` the index of the file to drop.
export default function DocumentUploadCard({
  id,
  title,
  hint,
  required = true,
  multiple = false,
  file,
  files = [],
  maxFiles = Infinity,
  error,
  accept,
  acceptLabel,
  onSelect,
  onRemove,
}) {
  const inputRef = React.useRef(null)
  const [dragging, setDragging] = React.useState(false)
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const attached = multiple ? files : (file ? [file] : [])
  const hasFiles = attached.length > 0
  const canAdd = multiple ? attached.length < maxFiles : !file
  const state = hasFiles ? 'attached' : error ? 'missing' : 'empty'

  const pick = (fileList) => {
    const picked = Array.from(fileList || [])
    if (picked.length === 0) return
    onSelect(multiple ? picked : picked[0])
  }

  const dropProps = canAdd ? {
    onDragOver: (event) => {
      event.preventDefault()
      event.dataTransfer.dropEffect = 'copy'
      setDragging(true)
    },
    onDragLeave: () => setDragging(false),
    onDrop: (event) => {
      event.preventDefault()
      setDragging(false)
      pick(event.dataTransfer.files)
    },
  } : {}

  let tagText = required ? 'Required' : 'Optional'
  if (hasFiles) tagText = multiple ? `${attached.length} attached` : 'Attached'

  return (
    <div className={`doc-upload is-${state}${dragging ? ' is-dragging' : ''}${multiple ? ' is-multiple' : ''}`} {...dropProps}>
      <div className="doc-upload-head">
        <span className="doc-upload-icon" aria-hidden="true">
          {hasFiles ? <FileCheck2 size={18} /> : <FileText size={18} />}
        </span>
        <div className="doc-upload-title">
          <h3 id={`${id}-title`}>{title}</h3>
          {hint && <p id={hintId}>{hint}</p>}
        </div>
        <span className={`doc-upload-tag is-${hasFiles ? 'attached' : required ? 'required' : 'optional'}`}>
          {tagText}
        </span>
      </div>

      <input
        ref={inputRef}
        id={id}
        type="file"
        className="sr-only"
        accept={accept}
        multiple={multiple}
        disabled={!canAdd && multiple}
        aria-labelledby={`${id}-title`}
        aria-describedby={[hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined}
        aria-invalid={error ? true : undefined}
        onChange={(event) => {
          pick(event.target.files)
          // Clear so choosing the same file again after Remove still fires.
          event.target.value = ''
        }}
      />

      {hasFiles && (
        <ul className="doc-upload-files" aria-label={`${title} files`}>
          {attached.map((item, index) => (
            <li className="doc-upload-file" key={`${item.name}-${item.size}-${item.lastModified}-${index}`}>
              <span className="doc-upload-type">{fileTypeLabel(item)}</span>
              <span className="doc-upload-file-text">
                <strong title={item.name}>{item.name}</strong>
                <small>{formatFileSize(item.size)}</small>
              </span>
              <span className="doc-upload-actions">
                {!multiple && (
                  <button type="button" className="doc-upload-action" onClick={() => inputRef.current?.click()} aria-label={`Replace ${title} file`}>
                    <RefreshCw size={14} aria-hidden="true" /> Replace
                  </button>
                )}
                <button
                  type="button"
                  className="doc-upload-action is-danger"
                  onClick={() => onRemove(multiple ? index : undefined)}
                  aria-label={multiple ? `Remove ${item.name}` : `Remove ${title} file`}
                >
                  <Trash2 size={14} aria-hidden="true" /> Remove
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {canAdd && (
        <label htmlFor={id} className={`doc-upload-zone${hasFiles ? ' is-compact' : ''}`}>
          <CloudUpload size={22} aria-hidden="true" />
          <span className="doc-upload-zone-text">
            <strong>
              {dragging
                ? 'Drop to attach'
                : hasFiles
                  ? <>Add another file: drag it here or <u>browse</u></>
                  : <>Drag {multiple ? 'files' : 'a file'} here or <u>browse</u></>}
            </strong>
            <small>
              {acceptLabel}
              {multiple && Number.isFinite(maxFiles) ? ` · up to ${maxFiles} files` : ''}
            </small>
          </span>
        </label>
      )}
      {multiple && !canAdd && (
        <p className="doc-upload-limit">Limit of {maxFiles} files reached. Remove one to add another.</p>
      )}

      <FieldError id={errorId}>{error}</FieldError>
    </div>
  )
}

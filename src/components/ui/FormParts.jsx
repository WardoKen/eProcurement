import { AlertCircle } from 'lucide-react'

// Visual required marker. The input itself carries `required` /
// `aria-required`, so the asterisk is hidden from assistive tech.
export function RequiredMark() {
  return <span className="required-mark" aria-hidden="true"> *</span>
}

export function RequiredLegend() {
  return (
    <p className="required-legend">
      Fields marked <span className="required-mark" aria-hidden="true">*</span>
      <span className="sr-only">with an asterisk</span> are required.
    </p>
  )
}

// Inline message linked to its field via aria-describedby={id}.
export function FieldError({ id, children }) {
  if (!children) return null
  return (
    <p id={id} className="field-error">
      <AlertCircle size={14} aria-hidden="true" />
      <span>{children}</span>
    </p>
  )
}

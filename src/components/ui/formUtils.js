// Props for a field with an optional inline error.
export const errorProps = (errorId, message, hintId) => ({
  'aria-invalid': message ? true : undefined,
  'aria-describedby': [message ? errorId : null, hintId].filter(Boolean).join(' ') || undefined,
})

// After a failed submit, move focus to the first invalid field in `root`.
export function focusFirstInvalid(root) {
  const target = root?.querySelector('[aria-invalid="true"]')
  if (target && typeof target.focus === 'function') target.focus()
}

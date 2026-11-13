import { useCallback, useRef, useState } from 'react'
import ConfirmDialog from './ConfirmDialog'

// Promise-based replacement for window.confirm():
//   const [confirmDialog, confirm] = useConfirm()
//   if (!(await confirm({ title, consequence, confirmLabel, tone }))) return
//   ...render {confirmDialog} somewhere in the component.
export default function useConfirm() {
  const [options, setOptions] = useState(null)
  const resolverRef = useRef(null)

  const confirm = useCallback((nextOptions) => new Promise((resolve) => {
    resolverRef.current = resolve
    setOptions(nextOptions)
  }), [])

  const settle = (answer) => {
    resolverRef.current?.(answer)
    resolverRef.current = null
    setOptions(null)
  }

  const dialog = options ? (
    <ConfirmDialog
      title={options.title}
      consequence={options.consequence}
      confirmLabel={options.confirmLabel}
      cancelLabel={options.cancelLabel}
      tone={options.tone}
      onConfirm={() => settle(true)}
      onCancel={() => settle(false)}
    >
      {options.message && <p>{options.message}</p>}
    </ConfirmDialog>
  ) : null

  return [dialog, confirm]
}

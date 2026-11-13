import { createContext, useContext } from 'react'

export const ToastContext = createContext(null)

const noop = () => {}
const fallback = { success: noop, error: noop, info: noop, dismiss: noop }

// `const toast = useToast(); toast.success('Saved.')`. Outside a provider the
// calls are no-ops, so a component never crashes when rendered on its own.
export function useToast() {
  return useContext(ToastContext) || fallback
}

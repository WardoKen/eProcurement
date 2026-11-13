import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle, Info, X } from 'lucide-react'
import { ToastContext } from './toast-context'

const ICONS = { success: CheckCircle, error: AlertCircle, info: Info }
const DURATION_MS = { success: 5000, info: 5000, error: 8000 }

// Non-blocking success/error notifications. Success and info toasts are
// announced politely; errors use role="alert". Toasts pause their timer while
// hovered or focused, so they can be read.
export default function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(1)

  const dismiss = useCallback((id) => setToasts((current) => current.filter((toast) => toast.id !== id)), [])

  const push = useCallback((tone, message) => {
    if (!message) return
    const id = nextId.current++
    setToasts((current) => [...current.slice(-3), { id, tone, message }])
  }, [])

  const api = useMemo(() => ({
    success: (message) => push('success', message),
    error: (message) => push('error', message),
    info: (message) => push('info', message),
    dismiss,
  }), [dismiss, push])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-region">
        {toasts.map((toast) => <Toast key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} />)}
      </div>
    </ToastContext.Provider>
  )
}

function Toast({ toast, onDismiss }) {
  const [paused, setPaused] = useState(false)
  const Icon = ICONS[toast.tone] || Info

  useEffect(() => {
    if (paused) return undefined
    const timer = window.setTimeout(onDismiss, DURATION_MS[toast.tone] || 5000)
    return () => window.clearTimeout(timer)
  }, [onDismiss, paused, toast.tone])

  return (
    <div
      className={`toast toast-${toast.tone}`}
      role={toast.tone === 'error' ? 'alert' : 'status'}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <Icon className="toast-icon" size={18} aria-hidden="true" />
      <p className="toast-message">{toast.message}</p>
      <button type="button" className="toast-dismiss" onClick={onDismiss} aria-label="Dismiss notification">
        <X size={14} aria-hidden="true" />
      </button>
    </div>
  )
}

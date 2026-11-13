import { useEffect, useRef } from 'react'

// Accessible modal shell used by every overlay in the app. It keeps the
// existing overlay/content class names so current styling applies, and adds:
//   - focus moves into the dialog on open (an autoFocus child wins), and
//     returns to the element that opened it on close;
//   - Tab / Shift+Tab stay inside the dialog;
//   - Escape and overlay clicks call onClose (when `dismissible`);
//   - only the top-most of several stacked modals reacts to keys.

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'iframe',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const openStack = []

const focusableIn = (node) => [...node.querySelectorAll(FOCUSABLE)]
  .filter((element) => !element.closest('[inert]') && element.getAttribute('aria-hidden') !== 'true')

export default function Modal({
  onClose,
  labelledBy,
  describedBy,
  label,
  role = 'dialog',
  overlayClassName = 'modal-overlay',
  className = 'modal-content',
  dismissible = true,
  closeOnOverlay = true,
  initialFocusRef,
  style,
  children,
}) {
  const contentRef = useRef(null)
  // Captured on first render, before any autoFocus child steals focus.
  const triggerRef = useRef(typeof document !== 'undefined' ? document.activeElement : null)
  const onCloseRef = useRef(onClose)
  const dismissibleRef = useRef(dismissible)

  useEffect(() => {
    onCloseRef.current = onClose
    dismissibleRef.current = dismissible
  })

  useEffect(() => {
    const node = contentRef.current
    const token = {}
    openStack.push(token)

    if (!node.contains(document.activeElement)) {
      const target = initialFocusRef?.current || node
      target.focus({ preventScroll: true })
    }

    const onKeyDown = (event) => {
      if (openStack[openStack.length - 1] !== token) return
      if (event.key === 'Escape') {
        if (dismissibleRef.current && onCloseRef.current) {
          event.stopPropagation()
          onCloseRef.current()
        }
        return
      }
      if (event.key !== 'Tab') return
      const focusables = focusableIn(node)
      if (focusables.length === 0) {
        event.preventDefault()
        node.focus()
        return
      }
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement
      if (!node.contains(active)) {
        event.preventDefault()
        first.focus()
      } else if (event.shiftKey && (active === first || active === node)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown, true)
    const trigger = triggerRef.current
    return () => {
      document.removeEventListener('keydown', onKeyDown, true)
      const index = openStack.indexOf(token)
      if (index >= 0) openStack.splice(index, 1)
      if (trigger && trigger.isConnected && typeof trigger.focus === 'function') {
        trigger.focus({ preventScroll: true })
      }
    }
    // Focus handling runs once per open; later prop changes are read via refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      className={overlayClassName}
      onClick={(event) => {
        if (event.target === event.currentTarget && closeOnOverlay && dismissible && onClose) onClose()
      }}
    >
      <div
        ref={contentRef}
        className={`${className} ds-modal-content`}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        aria-label={labelledBy ? undefined : label}
        tabIndex={-1}
        style={style}
      >
        {children}
      </div>
    </div>
  )
}

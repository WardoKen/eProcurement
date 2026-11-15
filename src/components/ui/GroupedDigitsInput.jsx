import React from 'react'

// A text input whose value is a string of digits shown with separators
// ("9171234567" as "917 123 4567", "123456789000" as "123-456-789-000").
// `parse(raw)` turns what the user typed or pasted into `{ digits, ...extra }`
// and `onChange` receives that result; `format(digits)` renders it back.
// Handles the two things a naive formatter gets wrong: the caret stays after
// the same digit when separators move, and deleting a separator deletes the
// digit beside it instead of being undone by the regrouping.
const GroupedDigitsInput = React.forwardRef(function GroupedDigitsInput(
  { digits, format, parse, onChange, ...inputProps },
  forwardedRef,
) {
  const inputRef = React.useRef(null)
  const pendingCaret = React.useRef(null)
  const formatted = format(digits)

  React.useImperativeHandle(forwardedRef, () => inputRef.current)

  React.useLayoutEffect(() => {
    const input = inputRef.current
    const digitsBefore = pendingCaret.current
    if (input == null || digitsBefore == null || document.activeElement !== input) return
    pendingCaret.current = null
    let position = 0
    let seen = 0
    while (position < formatted.length && seen < digitsBefore) {
      if (/\d/.test(formatted[position])) seen += 1
      position += 1
    }
    input.setSelectionRange(position, position)
  }, [formatted])

  const handleInput = (event) => {
    let { value } = event.target
    const { selectionStart } = event.target
    let typedBeforeCaret = value.slice(0, selectionStart ?? value.length).replace(/\D/g, '').length
    // Only a separator was deleted: delete the neighbouring digit instead.
    const inputType = event.nativeEvent?.inputType
    if (value.replace(/\D/g, '') === digits && value.length < formatted.length) {
      if (inputType === 'deleteContentBackward' && typedBeforeCaret > 0) {
        value = digits.slice(0, typedBeforeCaret - 1) + digits.slice(typedBeforeCaret)
        typedBeforeCaret -= 1
      } else if (inputType === 'deleteContentForward') {
        value = digits.slice(0, typedBeforeCaret) + digits.slice(typedBeforeCaret + 1)
      }
    }
    const next = parse(value)
    // Digits dropped from the front (a trunk 0, a pasted dial code) shift the caret.
    const dropped = Math.max(0, value.replace(/\D/g, '').length - next.digits.length)
    pendingCaret.current = Math.max(0, Math.min(next.digits.length, typedBeforeCaret - dropped))
    onChange(next)
  }

  return <input {...inputProps} ref={inputRef} value={formatted} onChange={handleInput} />
})

export default GroupedDigitsInput

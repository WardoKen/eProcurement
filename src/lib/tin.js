// Philippine Taxpayer Identification Number: a 9-digit TIN, optionally
// followed by a branch code of 3 digits (older "000") or 5 digits (the BIR's
// newer "00000"). Shown grouped as 123-456-789-000.
export const TIN_MAX_DIGITS = 14
const VALID_LENGTHS = [9, 12, 14]

export const parseTin = (raw) => String(raw || '').replace(/\D/g, '').slice(0, TIN_MAX_DIGITS)

export function formatTin(digits) {
  const head = [digits.slice(0, 3), digits.slice(3, 6), digits.slice(6, 9)].filter(Boolean)
  const branch = digits.slice(9)
  return [...head, ...(branch ? [branch] : [])].join('-')
}

export const isValidTin = (digits) => VALID_LENGTHS.includes(digits.length)

export const TIN_EXAMPLE = '123-456-789-000'

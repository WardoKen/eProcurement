// Phone numbers as a country dial code plus a national number that is grouped
// as it is typed, e.g. Philippines + "9171234567" -> "+63 917 123 4567".
// `groups` is the digit grouping of the national number (without the trunk
// "0"), `min`/`max` its accepted length. Any of the three may be a function
// of the digits typed so far (the Philippines mixes mobile and landline
// numbers).
const PH_GROUPS = (digits) => {
  if (digits.startsWith('9')) return [3, 3, 4] // mobile: 917 123 4567
  if (digits.startsWith('2')) return [1, 4, 4] // Metro Manila: 2 8123 4567
  return [2, 3, 4] //                              provincial: 32 463 9313
}
const PH_LENGTH = (digits) => (digits.startsWith('9') ? 10 : 9)

export const PHONE_COUNTRIES = [
  { code: 'PH', name: 'Philippines', dial: '63', groups: PH_GROUPS, min: PH_LENGTH, max: PH_LENGTH, example: '917 123 4567' },
  { code: 'US', name: 'United States / Canada', dial: '1', groups: [3, 3, 4], min: 10, max: 10, example: '415 555 0123' },
  { code: 'AU', name: 'Australia', dial: '61', groups: [3, 3, 3], min: 9, max: 9, example: '412 345 678' },
  { code: 'CN', name: 'China', dial: '86', groups: [3, 4, 4], min: 11, max: 11, example: '131 2345 6789' },
  { code: 'HK', name: 'Hong Kong', dial: '852', groups: [4, 4], min: 8, max: 8, example: '5123 4567' },
  { code: 'IN', name: 'India', dial: '91', groups: [5, 5], min: 10, max: 10, example: '81234 56789' },
  { code: 'ID', name: 'Indonesia', dial: '62', groups: [3, 4, 5], min: 9, max: 12, example: '812 3456 7890' },
  { code: 'JP', name: 'Japan', dial: '81', groups: [2, 4, 4], min: 9, max: 10, example: '90 1234 5678' },
  { code: 'MY', name: 'Malaysia', dial: '60', groups: [2, 4, 4], min: 9, max: 10, example: '12 345 6789' },
  { code: 'NZ', name: 'New Zealand', dial: '64', groups: [2, 3, 4], min: 8, max: 10, example: '21 123 4567' },
  { code: 'QA', name: 'Qatar', dial: '974', groups: [4, 4], min: 8, max: 8, example: '3312 3456' },
  { code: 'SA', name: 'Saudi Arabia', dial: '966', groups: [2, 3, 4], min: 9, max: 9, example: '51 234 5678' },
  { code: 'SG', name: 'Singapore', dial: '65', groups: [4, 4], min: 8, max: 8, example: '8123 4567' },
  { code: 'KR', name: 'South Korea', dial: '82', groups: [2, 4, 4], min: 9, max: 10, example: '10 1234 5678' },
  { code: 'TW', name: 'Taiwan', dial: '886', groups: [3, 3, 3], min: 9, max: 9, example: '912 345 678' },
  { code: 'TH', name: 'Thailand', dial: '66', groups: [2, 3, 4], min: 9, max: 9, example: '81 234 5678' },
  { code: 'AE', name: 'United Arab Emirates', dial: '971', groups: [2, 3, 4], min: 9, max: 9, example: '50 123 4567' },
  { code: 'GB', name: 'United Kingdom', dial: '44', groups: [4, 6], min: 10, max: 10, example: '7400 123456' },
  { code: 'VN', name: 'Vietnam', dial: '84', groups: [3, 3, 3], min: 9, max: 9, example: '912 345 678' },
]

export const DEFAULT_PHONE_COUNTRY = 'PH'

export const findPhoneCountry = (code) =>
  PHONE_COUNTRIES.find((country) => country.code === code) || PHONE_COUNTRIES[0]

const onlyDigits = (value) => String(value || '').replace(/\D/g, '')
const rule = (value, digits) => (typeof value === 'function' ? value(digits) : value)
// The most digits a country ever accepts, used before the number is known.
const MAX_LENGTH = (country) => (typeof country.max === 'function' ? 10 : country.max)

// Longest dial code first so "+852..." is Hong Kong rather than "+85"-anything.
const BY_DIAL_LENGTH = [...PHONE_COUNTRIES].sort((a, b) => b.dial.length - a.dial.length)

// Turns whatever was typed or pasted into national digits for `country`:
// drops the trunk "0" (0917... -> 917...) and a leading dial code when the
// number is otherwise too long (639171234567 -> 9171234567). A pasted
// "+<code>..." for another listed country switches to that country.
export function parsePhoneInput(raw, country) {
  const text = String(raw || '').trim()
  let target = country
  let digits = onlyDigits(text)

  if (text.startsWith('+')) {
    const match = BY_DIAL_LENGTH.find((item) => digits.startsWith(item.dial))
    if (match) {
      target = match
      digits = digits.slice(match.dial.length)
    }
  } else if (digits.length > MAX_LENGTH(target) && digits.startsWith(target.dial)) {
    digits = digits.slice(target.dial.length)
  }

  digits = digits.replace(/^0+/, '')
  digits = digits.slice(0, rule(target.max, digits))
  return { country: target, digits }
}

export function formatNationalNumber(digits, country) {
  const groups = rule(country.groups, digits)
  const parts = []
  let index = 0
  groups.forEach((size, groupIndex) => {
    if (index >= digits.length) return
    // The last group takes any remaining digits.
    const end = groupIndex === groups.length - 1 ? digits.length : index + size
    parts.push(digits.slice(index, end))
    index = end
  })
  return parts.join(' ')
}

export const formatPhoneNumber = (digits, country) =>
  digits ? `+${country.dial} ${formatNationalNumber(digits, country)}` : ''

export const isValidPhoneNumber = (digits, country) =>
  digits.length >= rule(country.min, digits) && digits.length <= rule(country.max, digits)

import { describe, expect, it } from 'vitest'
import { findPhoneCountry, formatNationalNumber, formatPhoneNumber, isValidPhoneNumber, parsePhoneInput } from './phone'

const PH = findPhoneCountry('PH')
const US = findPhoneCountry('US')

describe('phone number formatting', () => {
  it('groups Philippine mobile and landline numbers', () => {
    expect(formatPhoneNumber('9171234567', PH)).toBe('+63 917 123 4567')
    expect(formatPhoneNumber('324639313', PH)).toBe('+63 32 463 9313')
    expect(formatPhoneNumber('281234567', PH)).toBe('+63 2 8123 4567')
    expect(formatNationalNumber('91712', PH)).toBe('917 12')
  })

  it('reads local, prefixed and pasted international input', () => {
    expect(parsePhoneInput('0917-123-4567', PH)).toEqual({ country: PH, digits: '9171234567' })
    expect(parsePhoneInput('639171234567', PH).digits).toBe('9171234567')
    expect(parsePhoneInput('+63 917 123 4567', US)).toEqual({ country: PH, digits: '9171234567' })
    expect(parsePhoneInput('+1 (415) 555-0123', PH)).toEqual({ country: US, digits: '4155550123' })
    expect(parsePhoneInput('917123456789', PH).digits).toBe('9171234567')
  })

  it('validates length per country and number type', () => {
    expect(isValidPhoneNumber('9171234567', PH)).toBe(true)
    expect(isValidPhoneNumber('917123456', PH)).toBe(false)
    expect(isValidPhoneNumber('324639313', PH)).toBe(true)
    expect(isValidPhoneNumber('415555012', US)).toBe(false)
  })
})

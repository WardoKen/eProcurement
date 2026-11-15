import { describe, expect, it } from 'vitest'
import { formatTin, isValidTin, parseTin } from './tin'

describe('TIN formatting', () => {
  it('groups the TIN and branch code', () => {
    expect(formatTin('1234')).toBe('123-4')
    expect(formatTin('123456789')).toBe('123-456-789')
    expect(formatTin('123456789000')).toBe('123-456-789-000')
    expect(formatTin('12345678900000')).toBe('123-456-789-00000')
  })

  it('keeps only digits, up to a 5-digit branch code', () => {
    expect(parseTin('123 456 789-000')).toBe('123456789000')
    expect(parseTin('123-456-789-000001')).toBe('12345678900000')
  })

  it('accepts 9, 12 or 14 digits', () => {
    expect(isValidTin('123456789')).toBe(true)
    expect(isValidTin('123456789000')).toBe(true)
    expect(isValidTin('12345678900000')).toBe(true)
    expect(isValidTin('1234567890')).toBe(false)
  })
})

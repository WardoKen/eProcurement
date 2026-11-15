import { ChevronDown } from 'lucide-react'
import GroupedDigitsInput from './GroupedDigitsInput'
import { PHONE_COUNTRIES, findPhoneCountry, formatNationalNumber, parsePhoneInput } from '../../lib/phone'

// Country calling code picker plus a national number input that groups the
// digits as they are typed ("9171234567" shows as "917 123 4567"). The parent
// owns { countryCode, digits }; see src/lib/phone.js for the formatting rules.
// The native <select> sits invisibly over a compact "PH +63" face so the
// closed control stays narrow while the open list shows full country names.
export default function PhoneField({ id, countryCode, digits, onChange, inputProps = {} }) {
  const country = findPhoneCountry(countryCode)

  const parse = (raw) => {
    const next = parsePhoneInput(raw, country)
    return { countryCode: next.country.code, digits: next.digits }
  }

  const handleCountry = (event) => {
    const nextCountry = findPhoneCountry(event.target.value)
    // Re-apply the new country's length limit to digits already entered.
    onChange({ countryCode: nextCountry.code, digits: parsePhoneInput(digits, nextCountry).digits })
  }

  return (
    <div className="phone-field">
      <div className="phone-field-country">
        <span className="phone-field-country-face" aria-hidden="true">
          <span className="phone-field-country-code">{country.code}</span>
          <span className="phone-field-dial">+{country.dial}</span>
          <ChevronDown size={14} />
        </span>
        <select
          id={`${id}-country`}
          aria-label="Country calling code"
          value={country.code}
          onChange={handleCountry}
        >
          {PHONE_COUNTRIES.map((item) => (
            <option key={item.code} value={item.code}>{item.name} (+{item.dial})</option>
          ))}
        </select>
      </div>
      <GroupedDigitsInput
        {...inputProps}
        id={id}
        type="tel"
        inputMode="tel"
        autoComplete="tel-national"
        placeholder={country.example}
        digits={digits}
        format={(value) => formatNationalNumber(value, country)}
        parse={parse}
        onChange={onChange}
      />
    </div>
  )
}

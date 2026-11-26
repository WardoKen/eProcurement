// Date-range filtering shared by the admin tables and their CSV exports.
// Ranges are calendar days (YYYY-MM-DD, as <input type="date"> gives them),
// read in the viewer's own timezone. The export sends that timezone along so
// the server cuts the days in the same place.

const pad = (n) => String(n).padStart(2, '0')

// YYYY-MM-DD of a timestamp in the viewer's local time, or '' when unparseable.
export const localDateKey = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// Inclusive on both ends; an empty bound is open. A row with no usable date
// is outside any range that has a bound.
export const withinDateRange = (value, from, to) => {
  if (!from && !to) return true
  const key = localDateKey(value)
  if (!key) return false
  if (from && key < from) return false
  if (to && key > to) return false
  return true
}

export const viewerTimeZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  } catch {
    return ''
  }
}

// Query string for an export: drops blank values and the 'all' sentinel the
// filter dropdowns use, and adds the viewer's timezone, which the server uses
// both for the date range and for the timestamps it writes.
export const exportQuery = (params = {}) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    const text = typeof value === 'string' ? value.trim() : value
    if (text && text !== 'all') query.set(key, text)
  })
  const tz = viewerTimeZone()
  if (tz) query.set('tz', tz)
  const text = query.toString()
  return text ? `?${text}` : ''
}

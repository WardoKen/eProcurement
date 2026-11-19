import { useCallback, useState } from 'react'

// Table density (DESIGN.md, "Data"): 'compact' (default for the BAC) or
// 'comfortable'. Remembered per browser; storage failures are ignored.
const KEY = 'eprocure-density'

const read = () => {
  try {
    return window.localStorage.getItem(KEY) === 'comfortable' ? 'comfortable' : 'compact'
  } catch {
    return 'compact'
  }
}

export function useDensity() {
  const [density, setState] = useState(read)
  const setDensity = useCallback((value) => {
    setState(value)
    try {
      window.localStorage.setItem(KEY, value)
    } catch {
      // Storage blocked: the choice lasts for this page only.
    }
  }, [])
  return [density, setDensity]
}

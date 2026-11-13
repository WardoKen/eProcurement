import { useMemo, useState } from 'react'

// Client-side search, sort and pagination for lists the API already returns
// in full. It never changes what is fetched; it only orders and slices rows
// for display.
//
//   const table = useTableControls(rows, {
//     search: (row) => [row.pr_no, row.entity_name],   // searchable text
//     sorters: { pr_no: (row) => row.pr_no, created: (row) => row.created_at },
//     initialSort: { key: 'created', direction: 'descending' },
//     filter: (row) => status === 'all' || row.status === status,
//     pageSize: 10,
//   })

const compare = (a, b) => {
  if (a === b) return 0
  if (a === null || a === undefined || a === '') return 1
  if (b === null || b === undefined || b === '') return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' })
}

export default function useTableControls(rows, {
  search,
  sorters = {},
  initialSort = null,
  filter,
  pageSize: initialPageSize = 10,
} = {}) {
  const [query, setQueryState] = useState('')
  const [sort, setSort] = useState(initialSort)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSizeState] = useState(initialPageSize)

  const list = useMemo(() => (Array.isArray(rows) ? rows : []), [rows])

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    return list.filter((row) => {
      if (filter && !filter(row)) return false
      if (!term || !search) return true
      return search(row).filter(Boolean).join(' ').toLowerCase().includes(term)
    })
  }, [filter, list, query, search])

  const sorted = useMemo(() => {
    const accessor = sort && sorters[sort.key]
    if (!accessor) return filtered
    const direction = sort.direction === 'descending' ? -1 : 1
    return [...filtered].sort((a, b) => {
      const av = accessor(a)
      const bv = accessor(b)
      // Blank values always sort last, whichever the direction.
      const aBlank = av === null || av === undefined || av === ''
      const bBlank = bv === null || bv === undefined || bv === ''
      if (aBlank || bBlank) return aBlank === bBlank ? 0 : aBlank ? 1 : -1
      return compare(av, bv) * direction
    })
    // `sorters` is a fresh object each render; the sort key/direction drive it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered, sort])

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const start = (currentPage - 1) * pageSize
  const pageRows = sorted.slice(start, start + pageSize)

  const toggleSort = (key) => {
    setSort((current) => (
      current?.key === key
        ? { key, direction: current.direction === 'ascending' ? 'descending' : 'ascending' }
        : { key, direction: 'ascending' }
    ))
    setPage(1)
  }

  return {
    rows: pageRows,
    total: sorted.length,
    unfilteredTotal: list.length,
    query,
    setQuery: (value) => { setQueryState(value); setPage(1) },
    sort,
    toggleSort,
    ariaSort: (key) => (sort?.key === key ? sort.direction : 'none'),
    page: currentPage,
    pageCount,
    setPage,
    pageSize,
    setPageSize: (size) => { setPageSizeState(size); setPage(1) },
    rangeStart: sorted.length === 0 ? 0 : start + 1,
    rangeEnd: start + pageRows.length,
    resetPage: () => setPage(1),
  }
}

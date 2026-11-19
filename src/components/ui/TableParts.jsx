import { useId } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search } from 'lucide-react'

// Sortable column header. Pass the `table` object from useTableControls.
export function SortableHeader({ table, sortKey, children, className, style }) {
  const state = table.ariaSort(sortKey)
  const Icon = state === 'ascending' ? ArrowUp : state === 'descending' ? ArrowDown : ArrowUpDown
  return (
    <th aria-sort={state} className={className} style={style} scope="col">
      <button type="button" className="sort-button" onClick={() => table.toggleSort(sortKey)}>
        {children}
        <Icon size={13} aria-hidden="true" />
        <span className="sr-only">
          {state === 'none' ? ', not sorted. Activate to sort.' : `, sorted ${state}. Activate to reverse.`}
        </span>
      </button>
    </th>
  )
}

// Search box + optional extra controls + a live result count.
// Comfortable / Compact switch. The table's wrapper carries
// data-density={density}; src/lib/density.js remembers the choice.
export function DensityToggle({ density, onChange }) {
  return (
    <div className="density-toggle" role="group" aria-label="Row density">
      {[['comfortable', 'Comfortable'], ['compact', 'Compact']].map(([value, label]) => (
        <button key={value} type="button" aria-pressed={density === value} onClick={() => onChange(value)}>{label}</button>
      ))}
    </div>
  )
}

export function TableToolbar({ table, searchLabel, searchPlaceholder, children, noun = 'record', density, onDensityChange }) {
  const searchId = useId()
  const plural = (count) => {
    if (count === 1) return `${count} ${noun}`
    // "opportunity" -> "opportunities", "quotation" -> "quotations"
    return /[^aeiou]y$/i.test(noun) ? `${count} ${noun.slice(0, -1)}ies` : `${count} ${noun}s`
  }
  return (
    <div className="data-toolbar">
      <div className="data-toolbar-search">
        <label htmlFor={searchId}>{searchLabel}</label>
        <div className="supplier-search-box">
          <Search size={16} aria-hidden="true" />
          <input
            id={searchId}
            type="search"
            value={table.query}
            onChange={(event) => table.setQuery(event.target.value)}
            placeholder={searchPlaceholder}
          />
        </div>
      </div>
      {children}
      <p className="data-toolbar-count" aria-live="polite">
        {table.total === table.unfilteredTotal
          ? plural(table.total)
          : `${plural(table.total)} of ${table.unfilteredTotal}`}
      </p>
      {density && onDensityChange && <DensityToggle density={density} onChange={onDensityChange} />}
    </div>
  )
}

export function Pagination({ table, label = 'Pagination', pageSizes = [10, 25, 50] }) {
  const sizeId = useId()
  if (table.unfilteredTotal <= pageSizes[0]) return null
  return (
    <nav className="ds-pagination" aria-label={label}>
      <span>
        Showing {table.rangeStart}–{table.rangeEnd} of {table.total}
      </span>
      <div className="ds-pagination-controls">
        <label htmlFor={sizeId} className="sr-only">Rows per page</label>
        <select id={sizeId} value={table.pageSize} onChange={(event) => table.setPageSize(Number(event.target.value))}>
          {pageSizes.map((size) => <option key={size} value={size}>{size} per page</option>)}
        </select>
        <button
          type="button"
          className="btn-sm btn-secondary"
          onClick={() => table.setPage(table.page - 1)}
          disabled={table.page <= 1}
        >
          <ChevronLeft size={14} aria-hidden="true" /> Previous
        </button>
        <span aria-current="page">Page {table.page} of {table.pageCount}</span>
        <button
          type="button"
          className="btn-sm btn-secondary"
          onClick={() => table.setPage(table.page + 1)}
          disabled={table.page >= table.pageCount}
        >
          Next <ChevronRight size={14} aria-hidden="true" />
        </button>
      </div>
    </nav>
  )
}

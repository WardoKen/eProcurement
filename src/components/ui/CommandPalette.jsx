import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { CornerDownLeft, FileText, LayoutGrid, Search, Store } from 'lucide-react'
import Modal from './Modal'
import { isMac } from '../../lib/commandPalette'

// Ctrl K / Cmd K: jump to a page, a Purchase Request or a supplier.
// Presentation only: each item carries its own onSelect, supplied by the
// portal that owns the data (DESIGN.md, "Data").
//
// item: { id, group, label, detail?, meta?, keywords?, kind: 'page'|'pr'|'supplier', onSelect }

const GROUP_ORDER = ['Pages', 'Purchase requests', 'RFQs', 'Suppliers']
const KIND_ICON = { page: LayoutGrid, pr: FileText, rfq: FileText, supplier: Store }
const PER_GROUP = 8

const normalise = (value) => String(value ?? '').toLowerCase()

function rank(item, query) {
  if (!query) return item.kind === 'page' ? 0 : 1
  const label = normalise(item.label)
  const haystack = `${label} ${normalise(item.detail)} ${normalise(item.meta)} ${normalise(item.keywords)}`
  const terms = query.split(/\s+/).filter(Boolean)
  if (!terms.every((term) => haystack.includes(term))) return -1
  if (label.startsWith(query)) return 0
  if (label.includes(query)) return 1
  return 2
}

function PaletteBody({ items, onClose, placeholder }) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const listId = useId()

  const groups = useMemo(() => {
    const q = normalise(query).trim()
    const scored = items
      .map((item) => ({ item, score: rank(item, q) }))
      .filter((entry) => entry.score >= 0)
      .sort((a, b) => a.score - b.score)
    const byGroup = new Map()
    for (const { item } of scored) {
      const group = item.group || 'Pages'
      if (!byGroup.has(group)) byGroup.set(group, [])
      const list = byGroup.get(group)
      if (list.length < (q ? PER_GROUP : 6)) list.push(item)
    }
    return [...byGroup.entries()].sort((a, b) => {
      const ai = GROUP_ORDER.indexOf(a[0])
      const bi = GROUP_ORDER.indexOf(b[0])
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi)
    })
  }, [items, query])

  const flat = groups.flatMap(([, list]) => list)
  const indexed = []
  groups.reduce((offset, [group, list]) => {
    indexed.push([group, list.map((item, i) => ({ item, index: offset + i }))])
    return offset + list.length
  }, 0)
  const activeIndex = Math.min(active, Math.max(flat.length - 1, 0))

  useEffect(() => {
    const node = listRef.current?.querySelector('[aria-selected="true"]')
    node?.scrollIntoView?.({ block: 'nearest' })
  }, [activeIndex])

  const choose = (item) => {
    if (!item) return
    onClose()
    item.onSelect()
  }

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((index) => (flat.length ? (Math.min(index, flat.length - 1) + 1) % flat.length : 0))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((index) => (flat.length ? (Math.min(index, flat.length - 1) - 1 + flat.length) % flat.length : 0))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      choose(flat[activeIndex])
    }
  }

  const optionId = (index) => `${listId}-opt-${index}`

  return (
    <Modal onClose={onClose} label="Jump to" overlayClassName="cmdk-overlay" className="cmdk" initialFocusRef={inputRef}>
      <div className="cmdk-search">
        <Search size={18} aria-hidden="true" />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={flat.length ? optionId(activeIndex) : undefined}
          aria-label="Search pages and records"
          placeholder={placeholder}
          value={query}
          onChange={(event) => { setQuery(event.target.value); setActive(0) }}
          onKeyDown={onKeyDown}
          autoComplete="off"
          spellCheck="false"
        />
      </div>
      <ul className="cmdk-list" id={listId} role="listbox" aria-label="Results" ref={listRef}>
        {flat.length === 0 && <li className="cmdk-empty" role="presentation">Nothing matches “{query}”. Try a PR number, an office or a supplier name.</li>}
        {indexed.map(([group, list]) => (
          <li key={group} role="presentation">
            <div className="cmdk-group" role="presentation">{group}</div>
            <ul role="group" aria-label={group} style={{ margin: 0, padding: 0, listStyle: 'none' }}>
              {list.map(({ item, index }) => {
                const Icon = KIND_ICON[item.kind] || LayoutGrid
                return (
                  <li
                    key={item.id}
                    id={optionId(index)}
                    role="option"
                    aria-selected={index === activeIndex}
                    className="cmdk-item"
                    onMouseMove={() => { if (index !== activeIndex) setActive(index) }}
                    onClick={() => choose(item)}
                  >
                    <Icon size={16} aria-hidden="true" />
                    <span>
                      <span className="cmdk-label">{item.label}</span>
                      {item.detail && <span className="cmdk-detail">{item.detail}</span>}
                    </span>
                    {item.meta ? <span className="cmdk-meta">{item.meta}</span> : <span />}
                  </li>
                )
              })}
            </ul>
          </li>
        ))}
      </ul>
      <div className="cmdk-foot" aria-hidden="true">
        <span><kbd>↑</kbd> <kbd>↓</kbd> to move</span>
        <span><kbd><CornerDownLeft size={11} /></kbd> to open</span>
        <span><kbd>Esc</kbd> to close</span>
      </div>
    </Modal>
  )
}

export function CommandPaletteTrigger({ onOpen, label = 'Jump to a page or record' }) {
  return (
    <button type="button" className="cmdk-trigger" onClick={onOpen} aria-keyshortcuts="Control+K Meta+K">
      <Search size={15} aria-hidden="true" />
      <span>{label}</span>
      <kbd aria-hidden="true">{isMac() ? '⌘ K' : 'Ctrl K'}</kbd>
    </button>
  )
}

export default function CommandPalette({ open, onClose, items, placeholder = 'Type a PR number, office, supplier or page' }) {
  if (!open) return null
  return <PaletteBody items={items} onClose={onClose} placeholder={placeholder} />
}

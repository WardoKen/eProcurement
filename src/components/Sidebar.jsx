import { useMemo, useState } from 'react'
import { Menu, LogOut, X, Lock } from 'lucide-react'
import CommandPalette, { CommandPaletteTrigger } from './ui/CommandPalette'
import { useCommandPaletteHotkey } from '../lib/commandPalette'
import ThemeToggle from './ui/ThemeToggle'
import { withViewTransition } from '../lib/viewTransition'

// Shared portal shell for the Admin, End User and Supplier portals
// (DESIGN.md, "Shell"): a top bar (name, portal, command palette, theme,
// signed-in user, log out) and a horizontal index of the portal's pages,
// grouped by task. Below 960px the index becomes a drawer.
//
// `groups` shape: [{ section, items: [{ id, label, icon, count?, locked?, lockedReason? }] }]
// `count` shows how many records in that section are waiting on the user.
// `locked` items stay visible and selectable (they open an explanation of
// why access is pending) but are marked so users know before choosing them.
// `commands` adds records (PRs, suppliers, RFQs) to the command palette;
// every page in `groups` is always in it.
//
// The component keeps its old name so every portal imports it unchanged.

export const BrandMark = ({ size = 30 }) => (
  <svg className="brand-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <rect width="32" height="32" rx="8" fill="var(--jade)" />
    <path d="M6 20h20" stroke="var(--on-jade)" strokeWidth="3" strokeLinecap="round" />
    <circle cx="10" cy="20" r="3.4" fill="var(--jade)" stroke="var(--on-jade)" strokeWidth="2.4" />
    <circle cx="22" cy="20" r="3.4" fill="var(--marigold)" stroke="var(--marigold)" strokeWidth="2.4" />
    <path d="M10 11.5h12" stroke="var(--on-jade)" strokeOpacity="0.55" strokeWidth="2.4" strokeLinecap="round" />
  </svg>
)

const Sidebar = ({
  portalLabel,
  groups,
  activeId,
  onSelect,
  userPrimary,
  userSecondary,
  onLogout,
  commands = [],
}) => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  useCommandPaletteHotkey(setPaletteOpen)

  const go = (id) => {
    setMobileOpen(false)
    withViewTransition(() => onSelect(id))
  }

  const paletteItems = useMemo(() => [
    ...groups.flatMap((group) => group.items.map((item) => ({
      id: `page-${item.id}`,
      group: 'Pages',
      kind: 'page',
      label: item.label,
      detail: group.section,
      meta: item.count > 0 ? `${item.count} waiting` : item.locked ? 'Locked' : '',
      onSelect: () => withViewTransition(() => onSelect(item.id)),
    }))),
    ...commands,
  ], [groups, commands, onSelect])

  return (
    <>
      <header className="topbar">
        <div className="topbar-brand">
          <BrandMark />
          <span className="topbar-name">eProcure</span>
          <span className="topbar-portal">{portalLabel}</span>
        </div>
        <div className="topbar-search">
          <CommandPaletteTrigger onOpen={() => setPaletteOpen(true)} label="Jump to a page or record" />
        </div>
        <div className="topbar-end">
          <ThemeToggle />
          <div className="topbar-user">
            <span className="sr-only">Signed in as </span>
            <span className="topbar-user-name">{userPrimary}</span>
            {userSecondary && <span className="topbar-user-detail">{userSecondary}</span>}
          </div>
          <button type="button" className="topbar-logout" onClick={onLogout}>
            <LogOut size={15} aria-hidden="true" />
            <span>Log Out</span>
          </button>
          <button
            type="button"
            className="topbar-menu"
            onClick={() => setMobileOpen((open) => !open)}
            aria-expanded={mobileOpen}
            aria-controls="admin-mobile-panel"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          </button>
        </div>
      </header>

      <nav className={`index-nav ${mobileOpen ? 'is-open' : ''}`} aria-label={`${portalLabel} navigation`}>
        <div className="index-nav-inner" id="admin-mobile-panel">
          {groups.map((group, groupIndex) => {
            const headingId = group.section ? `nav-section-${portalLabel}-${groupIndex}`.replace(/\s+/g, '-') : undefined
            return (
              <div
                className="index-group"
                key={group.section || groupIndex}
                role={group.section ? 'group' : undefined}
                aria-labelledby={headingId}
              >
                {group.section && <span className="index-group-label" id={headingId}>{group.section}</span>}
                {group.items.map((item) => {
                  const isActive = activeId === item.id
                  return (
                    <button
                      type="button"
                      key={item.id}
                      className={`index-item ${isActive ? 'is-active' : ''} ${item.locked ? 'is-locked' : ''}`}
                      aria-current={isActive ? 'page' : undefined}
                      onClick={() => go(item.id)}
                      title={item.locked ? `${item.label} (${item.lockedReason || 'locked'})` : undefined}
                    >
                      <span className="index-label">{item.label}</span>
                      {item.count > 0 && (
                        <span className="nav-count">
                          {item.count}
                          <span className="sr-only"> waiting</span>
                        </span>
                      )}
                      {item.locked && (
                        <>
                          <Lock size={12} className="nav-lock" aria-hidden="true" />
                          <span className="sr-only">{` (${item.lockedReason || 'locked'})`}</span>
                        </>
                      )}
                    </button>
                  )
                })}
              </div>
            )
          })}
        </div>
      </nav>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} items={paletteItems} />
    </>
  )
}

export default Sidebar

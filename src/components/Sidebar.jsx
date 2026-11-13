import { useState } from 'react'
import { Menu, ChevronLeft, LogOut, X, Lock } from 'lucide-react'

// Shared sidebar shell for the Admin, Buyer (End User) and Supplier portals.
// Each caller supplies its own real nav items grouped into sections; this
// component only owns the shared chrome (brand mark, collapse toggle,
// active-state highlighting, user card, logout) so the three portals stop
// re-implementing the same markup with the same CSS classes.
//
// On phones the sidebar becomes a top bar and the nav is hidden behind the
// menu button; `mobileOpen` is local because it only matters at that width.
//
// `groups` shape: [{ section: 'MAIN' | undefined, items: [{ id, label, icon, locked?, lockedReason? }] }]
// `locked` items stay visible and selectable (they open an explanation of
// why access is pending) but are marked so users know before choosing them.
const Sidebar = ({
  portalLabel,
  groups,
  activeId,
  onSelect,
  navCollapsed,
  onToggleNav,
  userPrimary,
  userSecondary,
  onLogout,
}) => {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <nav className={`admin-navbar ${mobileOpen ? 'mobile-open' : ''}`} aria-label={`${portalLabel} navigation`}>
      <div className="admin-sidebar-header">
        <div className="admin-brand">
          <span className="admin-brand-mark" aria-hidden="true">eP</span>
          <span className="admin-brand-copy">
            <span className="admin-brand-name">eProcure</span>
            <span className="admin-brand-portal">{portalLabel}</span>
          </span>
        </div>
        <button
          type="button"
          className="admin-nav-toggle"
          onClick={onToggleNav}
          aria-expanded={!navCollapsed}
          aria-label={navCollapsed ? 'Expand navigation' : 'Collapse navigation'}
          title={navCollapsed ? 'Expand navigation' : 'Collapse navigation'}
        >
          {navCollapsed ? <Menu size={16} aria-hidden="true" /> : <ChevronLeft size={16} aria-hidden="true" />}
        </button>
        <button
          type="button"
          className="admin-mobile-toggle"
          onClick={() => setMobileOpen((open) => !open)}
          aria-expanded={mobileOpen}
          aria-controls="admin-mobile-panel"
          aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
        >
          {mobileOpen ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
        </button>
      </div>

      <div className="admin-mobile-panel" id="admin-mobile-panel">
        <div className="admin-nav-scroll">
          {groups.map((group, groupIndex) => {
            const headingId = group.section ? `nav-section-${portalLabel}-${groupIndex}`.replace(/\s+/g, '-') : undefined
            return (
              <div
                className="admin-nav-items"
                key={group.section || groupIndex}
                role={group.section ? 'group' : undefined}
                aria-labelledby={headingId}
              >
                {group.section && (
                  <span className="admin-nav-section-label" id={headingId}>{group.section}</span>
                )}
                {group.items.map((item) => {
                  const IconComponent = item.icon
                  const isActive = activeId === item.id
                  return (
                    <button
                      type="button"
                      key={item.id}
                      className={`admin-nav-item ${isActive ? 'active' : ''}`}
                      aria-current={isActive ? 'page' : undefined}
                      onClick={() => {
                        onSelect(item.id)
                        setMobileOpen(false)
                      }}
                      title={item.locked ? `${item.label} (${item.lockedReason || 'locked'})` : item.label}
                    >
                      <IconComponent size={14} aria-hidden="true" />
                      <span className="admin-nav-label">{item.label}</span>
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

        <div className="admin-navbar-right">
          <div className="admin-user-card">
            <span className="sr-only">Signed in as </span>
            <div className="admin-user">{userPrimary}</div>
            <div className="admin-user-email">{userSecondary}</div>
          </div>
          <button type="button" className="admin-nav-logout" onClick={onLogout} title="Log Out">
            <LogOut size={14} aria-hidden="true" />
            <span className="admin-nav-label">Log Out</span>
          </button>
        </div>
      </div>
    </nav>
  )
}

export default Sidebar

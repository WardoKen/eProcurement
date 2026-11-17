import { useState } from 'react'
import { Menu, PanelLeftClose, PanelLeftOpen, LogOut, X, Lock } from 'lucide-react'

// Shared portal shell for the Admin, End User and Supplier portals: a navy
// masthead across the top (system name, office, signed-in user, log out)
// and a light sidebar with the portal's navigation grouped by task.
// Each caller supplies its own nav items; this component owns the chrome.
//
// On phones the sidebar becomes a drawer opened from the masthead menu
// button; `mobileOpen` is local because it only matters at that width.
//
// `groups` shape: [{ section: 'Procurement' | undefined, items: [{ id, label, icon, count?, locked?, lockedReason? }] }]
// `count` shows how many records in that section are waiting on the user.
// `locked` items stay visible and selectable (they open an explanation of
// why access is pending) but are marked so users know before choosing them.

export const BrandMark = ({ size = 28 }) => (
  <svg className="brand-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <rect width="32" height="32" rx="3" fill="currentColor" />
    <path d="M7 11.5a1.5 1.5 0 0 1 1.5-1.5h5l2 2h8a1.5 1.5 0 0 1 1.5 1.5V22.5A1.5 1.5 0 0 1 23.5 24h-15A1.5 1.5 0 0 1 7 22.5z" fill="#D9B872" />
    <path d="M11 17h10M11 20h7" stroke="#1B3A5C" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
)

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
    <>
      <header className="portal-masthead">
        <div className="portal-masthead-brand">
          <BrandMark />
          <span className="portal-masthead-name">eProcure</span>
          <span className="portal-masthead-office">Bids and Awards Committee</span>
          <span className="portal-masthead-portal">{portalLabel}</span>
        </div>
        <div className="portal-masthead-user">
          <span className="sr-only">Signed in as </span>
          <span className="portal-user-name">{userPrimary}</span>
          {userSecondary && <span className="portal-user-detail">{userSecondary}</span>}
        </div>
        <button type="button" className="portal-logout" onClick={onLogout}>
          <LogOut size={15} aria-hidden="true" />
          <span>Log Out</span>
        </button>
        <button
          type="button"
          className="admin-mobile-toggle"
          onClick={() => setMobileOpen((open) => !open)}
          aria-expanded={mobileOpen}
          aria-controls="admin-mobile-panel"
          aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
        >
          {mobileOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
        </button>
      </header>

      <nav className={`admin-navbar ${mobileOpen ? 'mobile-open' : ''}`} aria-label={`${portalLabel} navigation`}>
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
                        <IconComponent size={16} aria-hidden="true" />
                        <span className="admin-nav-label">{item.label}</span>
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

          <button
            type="button"
            className="admin-nav-toggle"
            onClick={onToggleNav}
            aria-expanded={!navCollapsed}
            aria-label={navCollapsed ? 'Expand navigation' : 'Collapse navigation'}
            title={navCollapsed ? 'Expand navigation' : 'Collapse navigation'}
          >
            {navCollapsed ? <PanelLeftOpen size={16} aria-hidden="true" /> : <PanelLeftClose size={16} aria-hidden="true" />}
            <span className="admin-nav-label">Collapse menu</span>
          </button>
        </div>
      </nav>
    </>
  )
}

export default Sidebar

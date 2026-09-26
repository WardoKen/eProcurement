import { Menu, ChevronLeft, LogOut } from 'lucide-react'
import logo from '../assets/eprocure-logo.webp'

// Shared sidebar shell for the Admin, Buyer (End User) and Supplier portals.
// Each caller supplies its own real nav items grouped into sections; this
// component only owns the shared chrome (brand logo, collapse toggle,
// active-state highlighting, user card, logout) so the three portals stop
// re-implementing the same markup with the same CSS classes.
//
// `groups` shape: [{ section: 'MAIN' | undefined, items: [{ id, label, icon }] }]
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
  return (
    <nav className="admin-navbar">
      <div className="admin-sidebar-header">
        <div className="admin-brand">
          {/* Light surface keeps the logo's dark wordmark readable on the navy sidebar. */}
          <span className="logo-surface admin-brand-logo-surface">
            <img src={logo} alt="eProcure logo" className="admin-brand-logo" />
          </span>
          <span className="admin-brand-copy">
            <span className="admin-brand-portal">{portalLabel}</span>
          </span>
        </div>
        <button
          className="admin-nav-toggle"
          onClick={onToggleNav}
          aria-label={navCollapsed ? 'Open navigation' : 'Collapse navigation'}
          title={navCollapsed ? 'Open navigation' : 'Collapse navigation'}
        >
          {navCollapsed ? <Menu size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <div className="admin-nav-scroll">
        {groups.map((group, groupIndex) => (
          <div className="admin-nav-items" key={group.section || groupIndex}>
            {group.section && (
              <span className="admin-nav-section-label">{group.section}</span>
            )}
            {group.items.map((item) => {
              const IconComponent = item.icon
              return (
                <button
                  key={item.id}
                  className={`admin-nav-item ${activeId === item.id ? 'active' : ''}`}
                  onClick={() => onSelect(item.id)}
                  title={item.label}
                >
                  <IconComponent size={14} />
                  <span className="admin-nav-label">{item.label}</span>
                </button>
              )
            })}
          </div>
        ))}
      </div>

      <div className="admin-navbar-right">
        <div className="admin-user-card" aria-label="Logged in user">
          <div className="admin-user">{userPrimary}</div>
          <div className="admin-user-email">{userSecondary}</div>
        </div>
        <button className="admin-nav-logout" onClick={onLogout} title="Log Out">
          <LogOut size={14} />
          <span className="admin-nav-label">Log Out</span>
        </button>
      </div>
    </nav>
  )
}

export default Sidebar

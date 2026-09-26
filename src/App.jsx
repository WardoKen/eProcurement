import React from 'react'
import { createPortal } from 'react-dom'
import { BrowserRouter, Routes, Route, Link, Navigate, useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import {
  Check,
  Eye,
  BriefcaseBusiness,
  Pencil,
  Plus,
  CircleHelp,
  ClipboardList,
  House,
  LayoutDashboard,
  LogIn,
  LogOut,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  ScanSearch,
  Search,
  Trash2,
  Users,
  X,
  Bell,
  Calendar,
  MapPin,
  Phone,
  Mail,
  Edit2,
  FileText,
  TrendingUp,
  CheckCircle,
  Clock,
  AlertCircle,
  Save,
  FileUp,
  Download,
  Send,
  Settings,
  Building2,
  HelpCircle,
} from 'lucide-react'
import logo from './assets/eprocure-logo.webp'
import DragDropUpload, {
  SignatureValidationPanel,
  FieldShell,
  SignatureBlock,
  AutoGrowTextarea,
} from './components/DragDropUpload'
import SupplierRegistration from './components/SupplierRegistration'
import Sidebar from './components/Sidebar'
import { apiFetch } from './lib/apiClient'
import { UPLOAD_KINDS, acceptAttr, acceptedTypesLabel, fileTypeLabel, formatFileSize, validateFile } from './lib/fileValidation'
import './index.css'

// Auth/session state lives in sessionStorage so it is cleared when the browser
// (or its last tab) closes - opening the site fresh always starts logged out,
// while reloads and in-tab navigation keep the session. Any legacy copy left in
// localStorage by an older build is removed once on load so it can't resurface.
const AUTH_STORAGE_KEYS = ['eProcureUser', 'supplier_id', 'supplier_status']

// Maps the BAC review form's flat signatory field names to the signature
// detector's keys (see SIGNATURE_KEY_BY_BLOCK in DragDropUpload.jsx, which
// uses the Buyer upload wizard's split designation/name field names instead -
// the structured PurchaseRequest record only stores one name per signatory).
const ADMIN_SIGNATORY_DETECTOR_KEY = {
  requested_by: 'requested_by',
  funds_available_by: 'funds_available',
  approved_by: 'approved_by',
  twg_verified_by: 'twg',
}

try {
  AUTH_STORAGE_KEYS.forEach((key) => window.localStorage.removeItem(key))
} catch {
  // Storage may be unavailable (private mode / disabled cookies) - ignore.
}

const authStore = {
  get(key) {
    try { return window.sessionStorage.getItem(key) } catch { return null }
  },
  set(key, value) {
    try { window.sessionStorage.setItem(key, value) } catch { /* ignore */ }
  },
  remove(key) {
    try { window.sessionStorage.removeItem(key) } catch { /* ignore */ }
  },
  clear() {
    AUTH_STORAGE_KEYS.forEach((key) => authStore.remove(key))
  },
}

const SkeletonRows = ({ count = 4 }) => (
  <div className="skeleton-stack" aria-label="Loading content">
    {Array.from({ length: count }, (_, index) => (
      <div key={`skeleton-${index}`} className="skeleton-line" />
    ))}
  </div>
)

// Lightweight, dependency-free horizontal bar chart for status/category breakdowns.
const BreakdownBarList = ({ items, emptyLabel = 'No data yet.' }) => {
  const max = Math.max(1, ...items.map((item) => item.count || 0))
  if (items.length === 0) {
    return <div className="dashboard-empty-state"><span>{emptyLabel}</span></div>
  }
  return (
    <div className="stat-bar-list">
      {items.map((item) => {
        const pct = item.count > 0 ? Math.max((item.count / max) * 100, 3) : 0
        return (
          <div className="stat-bar-row" key={item.label}>
            <span className="stat-bar-label" title={item.label}>{item.label}</span>
            <div className="stat-bar-track">
              <div className="stat-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="stat-bar-count">{item.count}</span>
          </div>
        )
      })}
    </div>
  )
}

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const formatMonthKey = (monthKey) => {
  const [year, month] = (monthKey || '').split('-').map(Number)
  if (!year || !month) return monthKey || ''
  return `${MONTH_LABELS[month - 1]} '${String(year).slice(2)}`
}

// Simple 6-column vertical bar chart for the PR volume trend.
const MonthlyTrendChart = ({ data, emptyLabel = 'No purchase requests yet.' }) => {
  const max = Math.max(1, ...data.map((point) => point.count || 0))
  if (data.length === 0) {
    return <div className="dashboard-empty-state"><span>{emptyLabel}</span></div>
  }
  return (
    <div className="trend-chart">
      {data.map((point) => {
        const heightPct = point.count > 0 ? Math.max((point.count / max) * 100, 6) : 0
        return (
          <div className="trend-chart-col" key={point.month}>
            <span className="trend-chart-value">{point.count}</span>
            <div className="trend-chart-bar-track">
              <div className="trend-chart-bar" style={{ height: `${heightPct}%` }} />
            </div>
            <span className="trend-chart-label">{formatMonthKey(point.month)}</span>
          </div>
        )
      })}
    </div>
  )
}

// Streams a CSV export from an admin endpoint and triggers a browser download.
const downloadCsvExport = async (apiBaseUrl, path, filename, onError) => {
  try {
    const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}${path}`)
    if (!res.ok) throw new Error('Failed to export CSV.')
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error(error)
    if (onError) onError(error?.message || 'Failed to export CSV.')
  }
}

const verifyRecaptchaToken = async (token) => {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  if (!token) return false

  const response = await apiFetch(`${apiBaseUrl}/api/verify-recaptcha`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })

  const result = await response.json()
  return response.ok && result.success
}

const RecaptchaWidget = ({ onChange, error }) => {
  const containerRef = React.useRef(null)
  const widgetIdRef = React.useRef(null)
  const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY || ''

  React.useEffect(() => {
    if (!siteKey) return undefined

    let cancelled = false

    const renderWidget = () => {
      if (cancelled || !containerRef.current || !window.grecaptcha?.render) return

      try {
        if (widgetIdRef.current !== null && window.grecaptcha?.reset) {
          window.grecaptcha.reset(widgetIdRef.current)
        }

        widgetIdRef.current = window.grecaptcha.render(containerRef.current, {
          sitekey: siteKey,
          callback: (token) => onChange(token),
          'expired-callback': () => onChange(''),
          'error-callback': () => onChange(''),
        })
      } catch (renderError) {
        console.error('reCAPTCHA render failed', renderError)
      }
    }

    const startRender = () => {
      if (window.grecaptcha?.render) {
        renderWidget()
        return
      }

      if (window.grecaptcha?.ready) {
        window.grecaptcha.ready(() => {
          if (!cancelled) renderWidget()
        })
        return
      }

      const existingScript = document.querySelector('script[src*="recaptcha/api.js"]')
      if (existingScript) {
        if (existingScript.dataset.loaded === 'true' || window.grecaptcha?.render) {
          renderWidget()
        } else {
          existingScript.addEventListener('load', () => {
            if (!cancelled) renderWidget()
          }, { once: true })
        }
        return
      }

      const script = document.createElement('script')
      script.id = 'recaptcha-script'
      script.src = 'https://www.google.com/recaptcha/api.js?render=explicit'
      script.async = true
      script.defer = true
      script.onload = () => {
        script.dataset.loaded = 'true'
        if (!cancelled) renderWidget()
      }
      script.onerror = () => console.error('Failed to load the reCAPTCHA script')
      document.body.appendChild(script)
    }

    startRender()

    return () => {
      cancelled = true
      if (widgetIdRef.current !== null && window.grecaptcha?.reset) {
        try {
          window.grecaptcha.reset(widgetIdRef.current)
        } catch (resetError) {
          console.error('reCAPTCHA reset failed', resetError)
        }
      }
    }
  }, [onChange, siteKey])

  return (
    <div className="form-field captcha-field">
      <div ref={containerRef} className="g-recaptcha-box" />
      {!siteKey && (
        <div style={{ color: '#b91c1c', fontSize: '0.9rem', marginTop: 6 }}>
          Add a reCAPTCHA site key in VITE_RECAPTCHA_SITE_KEY to enable this widget.
        </div>
      )}
      {error && <div style={{ color: '#b91c1c', fontSize: '0.9rem', marginTop: 6 }}>{error}</div>}
    </div>
  )
}

const Home = () => (
  <div className="page-content institutional-home">
    <section className="procurement-hero">
      <div className="procurement-hero-copy">
        <p className="hero-kicker">eProcure / Procurement operations</p>
        <h1>From Purchase Request to Supplier Quotation.</h1>
        <p className="hero-lede">A document-led workspace for End Users, BAC Secretariat, and suppliers to move university procurement forward with a clear record at every stage.</p>
        <div className="hero-actions">
          <Link to="/login" className="btn-primary">Access eProcure</Link>
          <Link to="/faq" className="hero-text-link">View the process <ChevronRight size={16} /></Link>
        </div>
      </div>

      <div className="procurement-activity-panel" aria-label="eProcure workflow overview">
        <div className="activity-panel-head">
          <span className="document-tab">DOCUMENT TRAIL</span>
          <span className="activity-panel-state">Procurement workflow</span>
        </div>
        <div className="activity-document">
          <div><span className="activity-label">Purchase Request</span><strong>Original document &amp; extracted record</strong></div>
          <FileText size={24} aria-hidden="true" />
        </div>
        <ol className="activity-timeline">
          <li className="is-complete"><span>01</span><div><strong>Upload &amp; extraction</strong><small>Source document is retained with its OCR record.</small></div></li>
          <li className="is-current"><span>02</span><div><strong>BAC review</strong><small>Validate details, signatures, and PR information.</small></div></li>
          <li><span>03</span><div><strong>Supplier matching</strong><small>Group line items by procurement category.</small></div></li>
          <li><span>04</span><div><strong>RFQ &amp; quotation</strong><small>Issue supplier requests and receive responses.</small></div></li>
        </ol>
      </div>
    </section>

    <section className="home-role-strip" aria-label="eProcure workspaces">
      <article><span className="role-index">01</span><div><h2>BAC Secretariat</h2><p>Review documents, manage request queues, verify supplier compliance, and prepare RFQs.</p></div></article>
      <article><span className="role-index">02</span><div><h2>End User</h2><p>Upload an original signed Purchase Request and follow the progress of the submitted record.</p></div></article>
      <article><span className="role-index">03</span><div><h2>Supplier</h2><p>Maintain compliance documents, receive RFQs, and submit quotation documents.</p></div></article>
    </section>

    <div className="home-editorial-grid">
      <section className="home-process home-process-editorial">
        <p className="section-kicker">The operating record</p>
        <h2>One request, a visible chain of work.</h2>
        <div className="process-steps">
          <div className="process-step"><span>01</span><div><h3>Original PR</h3><p>The source file remains connected to the structured request record.</p></div></div>
          <div className="process-step"><span>02</span><div><h3>BAC validation</h3><p>Review extraction, signatures, and the official PR number in one workspace.</p></div></div>
          <div className="process-step"><span>03</span><div><h3>Category groups</h3><p>A single PR can lead to multiple supplier RFQs without losing the relationship.</p></div></div>
          <div className="process-step"><span>04</span><div><h3>Quotation record</h3><p>RFQ and quotation identifiers make supplier responses easy to trace.</p></div></div>
        </div>
      </section>

      <section className="home-notices official-bulletin">
        <div className="bulletin-head"><div><p className="section-kicker">BAC bulletin</p><h2>Procurement notices</h2></div><span>OFFICIAL UPDATES</span></div>
        <ul>
          <li><span>Supplier registration</span><p>New supplier registration deadline for the FY 2026 procurement cycle.</p></li>
          <li><span>Compliance reminder</span><p>Service providers must upload current BIR and PhilGEPS certificates.</p></li>
          <li><span>BAC meeting</span><p>Upcoming BAC meeting to review campus renovation bids on July 3.</p></li>
        </ul>
        <Link to="/faq" className="hero-text-link">Need support? Read the FAQ <ChevronRight size={16} /></Link>
      </section>
    </div>
  </div>
)

const Footer = () => (
  <footer className="site-footer">
    <div className="site-footer-inner">
      <div className="footer-left">
        <span className="logo-surface footer-logo-surface">
          <img src={logo} alt="eProcure logo" className="footer-logo" />
        </span>
        <h3>Disclaimer</h3>
        <p>
          The BAC team is not responsible for any typographical errors or misinformation presented here. The system
          only displays information provided by its clients; queries regarding postings should be directed to the
          contact person/s of the concerned party.
        </p>
      </div>

      <div className="footer-right">
        <div className="footer-block">
          <h3>Contact Information</h3>
          <ul>
            <li><Phone size={15} /> +63 912 345 6789</li>
            <li><Mail size={15} /> 4loops@4a.com</li>
          </ul>
        </div>

        <div className="footer-block">
          <h3>Office Address</h3>
          <p>Rizal 2, Bago, Asturias, Cebu</p>
          <a href="https://maps.app.goo.gl/1bKVQizTht6z4FYS9" className="footer-link">VIEW LOCATION</a>
        </div>
      </div>
    </div>

    <div className="site-footer-bottom">
      <div className="site-footer-bottom-inner">Copyright © 2026, 4Loops Boys at the Back.</div>
    </div>
  </footer>
)

export const Opportunities = () => {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  const [categories, setCategories] = React.useState([])
  const [catLoading, setCatLoading] = React.useState(true)
  const [catError, setCatError] = React.useState('')
  const [selectedCategory, setSelectedCategory] = React.useState(null)
  const [categoryPRs, setCategoryPRs] = React.useState([])
  const [prLoading, setPrLoading] = React.useState(false)
  const [prError, setPrError] = React.useState('')

  React.useEffect(() => {
    setCatLoading(true)
    setCatError('')
    apiFetch(`${apiBaseUrl}/api/categories/`)
      .then((r) => {
        if (!r.ok) throw new Error(`Server error ${r.status}`)
        return r.json()
      })
      .then((data) => {
        setCategories(data)
        setCatLoading(false)
      })
      .catch((err) => {
        setCatError('Failed to load categories. Please try again.')
        setCatLoading(false)
      })
  }, [apiBaseUrl])

  const handleCategoryClick = (cat) => {
    setSelectedCategory(cat)
    setPrLoading(true)
    setPrError('')
    setCategoryPRs([])
    apiFetch(`${apiBaseUrl}/api/pr/list/?category=${encodeURIComponent(cat.name)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Server error ${r.status}`)
        return r.json()
      })
      .then((data) => {
        setCategoryPRs(data)
        setPrLoading(false)
      })
      .catch(() => {
        setPrError('Failed to load opportunities for this category.')
        setPrLoading(false)
      })
  }

  const statusMeta = {
    uploaded: { label: 'Uploaded', className: 'status-review' },
    in_review: { label: 'In Review', className: 'status-review' },
    matched: { label: 'Matched', className: 'status-open' },
    approved: { label: 'Approved', className: 'status-open' },
    rejected: { label: 'Rejected', className: 'status-merged' },
  }

  const pageSize = 12
  const [currentPage, setCurrentPage] = React.useState(1)
  const totalPages = Math.ceil(categories.length / pageSize)
  const pageItems = categories.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  const totalOpportunities = categories.reduce((sum, item) => sum + (item.count || 0), 0)

  // Generate smart page numbers with ellipsis
  const getPageNumbers = () => {
    const pages = []
    const maxVisible = 5
    const halfVisible = Math.floor(maxVisible / 2)

    if (totalPages <= maxVisible + 2) {
      return Array.from({ length: totalPages }, (_, i) => i + 1)
    }

    pages.push(1)

    const rangeStart = Math.max(2, currentPage - halfVisible)
    const rangeEnd = Math.min(totalPages - 1, currentPage + halfVisible)

    if (rangeStart > 2) {
      pages.push('...')
    }

    for (let i = rangeStart; i <= rangeEnd; i++) {
      pages.push(i)
    }

    if (rangeEnd < totalPages - 1) {
      pages.push('...')
    }

    pages.push(totalPages)

    return pages
  }

  if (selectedCategory) {
    return (
      <div className="page-content">
        <div className="category-detail-header">
          <button className="btn-secondary" onClick={() => { setSelectedCategory(null); setCategoryPRs([]) }}>← Back to Categories</button>
          <h1>{selectedCategory.name}</h1>
          <p>{selectedCategory.count} open {selectedCategory.count === 1 ? 'opportunity' : 'opportunities'} in this category</p>
        </div>

        {prLoading && (
          <div className="skeleton-stack" style={{ marginTop: 16 }}>
            {[1, 2, 3].map((n) => <div key={n} className="skeleton-line" style={{ height: 44 }} />)}
          </div>
        )}

        {prError && <div className="alert alert-error" style={{ marginTop: 16 }}>{prError}</div>}

        {!prLoading && !prError && (
          <div className="opportunity-table-wrapper" style={{ marginTop: 16 }}>
            <table className="opportunity-table">
              <thead>
                <tr>
                  <th>PR No.</th>
                  <th>Purpose</th>
                  <th>Office / Section</th>
                  <th>Total (₱)</th>
                  <th>Date</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {categoryPRs.map((pr) => {
                  const meta = statusMeta[pr.status] || { label: pr.status, className: 'status-review' }
                  return (
                    <tr key={pr.id}>
                      <td style={{ fontWeight: 600, color: '#312e81' }}>{pr.pr_no || `PR-${pr.id}`}</td>
                      <td>{pr.purpose || '—'}</td>
                      <td>{pr.office_section || '—'}</td>
                      <td style={{ fontWeight: 600 }}>{pr.grand_total ? `₱${Number(pr.grand_total).toLocaleString()}` : '—'}</td>
                      <td>{pr.created_at ? new Date(pr.created_at).toLocaleDateString() : '—'}</td>
                      <td><span className={`status-badge ${meta.className}`}>{meta.label}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {categoryPRs.length === 0 && (
              <div style={{ padding: '40px 20px', textAlign: 'center', color: '#6b7280' }}>
                No opportunities found in this category. Check back soon!
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="page-content">
      <div className="table-header">
        <div>
          <h1>Open Opportunities</h1>
          <p>Click on a category to see open opportunities. Browse current procurement categories and view available bids.</p>
        </div>
        <div className="table-summary">
          {!catLoading && !catError && (
            <>
              <div>{categories.length} categories</div>
              <div>{totalOpportunities} open opportunities</div>
            </>
          )}
        </div>
      </div>

      {catError && <div className="alert alert-error" style={{ marginBottom: 16 }}>{catError}</div>}

      {catLoading ? (
        <div className="skeleton-stack">
          {Array.from({ length: 12 }, (_, i) => (
            <div key={i} className="skeleton-line" style={{ height: 44 }} />
          ))}
        </div>
      ) : (
        <>
          <div className="opportunity-table-wrapper">
            <table className="opportunity-table">
              <thead>
                <tr>
                  <th>Number</th>
                  <th>Category</th>
                  <th>No. Of Opportunities</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((item) => (
                  <tr key={item.id} onClick={() => handleCategoryClick(item)} className="clickable-row">
                    <td>{item.id}</td>
                    <td className="category-link">{item.name}</td>
                    <td>{item.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination-controls">
            <div className="pagination-info">
              <span className="pagination-text">Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong></span>
              <span className="pagination-separator">•</span>
              <span className="pagination-text">Showing {pageItems.length} of {categories.length} categories</span>
            </div>

            <div className="pagination-nav">
              <button
                className="btn-secondary btn-pagination"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(1)}
                title="First page"
              >
                ⟨⟨
              </button>
              <button
                className="btn-secondary btn-pagination"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                title="Previous page"
              >
                ⟨ Previous
              </button>

              <div className="pagination-pages">
                {getPageNumbers().map((page, index) => {
                  if (page === '...') {
                    return (
                      <span key={`ellipsis-${index}`} className="pagination-ellipsis">
                        …
                      </span>
                    )
                  }
                  return (
                    <button
                      key={page}
                      className={`pagination-page ${page === currentPage ? 'active' : ''}`}
                      onClick={() => setCurrentPage(page)}
                    >
                      {page}
                    </button>
                  )
                })}
              </div>

              <button
                className="btn-secondary btn-pagination"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                title="Next page"
              >
                Next ⟩
              </button>
              <button
                className="btn-secondary btn-pagination"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(totalPages)}
                title="Last page"
              >
                ⟩⟩
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

const Tracking = () => {
  const [query, setQuery] = React.useState('')
  const [fetchedPR, setFetchedPR] = React.useState(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')
  const [recentPRs, setRecentPRs] = React.useState([])
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  const normalizeValue = (value) => String(value || '').trim().toLowerCase()
  const isLikelyPrNumber = (value) => /^\d{4}-\d{2}-\d{3}$/.test(String(value || '').trim())

  const statusMeta = {
    uploaded: { label: 'Uploaded', className: 'status-review' },
    in_review: { label: 'In Review', className: 'status-review' },
    matched: { label: 'Matched', className: 'status-open' },
    approved: { label: 'Approved', className: 'status-open' },
    rejected: { label: 'Rejected', className: 'status-merged' },
  }

  const formatStatus = (status) => statusMeta[status] || { label: status || 'Unknown', className: 'status-review' }

  const loadTrackingRecords = React.useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/list/`)
      if (!res.ok) {
        throw new Error('Failed to load tracking records')
      }
      const data = await res.json()
      const records = Array.isArray(data) ? data : []
      setRecentPRs(records)
    } catch (err) {
      setError(err?.message || 'Failed to fetch PR information')
      setRecentPRs([])
    } finally {
      setLoading(false)
    }
  }, [apiBaseUrl])

  React.useEffect(() => {
    loadTrackingRecords()
  }, [loadTrackingRecords])

  async function fetchPR(e) {
    e && e.preventDefault()
    setError('')
    setFetchedPR(null)

    const trimmedQuery = query.trim()
    if (!trimmedQuery) {
      setError('Please provide a PR Control Number or employee name.')
      return
    }

    setLoading(true)
    try {
      let records = recentPRs
      if (!records.length) {
        const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/list/`)
        if (!res.ok) {
          throw new Error('Failed to load tracking records')
        }
        const data = await res.json()
        records = Array.isArray(data) ? data : []
        setRecentPRs(records)
      }

      const normalizedQuery = normalizeValue(trimmedQuery)
      const exactPrMatch = records.find((pr) => normalizeValue(pr.pr_no) === normalizedQuery)
      const partialMatch = records.find((pr) => {
        if (isLikelyPrNumber(trimmedQuery)) {
          return normalizeValue(pr.pr_no) === normalizedQuery
        }
        return [pr.requested_by, pr.entity_name, pr.pr_no].some((field) => normalizeValue(field).includes(normalizedQuery))
      })

      const match = exactPrMatch || partialMatch
      if (!match) {
        throw new Error('No matching Purchase Request found')
      }

      setFetchedPR(match)
    } catch (err) {
      setError(err?.message || 'Failed to fetch PR information')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-content">
      <div>
        <h1>Purchase Request Tracking Portal</h1>
        <p>Search by PR Control Number, Requestor, or Entity Name.</p>

        <form className="pr-lookup" onSubmit={fetchPR}>
          <div style={{display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-start', flexDirection: 'column'}}>
            <label style={{fontWeight: 600, color: '#1f2937'}}>Assigned PR Control Number</label>
            <div style={{display: 'flex', gap: 8, width: '100%', maxWidth: '500px'}}>
              <input
                placeholder="Example: 2026-01-010"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                maxLength="80"
                style={{flex: 1, padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px'}}
              />
              <button className="btn-primary" type="submit">
                <Search size={16} />
                Search
              </button>
            </div>
            <small style={{color: '#6b7280', marginTop: '4px'}}>Use PR number (YYYY-MM-NNN) or type requestor/entity keywords.</small>
          </div>
        </form>

        {loading && <div className="pr-loading"><SkeletonRows count={5} /></div>}
        {error && <div className="alert alert-error" style={{marginTop: '12px'}}>{error}</div>}

        {fetchedPR && (
          <div className="pr-details" style={{marginTop: '20px', padding: '16px', backgroundColor: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px'}}>
            <h2 style={{marginTop: 0}}>{fetchedPR.entity_name || 'Purchase Request'} <small style={{fontWeight:600,color:'#374151'}}>({fetchedPR.pr_no || `ID ${fetchedPR.id}`})</small></h2>
            <div style={{display:'flex',gap:12,alignItems:'center',marginTop:6}}>
              <div className={`status-badge ${formatStatus(fetchedPR.status).className}`}>
                {formatStatus(fetchedPR.status).label}
              </div>
              <div style={{color:'#6b7280'}}>Created: {fetchedPR.created_at ? new Date(fetchedPR.created_at).toLocaleString() : 'N/A'}</div>
            </div>
            <p style={{marginTop:12,whiteSpace:'pre-wrap'}}>{fetchedPR.purpose || 'No additional details available.'}</p>
            <div style={{marginTop: 10, color: '#374151'}}>
              <div><strong>Requestor:</strong> {fetchedPR.requested_by || 'N/A'}</div>
              <div><strong>Office:</strong> {fetchedPR.office_section || 'N/A'}</div>
              <div><strong>Items:</strong> {fetchedPR.items_count ?? 0}</div>
              <div><strong>Grand Total:</strong> {fetchedPR.grand_total ?? '0.00'}</div>
            </div>
          </div>
        )}

        <div style={{marginTop: '32px'}}>
          <h3 style={{marginBottom: '12px'}}>Recent Purchase Requests</h3>
          <ul className="pr-list">
            {recentPRs.map(pr => (
              <li key={pr.id} className="pr-item" style={{padding: '12px', borderBottom: '1px solid #e5e7eb'}}>
                <div className="pr-info"><strong>{pr.pr_no || `ID ${pr.id}`}</strong> — {pr.entity_name || 'N/A'}</div>
                <div className={`status-badge ${formatStatus(pr.status).className}`}>
                  {formatStatus(pr.status).label}
                </div>
              </li>
            ))}
            {!recentPRs.length && !loading && (
              <li className="pr-item" style={{padding: '12px', color: '#6b7280'}}>No purchase requests found.</li>
            )}
          </ul>
        </div>

        <div style={{marginTop: '32px', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px', borderLeft: '4px solid #3b82f6'}}>
          <p style={{margin: 0, color: '#1e40af'}}>
            <strong>Note:</strong> Data is pulled from the live eProcure database. If you have questions about your purchase request, contact the BAC office.
          </p>
        </div>
      </div>
    </div>
  )
}

const FAQ = () => (
  <div className="page-content">
    <div className="faq-container">
      <h1>Frequently Asked Questions & Help</h1>
      <p className="faq-intro">Find answers to common questions about eProcure and the procurement process.</p>

      <div className="faq-grid">
        {/* General Section */}
        <section className="faq-section">
          <h2>General</h2>
          
          <details className="faq-item">
            <summary><strong>What is eProcure?</strong></summary>
            <p>eProcure is the BAC's digital procurement platform that streamlines the purchase request and supplier matching process. It enables efficient procurement by digitizing workflows and automating communications.</p>
          </details>

          <details className="faq-item">
            <summary><strong>How do I access my account?</strong></summary>
            <p>Visit the login page and enter your credentials. If you don't have an account, you can register as either an end user (university/department) or supplier. Make sure to use the correct login role.</p>
          </details>

          <details className="faq-item">
            <summary><strong>I forgot my password. What should I do?</strong></summary>
            <p>Click "Forgot Password" on the login page and enter your username or registered email. If an account is found, we'll email you a link to reset your password yourself - no need to contact the BAC office.</p>
          </details>
        </section>

        {/* End User Section */}
        <section className="faq-section">
          <h2>End User Portal</h2>
          
          <details className="faq-item">
            <summary><strong>How do I submit a Purchase Request?</strong></summary>
            <p>Log in to your end user account and navigate to the Dashboard. Upload your signed PR document (PDF or image). The OCR system will automatically extract key information. BAC staff will review and number the request before supplier matching begins.</p>
          </details>

          <details className="faq-item">
            <summary><strong>What file formats are accepted for PR uploads?</strong></summary>
            <p>We accept PDF, JPG, PNG, and other common image formats. Ensure your PR document is clearly scanned or printed for best OCR accuracy.</p>
          </details>

          <details className="faq-item">
            <summary><strong>How can I track my Purchase Request status?</strong></summary>
            <p>After submitting a PR, it will appear in your Live Status tab. You'll see real-time updates as the BAC reviews and matches it with qualified suppliers.</p>
          </details>

          <details className="faq-item">
            <summary><strong>Can I edit a Purchase Request after submission?</strong></summary>
            <p>Once submitted to BAC, direct edits are not available through eProcure. If corrections are needed, contact BAC staff with details, and they can assist with amendments.</p>
          </details>
        </section>

        {/* Supplier Section */}
        <section className="faq-section">
          <h2>Supplier Portal</h2>
          
          <details className="faq-item">
            <summary><strong>How do I register as a supplier?</strong></summary>
            <p>Click "Supplier Registration" on the login page and complete the registration form with your company details, contact information, and upload required documents (DTI, BIR, business permit, PhilGEPS, etc.). BAC will review your submission and notify you of approval status.</p>
          </details>

          <details className="faq-item">
            <summary><strong>What documents are required for supplier registration?</strong></summary>
            <p>Required documents include: DTI/SEC Registration, Business Permit, BIR 2303 form, Tax Clearance, CDA Certificate (if applicable), and PhilGEPS Certificate. All documents must be valid and current.</p>
          </details>

          <details className="faq-item">
            <summary><strong>My account is showing "Pending Review". What does this mean?</strong></summary>
            <p>Your registration is being verified by BAC administrators. This typically takes 3-5 business days. Once approved, you'll receive an email notification and can immediately access all procurement opportunities.</p>
          </details>

          <details className="faq-item">
            <summary><strong>How do I respond to a Request for Quotation (RFQ)?</strong></summary>
            <p>Open the RFQ under "RFQs", download the generated RFQ PDF, then print it. Fill in the required supplier fields (brand/model, unit prices, totals, contact information), sign it, scan or photograph it as a single PDF, and upload the completed document in the "Completed RFQ Submission" area of that same RFQ.</p>
          </details>

          <details className="faq-item">
            <summary><strong>Can I change my completed RFQ after uploading it?</strong></summary>
            <p>While the RFQ is still open for a response, you can use "Replace Submission" to upload a corrected version. Your original submission is kept for the BAC's records. Once the BAC finalizes the RFQ, contact them directly for any changes.</p>
          </details>
        </section>

        {/* Technical Section */}
        <section className="faq-section">
          <h2>Technical & Account</h2>
          
          <details className="faq-item">
            <summary><strong>Is there a mobile app for eProcure?</strong></summary>
            <p>eProcure is accessible through web browsers on any device (desktop, tablet, mobile). A dedicated mobile app is not currently available, but the website is responsive and mobile-friendly.</p>
          </details>

          <details className="faq-item">
            <summary><strong>What browsers are supported?</strong></summary>
            <p>eProcure works best with modern browsers: Chrome, Firefox, Safari, and Edge (latest versions). We recommend updating your browser for the best experience.</p>
          </details>

          <details className="faq-item">
            <summary><strong>I'm having technical issues. Who should I contact?</strong></summary>
            <p>For technical support, account issues, or system problems, please contact the BAC office with a description of the issue. They can help troubleshoot or escalate to our technical team.</p>
          </details>
        </section>

        {/* Contact Section */}
        <section className="faq-section">
          <h2>Contact & Support</h2>
          
          <details className="faq-item">
            <summary><strong>How do I contact BAC support?</strong></summary>
            <p>Reach out to the BAC office through your institution's procurement department or direct BAC contact. Include your account username, the issue description, and any relevant PR/RFQ numbers.</p>
          </details>

          <details className="faq-item">
            <summary><strong>What are BAC's business hours?</strong></summary>
            <p>BAC typically operates during standard government office hours (8:00 AM - 5:00 PM, Monday-Friday). Response times may vary based on inquiry volume.</p>
          </details>
        </section>
      </div>
    </div>
  </div>
)

const Login = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialRole = searchParams.get('role') || 'buyer'
  const [role, setRole] = React.useState(initialRole)
  const [showPassword, setShowPassword] = React.useState(false)
  const resetSucceeded = searchParams.get('reset') === 'success'

  const handleSubmit = async (e) => {
    e.preventDefault()

    const fd = new FormData(e.currentTarget)
    const username = (fd.get('username') || '').toString().trim()
    const password = (fd.get('password') || '').toString()
    const selectedRole = (fd.get('role') || role || 'buyer').toString()

    if (!username || !password) {
      alert('Please enter your username and password.')
      return
    }

    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

      try {
        const response = await apiFetch(`${apiBaseUrl}/api/login/`, {
          method: 'POST',
          mode: 'cors',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password, role: selectedRole }),
        })

        const result = await response.json()
        if (!response.ok) {
          alert(result.message || 'Login failed')
          return
        }

        const user = result.user
        authStore.set('eProcureUser', JSON.stringify(user))

        if (user.role === 'supplier') {
          if (user.supplier_id) {
            authStore.set('supplier_id', user.supplier_id.toString())
          }
          if (user.supplier_status) {
            authStore.set('supplier_status', user.supplier_status)
          }
        }

        // If supplier, fetch their supplier profile ID
        if (user.role === 'supplier' && !user.supplier_id) {
          try {
            const suppliersRes = await apiFetch(`${apiBaseUrl}/api/suppliers/`)
            if (suppliersRes.ok) {
              const suppliers = await suppliersRes.json()
              // Try to find supplier by email or other identifier
              if (suppliers.length > 0) {
                authStore.set('supplier_id', suppliers[0].id.toString())
                user.supplier_id = suppliers[0].id
                authStore.set('eProcureUser', JSON.stringify(user))
              }
            }
            if (user.supplier_status) {
              authStore.set('supplier_status', user.supplier_status)
            }
          } catch (err) {
            console.error('Failed to fetch supplier profile:', err)
          }
        }

        alert(`Login successful as ${user.role}`)
        if (user.role === 'admin') {
          navigate('/admin')
        } else if (user.role === 'buyer') {
          navigate('/buyer')
        } else if (user.role === 'supplier') {
          navigate('/supplier')
        } else {
          navigate('/')
        }
      } catch (error) {
        console.error(error)
        alert('Unable to reach the authentication server.')
      }
    } catch (error) {
      console.error(error)
      alert('Unable to reach the authentication server.')
    }
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <aside className="login-context">
          <span className="logo-surface login-context-logo-surface">
            <img src={logo} alt="eProcure logo" className="login-context-logo" />
          </span>
          <p className="hero-kicker">Secure system access</p>
          <h1>University procurement, in one operating record.</h1>
          <p>Sign in to work within your role-specific eProcure workspace.</p>
          <div className="login-context-list">
            <span>End User <small>Submit and monitor Purchase Requests</small></span>
            <span>BAC Secretariat <small>Review records and manage RFQs</small></span>
            <span>Supplier <small>Respond to opportunities and quotations</small></span>
          </div>
        </aside>
        <div className="login-form-container">
          <p className="section-kicker">eProcure access</p>
          <h2>Sign in to your workspace</h2>
          <p className="login-form-intro">Select your role, then enter the credentials issued for your account.</p>
          {resetSucceeded && (
            <div className="alert alert-success" role="status">
              Your password has been reset. Please log in with your new password.
            </div>
          )}
          <form className="login-form" onSubmit={handleSubmit}>
            <div className="form-field">
              <select name="role" value={role} onChange={(e) => setRole(e.target.value)} className="form-select">
                <option value="">Select Login as</option>
                <option value="buyer">End User</option>
                <option value="supplier">Supplier</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            <div className="form-field">
              <input name="username" type="text" placeholder="Username" />
            </div>

            <div className="form-field password-field">
              <div className="password-input-wrapper">
                <input
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Password"
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.97 10.97 0 0 1 12 20c-5 0-9.27-3-11-7 1.18-2.54 3.16-4.7 5.57-5.88" />
                      <path d="M1 1l22 22" />
                      <path d="M9.88 9.88A3 3 0 0 0 14.12 14.12" />
                      <path d="M14.12 9.88a3 3 0 0 1-4.24 4.24" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <div className="form-actions login-actions">
              <button type="button" className="btn-secondary" onClick={() => navigate('/supplier/register')}>Register as Supplier</button>
              <button type="button" className="btn-outline" onClick={() => navigate('/forgot-password')}>Forgot Password</button>
              <button type="submit" className="btn-login">Log In</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

// A password-reset request must never let the caller tell "no such account"
// apart from "email sent" - the confirmation below is shown unconditionally,
// regardless of what the backend actually did (see api.views.forgot_password).
const ForgotPassword = () => {
  const navigate = useNavigate()
  const [identifier, setIdentifier] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [submitted, setSubmitted] = React.useState(false)
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    try {
      await apiFetch(`${apiBaseUrl}/api/forgot-password/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username_or_email: identifier.trim() }),
      })
    } catch (error) {
      console.error(error)
      // Network failures are not surfaced differently either - the same
      // confirmation is shown either way, below.
    } finally {
      setSubmitting(false)
      setSubmitted(true)
    }
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-form-container">
          <h2>FORGOT PASSWORD</h2>
          {submitted ? (
            <>
              <div className="alert alert-success" role="status">
                If an account exists for that username or email, a password reset link has been sent. Please check your inbox.
              </div>
              <div className="form-actions login-actions">
                <button type="button" className="btn-login" onClick={() => navigate('/login')}>Back to Log In</button>
              </div>
            </>
          ) : (
            <form className="login-form" onSubmit={handleSubmit}>
              <p className="helper-text">Enter your username or the email address on your account and we'll send you a link to reset your password.</p>
              <div className="form-field">
                <input
                  name="identifier"
                  type="text"
                  placeholder="Username or Email"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  required
                />
              </div>
              <div className="form-actions login-actions">
                <button type="button" className="btn-outline" onClick={() => navigate('/login')}>Cancel</button>
                <button type="submit" className="btn-login" disabled={submitting}>{submitting ? 'Sending...' : 'Send Reset Link'}</button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

const ResetPassword = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = (searchParams.get('token') || '').trim()
  const [password, setPassword] = React.useState('')
  const [confirmPassword, setConfirmPassword] = React.useState('')
  const [error, setError] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [tokenRejected, setTokenRejected] = React.useState(false)
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      const response = await apiFetch(`${apiBaseUrl}/api/reset-password/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      })
      const result = await response.json().catch(() => null)
      if (!response.ok) {
        setTokenRejected(true)
        setError(result?.message || 'This password reset link is invalid or has expired.')
        return
      }
      navigate('/login?reset=success')
    } catch (err) {
      console.error(err)
      setError('Unable to reach the server. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!token || tokenRejected) {
    return (
      <div className="login-page">
        <div className="login-container">
          <div className="login-form-container">
            <h2>RESET PASSWORD</h2>
            <div className="alert alert-error" role="alert">
              {error || 'This password reset link is invalid or missing. Please request a new one.'}
            </div>
            <div className="form-actions login-actions">
              <button type="button" className="btn-login" onClick={() => navigate('/forgot-password')}>Request a New Link</button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-form-container">
          <h2>RESET PASSWORD</h2>
          <form className="login-form" onSubmit={handleSubmit}>
            <div className="form-field">
              <input
                type="password"
                placeholder="New Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            <div className="form-field">
              <input
                type="password"
                placeholder="Confirm New Password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                minLength={8}
                required
              />
            </div>
            {error && (
              <div className="alert alert-error" role="alert">{error}</div>
            )}
            <div className="form-actions login-actions">
              <button type="button" className="btn-outline" onClick={() => navigate('/login')}>Cancel</button>
              <button type="submit" className="btn-login" disabled={submitting}>{submitting ? 'Saving...' : 'Reset Password'}</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

// ─── WorkflowStepper ─────────────────────────────────────────────────────────

const WorkflowStepper = ({ current }) => {
  const steps = [
    { key: 'upload', label: 'Upload PR' },
    { key: 'ocr', label: 'OCR Extraction' },
    { key: 'review', label: 'Review & Edit' },
    { key: 'save', label: 'Save Purchase Request' },
    { key: 'categories', label: 'Assign Categories' },
    { key: 'matching', label: 'Supplier Matching' },
    { key: 'rfq', label: 'RFQ Review' },
  ]
  const order = steps.map((s) => s.key)
  const currentIndex = order.indexOf(current)
  return (
    <div className="workflow-stepper">
      {steps.map((step, i) => {
        const isDone = i < currentIndex
        const isActive = i === currentIndex
        return (
          <React.Fragment key={step.key}>
            {i > 0 && <span className="workflow-step-arrow">→</span>}
            <div className={`workflow-step${isDone ? ' step-done' : ''}${isActive ? ' step-active' : ''}`}>
              <span className="step-icon">{isDone ? '✓' : isActive ? '►' : '○'}</span>
              <span className="step-label">{step.label}</span>
            </div>
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ─── SearchableSelect ────────────────────────────────────────────────────────
// A type-to-filter dropdown for long option lists (e.g. procurement categories).
// The list is rendered in a body portal with fixed positioning so it floats
// over the page - a scrolling parent never clips it and the table never grows.

const SearchableSelect = ({ value, onChange, options, placeholder = 'Select…', invalid = false, id }) => {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const [activeIndex, setActiveIndex] = React.useState(0)
  const [menuRect, setMenuRect] = React.useState(null)
  const rootRef = React.useRef(null)
  const inputRef = React.useRef(null)
  const listRef = React.useRef(null)

  const filtered = React.useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return options
    return options.filter((option) => option.toLowerCase().includes(term))
  }, [options, query])

  const reposition = React.useCallback(() => {
    const input = inputRef.current
    if (!input) return
    const rect = input.getBoundingClientRect()
    const belowSpace = window.innerHeight - rect.bottom
    const maxHeight = Math.min(260, Math.max(belowSpace, rect.top) - 12)
    const dropUp = belowSpace < 180 && rect.top > belowSpace
    setMenuRect({
      left: rect.left,
      width: rect.width,
      top: dropUp ? undefined : rect.bottom + 4,
      bottom: dropUp ? window.innerHeight - rect.top + 4 : undefined,
      maxHeight,
    })
  }, [])

  const openMenu = React.useCallback(() => {
    setOpen(true)
    setActiveIndex(0)
    reposition()
  }, [reposition])

  React.useEffect(() => {
    if (!open) return undefined
    const onScroll = () => reposition()
    const onDocMouseDown = (event) => {
      if (rootRef.current?.contains(event.target)) return
      if (listRef.current?.contains(event.target)) return
      setOpen(false)
      setQuery('')
    }
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    document.addEventListener('mousedown', onDocMouseDown)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
      document.removeEventListener('mousedown', onDocMouseDown)
    }
  }, [open, reposition])

  const choose = (option) => {
    onChange(option)
    setOpen(false)
    setQuery('')
  }

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!open) { openMenu(); return }
      setActiveIndex((index) => Math.min(index + 1, filtered.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => Math.max(index - 1, 0))
    } else if (event.key === 'Enter' && open) {
      event.preventDefault()
      if (filtered[activeIndex]) choose(filtered[activeIndex])
    } else if (event.key === 'Escape') {
      setOpen(false)
      setQuery('')
    }
  }

  return (
    <div className={`searchable-select${invalid ? ' is-invalid' : ''}`} ref={rootRef}>
      <input
        id={id}
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        className="searchable-select-input"
        value={open ? query : value}
        placeholder={value || placeholder}
        onFocus={openMenu}
        onChange={(event) => { setQuery(event.target.value); openMenu() }}
        onKeyDown={onKeyDown}
      />
      {value && !open && (
        <button
          type="button"
          className="searchable-select-clear"
          aria-label="Clear category"
          onClick={() => onChange('')}
        >
          ×
        </button>
      )}
      {open && menuRect && createPortal(
        <ul
          ref={listRef}
          className="searchable-select-list"
          role="listbox"
          style={{
            position: 'fixed',
            left: menuRect.left,
            width: menuRect.width,
            top: menuRect.top,
            bottom: menuRect.bottom,
            maxHeight: menuRect.maxHeight,
          }}
        >
          {filtered.length === 0 ? (
            <li className="searchable-select-empty">No matching category</li>
          ) : (
            filtered.map((option, index) => (
              <li
                key={option}
                role="option"
                aria-selected={option === value}
                className={`searchable-select-option${index === activeIndex ? ' is-active' : ''}${option === value ? ' is-selected' : ''}`}
                onMouseEnter={() => setActiveIndex(index)}
                onMouseDown={(event) => { event.preventDefault(); choose(option) }}
              >
                {option}
              </li>
            ))
          )}
        </ul>,
        document.body,
      )}
    </div>
  )
}

// ─── AssignCategories ─────────────────────────────────────────────────────────

const AssignCategories = ({ prId, apiBase, onComplete, onBack }) => {
  const [categories, setCategories] = React.useState([])
  const [items, setItems] = React.useState([])
  const [assignments, setAssignments] = React.useState({})
  const [loading, setLoading] = React.useState(true)
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState('')
  const [touched, setTouched] = React.useState(false)

  React.useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([
      apiFetch(`${apiBase}/api/categories/`).then((r) => { if (!r.ok) throw new Error('Failed to load categories'); return r.json() }),
      apiFetch(`${apiBase}/api/pr/${prId}/items/`).then((r) => { if (!r.ok) throw new Error('Failed to load PR items'); return r.json() }),
    ])
      .then(([cats, itms]) => {
        setCategories(cats)
        setItems(itms)
        const init = {}
        for (const item of itms) {
          if (item.category) {
            init[item.id] = item.category
          }
        }
        setAssignments(init)
        setLoading(false)
      })
      .catch((err) => { setError(err.message || 'Failed to load data'); setLoading(false) })
  }, [prId, apiBase])

  const categoryNames = React.useMemo(
    () => categories.map((cat) => cat.name).sort((a, b) => a.localeCompare(b)),
    [categories],
  )
  const allAssigned = items.length > 0 && items.every((item) => assignments[item.id])
  const unassignedCount = items.filter((item) => !assignments[item.id]).length

  async function handleSave() {
    setTouched(true)
    if (!allAssigned) return
    setSaving(true)
    setError('')
    try {
      const res = await apiFetch(`${apiBase}/api/pr/${prId}/items/categories/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assignments: items.map((item) => ({ item_id: item.id, category: assignments[item.id] || '' })) }),
      })
      if (!res.ok) { const e = await res.json().catch(() => null); throw new Error(e?.message || 'Failed to save') }
      onComplete(prId)
    } catch (err) {
      setError(err.message || 'Failed to save categories')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="supplier-section">
        <WorkflowStepper current="categories" />
        <div className="skeleton-stack" style={{ marginTop: 24 }}>
          {[1, 2, 3, 4].map((n) => <div key={n} className="skeleton-line" style={{ height: 48 }} />)}
        </div>
      </div>
    )
  }

  return (
    <div className="supplier-section">
      <WorkflowStepper current="categories" />

      <div className="supplier-header" style={{ marginTop: 20 }}>
        <h1>Assign Categories</h1>
        <p>Assign a category to each item in Purchase Request <strong>#{prId}</strong>, then click Save.</p>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 14 }}>{error}</div>}
      {touched && !allAssigned && (
        <div className="alert alert-warning" style={{ marginBottom: 14 }}>
          {unassignedCount} item{unassignedCount !== 1 ? 's' : ''} still need a category before you can continue.
        </div>
      )}

      <div className="card" style={{ overflow: 'auto', marginBottom: 18 }}>
        <table className="cat-assign-table">
          <thead>
            <tr className="cat-assign-head">
              <th>#</th>
              <th>Item Description</th>
              <th>Qty</th>
              <th>Unit Cost</th>
              <th style={{ minWidth: 220 }}>Final Category</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => {
              const assigned = assignments[item.id] || ''
              const missing = touched && !assigned
              return (
                <tr key={item.id} className={`cat-assign-row${missing ? ' cat-row-missing' : ''}`}>
                  <td>{idx + 1}</td>
                  <td style={{ fontWeight: 500 }}>{item.item_description || '—'}</td>
                  <td>{Number(item.quantity)}</td>
                  <td>₱{Number(item.unit_cost).toLocaleString()}</td>
                  <td>
                    <SearchableSelect
                      id={`cat-select-${item.id}`}
                      value={assigned}
                      onChange={(name) => setAssignments((prev) => ({ ...prev, [item.id]: name }))}
                      options={categoryNames}
                      placeholder="Search category…"
                      invalid={missing}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {items.length === 0 && (
          <div style={{ padding: '36px 20px', textAlign: 'center', color: '#6b7280' }}>
            No items found for this Purchase Request.
          </div>
        )}
      </div>

      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onBack}>← Back to PR Upload</button>
        <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save Categories & Continue →'}
        </button>
        {touched && !allAssigned && (
          <span style={{ color: '#b91c1c', fontSize: 13, marginLeft: 4 }}>
            {unassignedCount} item{unassignedCount !== 1 ? 's' : ''} unassigned
          </span>
        )}
      </div>
    </div>
  )
}

// The generated RFQ PDF is always written to the same file path, so its URL
// never changes between saves. Append a fresh token so the browser (and the
// preview iframe) fetch the newly rendered document instead of a cached copy.
const bustCache = (url) => {
  if (!url) return ''
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}v=${Date.now()}`
}

// ─── SupplierMatchingView ─────────────────────────────────────────────────────

const RFQPreparation = ({ prId, apiBase, supplier, prDetails, onBack }) => {
  const [rfq, setRfq] = React.useState(null)
  const [subject, setSubject] = React.useState('')
  const [message, setMessage] = React.useState('')
  const [abc, setAbc] = React.useState('')
  const [quotationBasis, setQuotationBasis] = React.useState('LOT')
  const [modeOfProcurement, setModeOfProcurement] = React.useState('')
  const [procurementModes, setProcurementModes] = React.useState([])
  const [additionalNotes, setAdditionalNotes] = React.useState('')
  const [pendingAction, setPendingAction] = React.useState('')
  const [error, setError] = React.useState('')
  const [notice, setNotice] = React.useState('')
  const [previewUrl, setPreviewUrl] = React.useState('')
  const rfqApiBase = apiBase.replace(/\/$/, '')
  const busy = Boolean(pendingAction)
  const isSent = rfq?.status === 'sent'
  const isManualSelection = (rfq?.selection_type || supplier.selection_type) === 'manual_bac'
  // The procurement category group this RFQ serves, and the exact PR items in it.
  const groupCategory = supplier.matched_category || rfq?.category || ''
  const groupItems = React.useMemo(() => {
    if (Array.isArray(supplier.groupItems) && supplier.groupItems.length) return supplier.groupItems
    if (Array.isArray(rfq?.purchase_request?.items)) return rfq.purchase_request.items
    const all = prDetails?.items || []
    return groupCategory ? all.filter((it) => (it.category || '') === groupCategory) : all
  }, [supplier.groupItems, rfq?.purchase_request?.items, prDetails?.items, groupCategory])

  // The ABC is always the PR's full grand total, never the category group's
  // subtotal. The backend is authoritative; this is only the pre-save display.
  const computedAbc = React.useMemo(() => {
    const total = Number(prDetails?.grand_total ?? 0)
    return Number.isFinite(total) ? `₱${total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '₱0.00'
  }, [prDetails?.grand_total])

  React.useEffect(() => {
    const headers = { 'Content-Type': 'application/json' }
    apiFetch(`${rfqApiBase}/api/pr/${prId}/rfq/`, { headers })
      .then((response) => response.ok ? response.json() : { rfqs: [] })
      .then((data) => {
        const wantCategory = supplier.matched_category || ''
        const forSupplier = (data.rfqs || []).filter((item) => (
          item.supplier.id === supplier.id
          && (!wantCategory || (item.category || '') === wantCategory)
        ))
        const existing = forSupplier.find((item) => item.status !== 'sent') || forSupplier.find((item) => item.status === 'sent')
        if (existing) {
          setRfq(existing)
          setSubject(existing.subject)
          setMessage(existing.message)
          setAbc(existing.abc || computedAbc)
          setQuotationBasis(existing.quotation_basis === 'LINE' ? 'LINE' : 'LOT')
          setModeOfProcurement(existing.mode_of_procurement || '')
          setAdditionalNotes(existing.additional_notes || '')
          setPreviewUrl(bustCache(existing.pdf_url))
          if (existing.status === 'sent') {
            setNotice(`RFQ ${existing.rfq_no} was already sent to ${supplier.email || 'the supplier'}. It can no longer be edited.`)
          }
        } else {
          setAbc(computedAbc)
          setSubject(`Request for Quotation - PR ${prDetails?.pr_no || prId}`)
          setMessage(
            `Dear ${supplier.contact_person || supplier.company_name},\n\n` +
            'Greetings.\n\n' +
            `The ${prDetails?.entity_name || 'requesting office'} is requesting a quotation for the items/services specified in Purchase Request ${prDetails?.pr_no || prId}.\n\n` +
            'Please provide your quotation based on the specifications and quantities indicated.\n\n' +
            'Kindly submit your quotation through the eProcure system or through the designated submission process.\n\n' +
            'Thank you.\n\nRegards,\nBAC Secretariat'
          )
        }
      })
      .catch(() => {})
  }, [computedAbc, prId, rfqApiBase, prDetails?.entity_name, prDetails?.pr_no, supplier.company_name, supplier.contact_person, supplier.email, supplier.id, supplier.matched_category])

  React.useEffect(() => {
    apiFetch(`${rfqApiBase}/api/procurement-modes/`)
      .then((response) => response.ok ? response.json() : { modes: [] })
      .then((data) => setProcurementModes(Array.isArray(data.modes) ? data.modes : []))
      .catch(() => {})
  }, [rfqApiBase])

  const items = groupItems
  const canPrepare = Boolean(modeOfProcurement.trim() && subject.trim() && message.trim())

  // Save applies the current edits and always refreshes the RFQ preview.
  // Send delivers the saved RFQ (with its PDF) to the supplier by email.
  const persistRfq = async (action) => {
    const send = action === 'send'
    if (!canPrepare) {
      setError(!modeOfProcurement.trim()
        ? 'Please enter a mode of procurement.'
        : 'Subject and RFQ message are required.')
      return
    }
    if (send) {
      if (!rfq) {
        setError('Save the RFQ first, then send it to the supplier.')
        return
      }
      if (!supplier.email) {
        setError('The selected supplier has no email address on file.')
        return
      }
      if (!window.confirm(`Send RFQ ${rfq.rfq_no} to ${supplier.email}? Once sent it can no longer be edited.`)) {
        return
      }
    }
    setPendingAction(action)
    setError('')
    setNotice('')
    try {
      const response = await apiFetch(`${rfqApiBase}/api/pr/${prId}/rfq/`, {
        method: rfq ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          supplier_id: supplier.id,
          selection_type: isManualSelection ? 'manual_bac' : 'category_match',
          // The procurement category group this RFQ serves - always sent so the
          // backend scopes the RFQ to that group's items only.
          category: groupCategory || supplier.matched_category || rfq?.category || '',
          rfq_id: rfq?.id,
          subject,
          message,
          quotation_basis: quotationBasis,
          mode_of_procurement: modeOfProcurement,
          additional_notes: additionalNotes,
          generate_pdf: true,
          preview: !send,
          send,
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || `Unable to ${send ? 'send' : 'save'} RFQ (HTTP ${response.status})`)
      setRfq(data)
      setSubject(data.subject)
      setMessage(data.message)
      setAbc(data.abc || computedAbc)
      setQuotationBasis(data.quotation_basis === 'LINE' ? 'LINE' : 'LOT')
      setModeOfProcurement(data.mode_of_procurement || '')
      setAdditionalNotes(data.additional_notes || '')
      setPreviewUrl(bustCache(data.pdf_url))
      setNotice(send
        ? `RFQ ${data.rfq_no} sent to ${supplier.email}. It can no longer be edited.`
        : 'Changes saved. The RFQ preview below has been updated.')
    } catch (saveError) {
      setError(saveError.message === 'Failed to fetch'
        ? `Unable to reach the backend at ${rfqApiBase}. Please verify that Django is running.`
        : (saveError.message || 'Unable to save RFQ'))
    } finally {
      setPendingAction('')
    }
  }

  return (
    <div className="supplier-section">
      <WorkflowStepper current="rfq" />
      <div className="supplier-header" style={{ marginTop: 20 }}>
        <h1>RFQ Preparation</h1>
        <p>Edit the RFQ details, click <strong>Save RFQ</strong> to apply changes and refresh the preview, then <strong>Send RFQ to Supplier</strong> to deliver it.</p>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className={`alert ${isSent ? 'alert-success' : 'alert-info'}`}>{notice}</div>}
      {isManualSelection && (
        <div className="alert alert-warning">
          <strong>Manual BAC Selection.</strong> You are proceeding with a supplier outside the PR's registered
          procurement category. This choice is recorded on the RFQ for audit and does not change the PR or the
          supplier's registered categories.
        </div>
      )}
      <div className="card rfq-review-card">
        {rfq?.pdf_url && <p><a className="btn-secondary" href={bustCache(rfq.pdf_url)} download target="_blank" rel="noreferrer">Download RFQ PDF</a></p>}
        <div className="detail-grid">
          <div><strong>PR No.: </strong><span>{prDetails?.pr_no || `PR-${prId}`}</span></div>
          <div><strong>PR Date: </strong><span>{prDetails?.date || 'N/A'}</span></div>
          <div><strong>Requesting Office / Entity: </strong><span>{prDetails?.office_section || prDetails?.entity_name || 'N/A'}</span></div>
          <div><strong>Category: </strong><span>{prDetails?.category || items.find((item) => item.category)?.category || 'N/A'}</span></div>
          <div><strong>Supplier: </strong><span>{supplier.company_name}</span></div>
          <div><strong>Selection Type: </strong><span>{isManualSelection ? 'Manual BAC Selection' : 'Category Match'}</span></div>
          <div><strong>Supplier Contact: </strong><span>{supplier.contact_person || 'N/A'}</span></div>
          <div><strong>Supplier Email: </strong><span>{supplier.email || 'N/A'}</span></div>
          <div><strong>Supplier TIN: </strong><span>{supplier.tin || 'N/A'}</span></div>
          <div><strong>Status: </strong><span className={`status-badge ${rfq?.rfq_no ? 'status-open' : 'status-draft'}`}>{rfq?.status || 'Draft'}</span></div>
          <div><strong>Quotation No.: </strong><span>{rfq?.quotation_no || 'Not Yet Issued'}</span></div>
          {rfq?.rfq_no && (
            <>
              <div><strong>Delivery Method: </strong><span>{rfq.delivery_method === 'manual' ? 'Manual' : 'System'}</span></div>
              <div><strong>Issued: </strong><span>{rfq.sent_at ? new Date(rfq.sent_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A'}</span></div>
            </>
          )}
        </div>
      </div>
      <div className="card rfq-review-card">
        <h2>RFQ Information</h2>
        <div className="detail-grid">
          <label className="form-field">
            <span>Mode of Procurement *</span>
            <input
              type="text"
              list="procurement-mode-options"
              value={modeOfProcurement}
              onChange={(event) => setModeOfProcurement(event.target.value)}
              disabled={isSent}
              placeholder="Select a suggestion or type a mode"
              maxLength={200}
            />
            <datalist id="procurement-mode-options">
              {procurementModes.map((mode) => <option key={mode} value={mode} />)}
            </datalist>
          </label>
          <label className="form-field"><span>ABC</span><input value={abc || computedAbc} readOnly /></label>
          <label className="form-field">
            <span>Quotation Basis</span>
            <select value={quotationBasis} onChange={(event) => setQuotationBasis(event.target.value)} disabled={isSent}>
              <option value="LOT">Lot</option>
              <option value="LINE">Line</option>
            </select>
          </label>
        </div>
        {!modeOfProcurement.trim() && (
          <p className="helper-text" style={{ marginTop: 4 }}>Choose a suggested procurement procedure or type your own. This is separate from the PR category.</p>
        )}
        <p className="helper-text" style={{ marginTop: 4 }}>
          {quotationBasis === 'LINE'
            ? 'The RFQ note will state the award is on a per line item basis; suppliers may quote for one or more items.'
            : 'The RFQ note will state the award is on a LOT basis; suppliers must quote all items to avoid disqualification.'}
        </p>
        <label className="form-field"><span>Additional RFQ Notes</span><textarea rows="5" value={additionalNotes} onChange={(event) => setAdditionalNotes(event.target.value)} placeholder="Optional terms, notes, or instructions for the supplier" disabled={isSent} /></label>
      </div>
      <div className="card rfq-review-card">
        <h2>Requested Items</h2>
        <div className="opportunity-table-wrapper">
          <table className="opportunity-table">
            <thead><tr><th>#</th><th>Unit</th><th>Description</th><th>Quantity</th><th>Category</th></tr></thead>
            <tbody>{items.map((item, index) => (
              <tr key={item.id || index}>
                <td>{index + 1}</td><td>{item.unit || 'N/A'}</td><td>{item.item_description || 'N/A'}</td><td>{item.quantity}</td><td>{item.category || 'N/A'}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        {items.length === 0 && <p>No requested items found.</p>}
      </div>
      <div className="card rfq-review-card">
        <label className="form-field"><span>Subject</span><input value={subject} onChange={(event) => setSubject(event.target.value)} placeholder={`Request for Quotation - PR ${prDetails?.pr_no || prId}`} disabled={isSent} /></label>
        <label className="form-field"><span>RFQ Message</span><textarea rows="12" value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Enter the RFQ message" disabled={isSent} /></label>
      </div>
      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onBack} disabled={busy}>Back to Matching</button>
        {!isSent && (
          <>
            <button type="button" className="btn-secondary" onClick={() => persistRfq('save')} disabled={busy || !canPrepare}>{pendingAction === 'save' ? 'Saving...' : 'Save RFQ'}</button>
            <button type="button" className="btn-primary" onClick={() => persistRfq('send')} disabled={busy || !rfq || !canPrepare || !supplier.email} title={!rfq ? 'Save the RFQ first' : undefined}>{pendingAction === 'send' ? 'Sending...' : 'Send RFQ to Supplier'}</button>
          </>
        )}
      </div>
      {!isSent && !rfq && (
        <p className="helper-text">Save the RFQ to enable sending it to the supplier.</p>
      )}
      {previewUrl && (
        <div className="card rfq-review-card" style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h2 style={{ margin: 0 }}>RFQ Preview</h2>
            <a href={previewUrl} target="_blank" rel="noreferrer" className="btn-secondary">Open PDF</a>
          </div>
          {(rfq?.mode_of_procurement || modeOfProcurement) && (
            <p className="helper-text" style={{ marginBottom: 12 }}>Mode of Procurement: <strong>{rfq?.mode_of_procurement || modeOfProcurement}</strong></p>
          )}
          <iframe key={previewUrl} title="RFQ preview" src={previewUrl} style={{ width: '100%', minHeight: '820px', border: '1px solid #d1d5db', borderRadius: 8 }} />
        </div>
      )}
    </div>
  )
}

const rfqStatusLabelText = (status) => {
  if (status === 'quotation_received') return 'Quotation Received'
  if (status === 'completed') return 'RFQ Completed'
  return 'RFQ Sent'
}

// One collapsible procurement category group inside Supplier Matching. Its
// suppliers, "other supplier" search and manual-RFQ action are all scoped to
// this group only.
const ProcurementGroup = ({ group, expanded, onToggle, apiBase, issuedFor, onSelectSupplier, onManualRfq }) => {
  const [query, setQuery] = React.useState('')
  const [results, setResults] = React.useState([])
  const [busy, setBusy] = React.useState(false)
  const [ran, setRan] = React.useState(false)
  const [searchError, setSearchError] = React.useState('')
  const matchedIds = React.useMemo(() => new Set(group.suppliers.map((s) => s.id)), [group.suppliers])

  const runSearch = async (event) => {
    if (event) event.preventDefault()
    setBusy(true); setSearchError(''); setRan(true)
    try {
      const params = new URLSearchParams()
      if (query.trim()) params.set('name', query.trim())
      const res = await apiFetch(`${apiBase}/api/suppliers/search/?${params.toString()}`)
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.message || `Search failed (HTTP ${res.status})`)
      setResults((Array.isArray(data.results) ? data.results : []).filter((s) => !matchedIds.has(s.id)))
    } catch (err) {
      setSearchError(err.message || 'Supplier search failed'); setResults([])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`procurement-group ${expanded ? 'expanded' : ''}`}>
      <button type="button" className="procurement-group-header" onClick={onToggle} aria-expanded={expanded}>
        <span className="procurement-group-chevron">{expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
        <span className="procurement-group-title">{group.category}</span>
        <span className="procurement-group-count">
          {group.item_count} Item{group.item_count !== 1 ? 's' : ''} &middot; {group.suppliers.length} matched supplier{group.suppliers.length !== 1 ? 's' : ''}
        </span>
      </button>

      {expanded && (
        <div className="procurement-group-body">
          <div className="card" style={{ padding: 14, marginBottom: 16 }}>
            <strong>Items</strong>
            <ol style={{ margin: '6px 0 0', paddingLeft: 20 }}>
              {group.items.map((it) => (
                <li key={it.id}>{it.item_description || 'N/A'} ({Number(it.quantity)} {it.unit || 'units'})</li>
              ))}
            </ol>
          </div>

          <div className="match-section-heading"><h3>Category-Matched Suppliers</h3></div>
          {group.suppliers.length === 0 ? (
            <div className="alert alert-info">
              No eligible suppliers are registered under this category. Search <strong>Other Registered Suppliers</strong> or add an unregistered supplier below.
            </div>
          ) : (
            <div className="supplier-match-grid">
              {group.suppliers.map((s) => {
                const status = issuedFor(group.category, s.id)
                return (
                  <article key={s.id} className="supplier-match-card">
                    <div className="supplier-match-head">
                      <h4>{s.company_name}</h4>
                      <span className="status-badge status-open">{s.status || 'Approved'}</span>
                    </div>
                    <div className="supplier-match-body">
                      <div><span className="match-tag match-tag-category">✓ Category Match</span></div>
                      <div>Coverage: {group.item_count}/{group.item_count} items</div>
                      {s.contact_person && <div><strong>Contact:</strong> {s.contact_person}</div>}
                      {s.email && <div><strong>Email:</strong> {s.email}</div>}
                      <div><strong>Compliance:</strong> <span className="status-badge status-open">{s.compliance_status || 'Eligible'} ({s.compliance_percentage ?? 100}%)</span></div>
                    </div>
                    <div className="supplier-match-foot">
                      {status ? (
                        <span className="status-badge status-open">{rfqStatusLabelText(status)}</span>
                      ) : (
                        <button type="button" className="btn-sm btn-primary" onClick={() => onSelectSupplier(s, group, 'category_match')}>Request Quotation</button>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          )}

          <div className="match-section-divider" />
          <div className="match-section-heading">
            <h3>Other Registered Suppliers</h3>
            <p className="helper-text">
              Suppliers not registered under this category. Selecting one is recorded as a <strong>Manual BAC Selection</strong> for this group only.
            </p>
          </div>
          <form className="other-supplier-search" onSubmit={runSearch}>
            <label className="form-field" style={{ flex: 1, margin: 0 }}>
              <span>Search by supplier name</span>
              <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="🔍 Search supplier name..." />
            </label>
            <button type="submit" className="btn-primary" disabled={busy}>{busy ? 'Searching…' : 'Search'}</button>
          </form>
          {searchError && <div className="alert alert-error" style={{ marginTop: 10 }}>{searchError}</div>}
          {ran && !searchError && (
            results.length === 0 ? (
              <div className="supplier-match-empty">No other registered suppliers found.</div>
            ) : (
              <div className="supplier-match-grid">
                {results.map((s) => {
                  const status = issuedFor(group.category, s.id)
                  return (
                    <article key={s.id} className="supplier-match-card supplier-match-card-manual">
                      <div className="supplier-match-head">
                        <h4>{s.company_name}</h4>
                        <span className={`status-badge ${s.status === 'Approved' ? 'status-open' : 'status-review'}`}>{s.status || 'Pending'}</span>
                      </div>
                      <div className="supplier-match-body">
                        <div><span className="match-tag match-tag-manual">Manual BAC Selection</span></div>
                        <div><strong>Registered Categories:</strong> {s.categories && s.categories.length ? s.categories.join(', ') : 'None on file'}</div>
                        {s.email && <div><strong>Email:</strong> {s.email}</div>}
                      </div>
                      <div className="supplier-match-foot">
                        {status ? (
                          <span className="status-badge status-open">{rfqStatusLabelText(status)}</span>
                        ) : (
                          <button
                            type="button"
                            className="btn-sm btn-primary"
                            disabled={s.status !== 'Approved'}
                            title={s.status !== 'Approved' ? 'Only approved suppliers can be selected.' : undefined}
                            onClick={() => onSelectSupplier(s, group, 'manual_bac')}
                          >
                            Select Supplier
                          </button>
                        )}
                      </div>
                    </article>
                  )
                })}
              </div>
            )
          )}

          <div className="match-section-divider" />
          <div className="match-section-heading">
            <h3>Manual / Unregistered Supplier</h3>
            <p className="helper-text">
              Issue an RFQ to a supplier not registered in eProcure. The name is an internal reference for this PR and category group only and never appears on the RFQ PDF.
            </p>
          </div>
          <button type="button" className="btn-primary" onClick={() => onManualRfq(group)}>+ Add Unregistered Supplier</button>
        </div>
      )}
    </div>
  )
}

const SupplierMatchingView = ({ prId, apiBase, onBack }) => {
  const [data, setData] = React.useState(null)
  const [prDetails, setPrDetails] = React.useState(null)
  const [selectedSupplier, setSelectedSupplier] = React.useState(null)
  const [issuedMap, setIssuedMap] = React.useState({})
  const [expanded, setExpanded] = React.useState({})
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')
  const [reloadToken, setReloadToken] = React.useState(0)

  // ── Manual / unregistered supplier RFQ (scoped to one category group) ──
  const [manualRfqGroup, setManualRfqGroup] = React.useState(null)
  const [manualRfqName, setManualRfqName] = React.useState('')
  const [manualRfqMode, setManualRfqMode] = React.useState('')
  const [manualRfqQuotationBasis, setManualRfqQuotationBasis] = React.useState('LOT')
  const [manualRfqModes, setManualRfqModes] = React.useState([])
  const [manualRfqBusy, setManualRfqBusy] = React.useState(false)
  const [manualRfqError, setManualRfqError] = React.useState('')
  const [manualRfqResult, setManualRfqResult] = React.useState(null)

  React.useEffect(() => {
    apiFetch(`${apiBase}/api/procurement-modes/`)
      .then((r) => (r.ok ? r.json() : { modes: [] }))
      .then((d) => setManualRfqModes(Array.isArray(d.modes) ? d.modes : []))
      .catch(() => {})
  }, [apiBase])

  const issuedFor = React.useCallback((categoryName, supplierId) => {
    return issuedMap[`${categoryName}::${supplierId}`]
  }, [issuedMap])

  const createManualRfq = async () => {
    const name = manualRfqName.trim()
    if (!name) { setManualRfqError('Enter the supplier / company name.'); return }
    if (!manualRfqMode.trim()) { setManualRfqError('Enter a mode of procurement.'); return }
    setManualRfqBusy(true)
    setManualRfqError('')
    try {
      const res = await apiFetch(`${apiBase}/api/pr/${prId}/manual-rfq/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          manual_supplier_name: name,
          category: manualRfqGroup?.category || '',
          mode_of_procurement: manualRfqMode.trim(),
          quotation_basis: manualRfqQuotationBasis,
        }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(body.message || body.error || `Failed to create RFQ (HTTP ${res.status})`)
      setManualRfqResult({ ...body, _category: manualRfqGroup?.category || '' })
      setManualRfqGroup(null)
      setManualRfqName('')
      setManualRfqMode('')
      setReloadToken((t) => t + 1)
    } catch (err) {
      setManualRfqError(err.message || 'Failed to create the manual RFQ.')
    } finally {
      setManualRfqBusy(false)
    }
  }

  React.useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([
      apiFetch(`${apiBase}/api/pr/${prId}/supplier-match/`).then((r) => { if (!r.ok) throw new Error('Failed to load supplier matches'); return r.json() }),
      apiFetch(`${apiBase}/api/pr/${prId}/details/`).then((r) => { if (!r.ok) throw new Error('Failed to load Purchase Request details'); return r.json() }),
      apiFetch(`${apiBase}/api/pr/${prId}/rfq/`)
        .then((r) => r.ok ? r.json() : { rfqs: [] })
        .catch(() => ({ rfqs: [] })),
    ])
      .then(([matchData, details, rfqData]) => {
        setData(matchData)
        setPrDetails(details)
        setExpanded((prev) => {
          const next = { ...prev }
          for (const g of matchData.groups || []) {
            if (!(g.category in next)) next[g.category] = (matchData.groups.length === 1)
          }
          return next
        })
        // Key issued RFQs by category + supplier so a supplier picked for one
        // group is never shown as picked for another (task 12).
        const issued = {}
        for (const rfq of rfqData.rfqs || []) {
          if (!rfq.status || rfq.status === 'draft') continue
          const cat = rfq.category || ''
          if (rfq.supplier?.id) issued[`${cat}::${rfq.supplier.id}`] = rfq.status
        }
        setIssuedMap(issued)
        setLoading(false)
      })
      .catch((err) => { setError(err.message || 'Failed to load'); setLoading(false) })
  }, [prId, apiBase, reloadToken])

  const onSelectSupplier = (supplier, group, selectionType) => {
    setSelectedSupplier({
      ...supplier,
      matched_category: group.category,
      category_id: group.category_id,
      groupItems: group.items,
      selection_type: selectionType,
    })
  }

  if (selectedSupplier && prDetails) {
    return (
      <RFQPreparation
        prId={prId}
        apiBase={apiBase}
        supplier={selectedSupplier}
        prDetails={prDetails}
        onBack={() => { setSelectedSupplier(null); setReloadToken((token) => token + 1) }}
      />
    )
  }

  const groups = data?.groups || []
  const uncategorized = data?.uncategorized_items || []

  return (
    <div className="supplier-section">
      <WorkflowStepper current="matching" />

      <div className="supplier-header" style={{ marginTop: 20 }}>
        <h1>Supplier Matching</h1>
        <p>
          Purchase Request <strong>#{data?.pr?.pr_no || prDetails?.pr_no || prId}</strong>
          {data && <> &mdash; {data.item_count} Item{data.item_count !== 1 ? 's' : ''}, {data.category_count} Procurement {data.category_count === 1 ? 'Category' : 'Categories'}</>}
        </p>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 14 }}>{error}</div>}

      {manualRfqResult && (
        <div className="alert alert-success" style={{ marginBottom: 14 }}>
          <strong>Manual RFQ issued</strong> for {manualRfqResult._category || 'this PR'} &mdash;{' '}
          {manualRfqResult.manual_supplier_name}, Quotation No. <strong>{manualRfqResult.quotation_no}</strong>.{' '}
          <a href={`${apiBase}/api/manual-rfqs/${manualRfqResult.id}/pdf/`} target="_blank" rel="noreferrer">Download RFQ PDF</a>.
        </div>
      )}

      {loading ? (
        <div className="skeleton-stack">
          {[1, 2, 3].map((n) => <div key={n} className="skeleton-line" style={{ height: 90 }} />)}
        </div>
      ) : (
        <>
          {uncategorized.length > 0 && (
            <div className="alert alert-warning" style={{ marginBottom: 16 }}>
              <strong>Category Required.</strong> {uncategorized.length} item{uncategorized.length !== 1 ? 's have' : ' has'} no procurement category and cannot proceed to category-based supplier matching:
              <ul style={{ margin: '6px 0 8px', paddingLeft: 20 }}>
                {uncategorized.map((it) => <li key={it.id}>{it.item_description || 'N/A'}</li>)}
              </ul>
              <button type="button" className="btn-sm btn-secondary" onClick={onBack}>Assign categories</button>
            </div>
          )}

          {groups.length === 0 && uncategorized.length === 0 && (
            <div className="alert alert-info">This Purchase Request has no line items.</div>
          )}

          <div className="procurement-group-list">
            {groups.map((group) => (
              <ProcurementGroup
                key={group.category}
                group={group}
                apiBase={apiBase}
                expanded={Boolean(expanded[group.category])}
                onToggle={() => setExpanded((prev) => ({ ...prev, [group.category]: !prev[group.category] }))}
                issuedFor={issuedFor}
                onSelectSupplier={onSelectSupplier}
                onManualRfq={(g) => { setManualRfqGroup(g); setManualRfqError(''); setManualRfqResult(null) }}
              />
            ))}
          </div>
        </>
      )}

      {manualRfqGroup && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="manual-rfq-title" onClick={() => setManualRfqGroup(null)}>
          <div className="modal-content" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3 id="manual-rfq-title">Add Unregistered Supplier — {manualRfqGroup.category}</h3>
              <button type="button" className="modal-close" onClick={() => setManualRfqGroup(null)}>×</button>
            </div>
            <div className="modal-body">
              {manualRfqError && <div className="alert alert-error" style={{ marginBottom: 10 }}>{manualRfqError}</div>}
              <label className="form-field">
                <span>Company / Supplier Name *</span>
                <input type="text" value={manualRfqName} onChange={(e) => setManualRfqName(e.target.value)} placeholder="e.g. Juan's Aircon Services" autoFocus />
              </label>
              <label className="form-field">
                <span>Mode of Procurement *</span>
                <input type="text" list="manual-rfq-modes" value={manualRfqMode} onChange={(e) => setManualRfqMode(e.target.value)} placeholder="Select a suggestion or type a mode" />
                <datalist id="manual-rfq-modes">
                  {manualRfqModes.map((mode) => <option key={mode} value={mode} />)}
                </datalist>
              </label>
              <label className="form-field">
                <span>Quotation Basis *</span>
                <select value={manualRfqQuotationBasis} onChange={(e) => setManualRfqQuotationBasis(e.target.value)}>
                  <option value="LOT">Lot</option>
                  <option value="LINE">Line</option>
                </select>
              </label>
              <p className="helper-text" style={{ margin: '4px 0 0' }}>
                The RFQ will contain only the {manualRfqGroup.item_count} item{manualRfqGroup.item_count !== 1 ? 's' : ''} in <strong>{manualRfqGroup.category}</strong>.
              </p>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setManualRfqGroup(null)} disabled={manualRfqBusy}>Cancel</button>
              <button type="button" className="btn btn-primary" onClick={createManualRfq} disabled={manualRfqBusy}>
                {manualRfqBusy ? 'Creating…' : 'Create RFQ'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="form-actions" style={{ marginTop: 20 }}>
        <button type="button" className="btn-secondary" onClick={onBack}>← Back to Categories</button>
      </div>
    </div>
  )
}


const UnmatchedPurchaseRequests = ({ apiBase, onContinue }) => {
  const [requests, setRequests] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    let cancelled = false
    setLoading(true)
    apiFetch(`${apiBase}/api/pr/unmatched/`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load unmatched Purchase Requests')
        return response.json()
      })
      .then((data) => {
        if (!cancelled) {
          setRequests(Array.isArray(data) ? data : [])
          setLoading(false)
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError.message || 'Failed to load unmatched Purchase Requests')
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [apiBase])

  return (
    <div className="supplier-section">
      <WorkflowStepper current="matching" />
      <div className="supplier-header" style={{ marginTop: 20 }}>
        <h1>Supplier Matching</h1>
        <p>Continue matching an existing Purchase Request with registered suppliers.</p>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="admin-checklist unmatched-pr-section">
        <h3>Unmatched Purchase Requests</h3>
        {loading ? (
          <div className="skeleton-stack"><div className="skeleton-line" style={{ height: 48 }} /></div>
        ) : requests.length === 0 ? (
          <div className="supplier-match-empty">No unmatched Purchase Requests available.</div>
        ) : (
          <div className="table-shell">
            <table className="enterprise-table unmatched-pr-table">
              <thead>
                <tr><th>PR No.</th><th>Category</th><th>Status</th><th>Action</th></tr>
              </thead>
              <tbody>
                {requests.map((request) => (
                  <tr key={request.id}>
                    <td><strong>{request.pr_no || `PR-${request.id}`}</strong></td>
                    <td>{request.category || 'Category not assigned'}</td>
                    <td><span className="status-badge status-review">Unmatched</span></td>
                    <td><button type="button" className="btn-sm btn-primary" onClick={() => onContinue(request.id)}>Continue Matching</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

const RFQ_MGMT_FILTERS = [
  ['all', 'All'],
  ['awaiting', 'Awaiting Response'],
  ['received', 'Responses Received'],
]

const RFQ_MGMT_SORTS = [
  ['newest_pr', 'Newest PR'],
  ['oldest_pr', 'Oldest PR'],
  ['recent_activity', 'Recent activity'],
  ['response_status', 'Response status'],
]

const PR_RFQ_STATUS_META = {
  awaiting_responses: { label: 'Awaiting Responses', className: 'status-review' },
  responses_in_progress: { label: 'Responses In Progress', className: 'status-review' },
  all_responses_received: { label: 'All Responses Received', className: 'status-open' },
  no_rfqs: { label: 'No RFQs', className: 'status-review' },
}

const rfqResponseIndicator = (rfq) => {
  if (rfq.has_response) return { icon: '✓', label: 'Response Received', className: 'received' }
  if (rfq.status === 'draft') return { icon: '•', label: 'Draft', className: 'draft' }
  return { icon: '⏳', label: 'Awaiting Response', className: 'awaiting' }
}

const rfqMgmtFormatDate = (value) => (value ? new Date(value).toLocaleDateString() : '—')
const rfqMgmtFormatDateTime = (value) => (value ? new Date(value).toLocaleString() : '—')

const RFQDocumentViewerModal = ({ viewer, onClose }) => {
  if (!viewer) return null
  return (
    <div className="supplier-preview-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="supplier-preview-modal" onClick={(event) => event.stopPropagation()}>
        <div className="supplier-preview-header">
          <div className="supplier-panel-title">{viewer.title}</div>
          <button className="icon-action-btn" type="button" onClick={onClose} aria-label="Close document viewer"><X size={14} /></button>
        </div>
        <iframe className="supplier-preview-frame" src={viewer.url} title={viewer.title} />
      </div>
    </div>
  )
}

const PRResponsesView = ({ group, onBack, onOpenRfq, onView }) => {
  const pr = group.purchase_request
  const summary = group.rfq_summary
  const responded = group.rfqs.filter((rfq) => rfq.has_response)
  const awaiting = group.rfqs.filter((rfq) => !rfq.has_response)

  return (
    <>
      <button type="button" className="btn-sm btn-secondary" onClick={onBack} style={{ marginBottom: 16 }}>
        <ChevronLeft size={14} /> Back to RFQ Management
      </button>
      <div className="supplier-header">
        <h1>Supplier Responses · {pr.pr_no}</h1>
        <p>{pr.category || 'Category not assigned'}</p>
      </div>

      <div className="rfq-mgmt-progress" style={{ marginBottom: 16 }}>
        <span className="rfq-resp-indicator received">✓ {summary.responses_received} Response{summary.responses_received !== 1 ? 's' : ''} Received</span>
        <span className="rfq-resp-indicator awaiting">⏳ {summary.awaiting_response} Awaiting Response</span>
      </div>

      {responded.length === 0 ? (
        <div className="empty-state"><Clock size={48} /><h3>No responses yet</h3><p>No supplier responses have been received yet.</p></div>
      ) : (
        <div className="rfq-mgmt-response-list">
          {responded.map((rfq) => (
            <div key={rfq.id} className="rfq-mgmt-response-card">
              <div>
                <h4>{rfq.supplier.company_name}</h4>
                <p className="supplier-subtext">{rfq.rfq_no}</p>
                <span className="rfq-resp-indicator received">✓ Response Received</span>
                {rfq.submitted_at && <p className="supplier-subtext">Submitted: {new Date(rfq.submitted_at).toLocaleString()}</p>}
              </div>
              <div className="rfq-mgmt-row-actions">
                <button type="button" className="btn-sm btn-primary" onClick={() => onView(rfq.submitted_pdf_url, `Supplier Submitted RFQ · ${rfq.rfq_no}`)}>View Response</button>
                <a className="btn-sm btn-secondary" href={rfq.submitted_pdf_url} download target="_blank" rel="noreferrer"><Download size={13} /> Download</a>
                <button type="button" className="btn-sm btn-secondary" onClick={() => onOpenRfq(rfq)}>RFQ Details</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {awaiting.length > 0 && (
        <>
          <h3 style={{ marginTop: 24 }}>Awaiting Response</h3>
          <div className="rfq-mgmt-response-list">
            {awaiting.map((rfq) => (
              <div key={rfq.id} className="rfq-mgmt-response-card">
                <div>
                  <h4>{rfq.supplier.company_name}</h4>
                  <p className="supplier-subtext">{rfq.rfq_no}</p>
                  <span className="rfq-resp-indicator awaiting">⏳ Awaiting Response</span>
                </div>
                <div className="rfq-mgmt-row-actions">
                  {rfq.generated_pdf_url && (
                    <button type="button" className="btn-sm btn-secondary" onClick={() => onView(rfq.generated_pdf_url, `Generated RFQ · ${rfq.rfq_no}`)}>View RFQ</button>
                  )}
                  <button type="button" className="btn-sm btn-secondary" onClick={() => onOpenRfq(rfq)}>RFQ Details</button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {awaiting.length === 0 && responded.length > 0 && (
        <p className="helper-text" style={{ marginTop: 16 }}>All RFQs for this PR have received responses.</p>
      )}

      {/* future: Compare Quotations — this PR-level view already holds every
          supplier's submitted RFQ (rfq.submitted_pdf_url) grouped under the PR,
          so a quotation-extraction / comparison step can be added here without
          reshaping the data. */}
    </>
  )
}

const RFQDetailView = ({ group, rfq, onBack, onView }) => {
  const pr = group.purchase_request
  const supplier = rfq.supplier

  return (
    <>
      <button type="button" className="btn-sm btn-secondary" onClick={onBack} style={{ marginBottom: 16 }}>
        <ChevronLeft size={14} /> Back to RFQ Management
      </button>
      <div className="supplier-header">
        <h1>{rfq.rfq_no}</h1>
        <p><span className={`status-badge ${rfq.has_response ? 'status-open' : 'status-review'}`}>{rfq.status_label || rfq.status}</span></p>
      </div>

      <div className="card rfq-review-card">
        <h2>RFQ Information</h2>
        <div className="detail-grid">
          <div><strong>RFQ No.: </strong><span>{rfq.rfq_no}</span></div>
          <div><strong>Status: </strong><span>{rfq.status_label || rfq.status}</span></div>
          <div><strong>Created: </strong><span>{rfqMgmtFormatDate(rfq.created_at)}</span></div>
          <div><strong>Sent: </strong><span>{rfqMgmtFormatDate(rfq.sent_at)}</span></div>
          <div><strong>Response Received: </strong><span>{rfq.submitted_at ? rfqMgmtFormatDateTime(rfq.submitted_at) : 'Not yet submitted'}</span></div>
        </div>
      </div>

      <div className="card rfq-review-card">
        <h2>Purchase Request</h2>
        <div className="detail-grid">
          <div><strong>PR No.: </strong><span>{pr.pr_no}</span></div>
          <div><strong>PR Date: </strong><span>{pr.date || '—'}</span></div>
          <div><strong>Category: </strong><span>{pr.category || '—'}</span></div>
          <div style={{ gridColumn: '1 / -1' }}><strong>Purpose: </strong><span>{pr.purpose || '—'}</span></div>
        </div>
      </div>

      <div className="card rfq-review-card">
        <h2>Supplier</h2>
        <div className="detail-grid">
          <div><strong>Company Name: </strong><span>{supplier.company_name}</span></div>
          <div><strong>Contact Person: </strong><span>{supplier.contact_person || '—'}</span></div>
          <div><strong>Email: </strong><span>{supplier.email || '—'}</span></div>
          <div><strong>Phone: </strong><span>{supplier.contact_phone || '—'}</span></div>
          <div style={{ gridColumn: '1 / -1' }}><strong>Address: </strong><span>{supplier.business_address || '—'}</span></div>
          <div><strong>TIN: </strong><span>{supplier.tin || '—'}</span></div>
        </div>
      </div>

      <div className="card rfq-review-card">
        <h2>Documents</h2>
        <div className="rfq-mgmt-doc-row">
          <div>
            <strong>Generated RFQ</strong>
            <p className="supplier-subtext">System-generated RFQ issued to the supplier.</p>
          </div>
          <div className="rfq-mgmt-row-actions">
            {rfq.generated_pdf_url ? (
              <>
                <button type="button" className="btn-sm btn-secondary" onClick={() => onView(rfq.generated_pdf_url, `Generated RFQ · ${rfq.rfq_no}`)}>View</button>
                <a className="btn-sm btn-secondary" href={rfq.generated_pdf_url} download target="_blank" rel="noreferrer"><Download size={13} /> Download</a>
              </>
            ) : <span className="supplier-subtext">Not generated</span>}
          </div>
        </div>
        <div className="rfq-mgmt-doc-row">
          <div>
            <strong>Supplier Submitted RFQ</strong>
            <p className="supplier-subtext">Completed, signed RFQ uploaded by the supplier. Stored separately from the generated RFQ.</p>
            {rfq.submitted_pdf_url && (
              <p className="supplier-subtext">
                {rfq.submitted_filename ? `${rfq.submitted_filename} · ` : ''}
                Received {rfq.submitted_at ? new Date(rfq.submitted_at).toLocaleString() : '—'}
              </p>
            )}
          </div>
          <div className="rfq-mgmt-row-actions">
            {rfq.submitted_pdf_url ? (
              <>
                <button type="button" className="btn-sm btn-primary" onClick={() => onView(rfq.submitted_pdf_url, `Supplier Submitted RFQ · ${rfq.rfq_no}`)}>View</button>
                <a className="btn-sm btn-secondary" href={rfq.submitted_pdf_url} download target="_blank" rel="noreferrer"><Download size={13} /> Download</a>
              </>
            ) : <span className="supplier-subtext">Not yet submitted</span>}
          </div>
        </div>
      </div>
    </>
  )
}

const ManualRFQsView = ({ apiBaseUrl }) => {
  const [rfqs, setRfqs] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')
  const [search, setSearch] = React.useState('')
  const [activeSearch, setActiveSearch] = React.useState('')
  const [openRfq, setOpenRfq] = React.useState(null)
  const [uploadingId, setUploadingId] = React.useState(null)
  const base = apiBaseUrl.replace(/\/$/, '')

  const load = React.useCallback(async (term = '') => {
    setLoading(true)
    setError('')
    try {
      const url = `${base}/api/manual-rfqs/${term ? `?search=${encodeURIComponent(term)}` : ''}`
      const res = await apiFetch(url, { cache: 'no-store' })
      if (!res.ok) throw new Error('Unable to load Manual RFQs.')
      const data = await res.json()
      setRfqs(Array.isArray(data.rfqs) ? data.rfqs : [])
      setActiveSearch(term)
    } catch (err) {
      setError(err.message || 'Unable to load Manual RFQs.')
    } finally {
      setLoading(false)
    }
  }, [base])

  React.useEffect(() => { load('') }, [load])

  const uploadCompleted = async (rfq, file) => {
    if (!file) return
    setUploadingId(rfq.id)
    try {
      const body = new FormData()
      body.append('file', file)
      const res = await apiFetch(`${base}/api/manual-rfqs/${rfq.id}/completed/`, { method: 'POST', body })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.message || data.error || 'Upload failed.')
      await load(activeSearch)
      setOpenRfq(data)
    } catch (err) {
      window.alert(err.message || 'Upload failed.')
    } finally {
      setUploadingId(null)
    }
  }

  return (
    <div className="supplier-section">
      <div className="supplier-header">
        <h1>Manual RFQs</h1>
        <p>RFQs issued to unregistered suppliers. The supplier name is an internal reference and is not printed on the RFQ PDF. Re-download uses the same quotation number.</p>
      </div>

      <form
        className="other-supplier-search"
        style={{ marginBottom: 16 }}
        onSubmit={(e) => { e.preventDefault(); load(search.trim()) }}
      >
        <label className="form-field" style={{ flex: 1, margin: 0 }}>
          <span>Search by supplier name, PR number or quotation number</span>
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="🔍 e.g. Juan's, 2026-09-001, 2026-021" />
        </label>
        <button type="submit" className="btn-primary" disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
        {activeSearch && (
          <button type="button" className="btn-secondary" onClick={() => { setSearch(''); load('') }} disabled={loading}>Show all</button>
        )}
      </form>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <div className="skeleton-stack">{[1, 2, 3].map((n) => <div key={n} className="skeleton-line" style={{ height: 90 }} />)}</div>
      ) : rfqs.length === 0 ? (
        <div className="supplier-match-empty">
          {activeSearch ? 'No manual RFQs match your search.' : 'No manual RFQs yet. Create one from Supplier Matching → Manual / Unregistered Supplier.'}
        </div>
      ) : (
        <div className="supplier-match-grid">
          {rfqs.map((rfq) => (
            <article key={rfq.id} className="supplier-match-card supplier-match-card-manual">
              <div className="supplier-match-head">
                <h4>{rfq.manual_supplier_name || rfq.supplier_name}</h4>
                <span className={`status-badge ${rfq.has_response ? 'status-open' : 'status-review'}`}>{rfq.status_label}</span>
              </div>
              <div className="supplier-match-body">
                <div><span className="match-tag match-tag-manual">Manual / Unregistered</span></div>
                <div><strong>PR:</strong> {rfq.purchase_request?.pr_no || `PR-${rfq.purchase_request?.id}`}</div>
                <div><strong>Quotation No.:</strong> {rfq.quotation_no}</div>
                <div><strong>RFQ No.:</strong> {rfq.rfq_no}</div>
                <div><strong>Delivery:</strong> Manual</div>
                {rfq.created_by && <div><strong>Issued by:</strong> {rfq.created_by}</div>}
                <div><strong>Issued:</strong> {rfq.sent_at ? new Date(rfq.sent_at).toLocaleString() : new Date(rfq.created_at).toLocaleString()}</div>
              </div>
              <div className="supplier-match-foot">
                <button type="button" className="btn-sm btn-secondary" onClick={() => setOpenRfq(rfq)}>Open</button>
                <a className="btn-sm btn-primary" href={`${base}/api/manual-rfqs/${rfq.id}/pdf/`} target="_blank" rel="noreferrer">Download RFQ</a>
              </div>
            </article>
          ))}
        </div>
      )}

      {openRfq && (
        <div className="modal-overlay" role="dialog" aria-modal="true" onClick={() => setOpenRfq(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Manual RFQ — {openRfq.manual_supplier_name || openRfq.supplier_name}</h3>
              <button type="button" className="modal-close" onClick={() => setOpenRfq(null)}>×</button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div><strong>Supplier: </strong><span>{openRfq.manual_supplier_name || openRfq.supplier_name}</span></div>
                <div><strong>Type: </strong><span>Manual / Unregistered</span></div>
                <div><strong>PR No.: </strong><span>{openRfq.purchase_request?.pr_no || `PR-${openRfq.purchase_request?.id}`}</span></div>
                <div><strong>Quotation No.: </strong><span>{openRfq.quotation_no}</span></div>
                <div><strong>RFQ No.: </strong><span>{openRfq.rfq_no}</span></div>
                <div><strong>Delivery: </strong><span>Manual</span></div>
                <div><strong>Mode of Procurement: </strong><span>{openRfq.mode_of_procurement || 'N/A'}</span></div>
                <div><strong>Status: </strong><span>{openRfq.status_label}</span></div>
                {openRfq.created_by && <div><strong>Issued by: </strong><span>{openRfq.created_by}</span></div>}
              </div>

              <div className="form-actions" style={{ marginTop: 14 }}>
                <a className="btn-secondary" href={`${base}/api/manual-rfqs/${openRfq.id}/pdf/`} target="_blank" rel="noreferrer">Download Generated RFQ</a>
                {openRfq.submitted_pdf_url && (
                  <a className="btn-secondary" href={openRfq.submitted_pdf_url} target="_blank" rel="noreferrer">View Completed RFQ</a>
                )}
              </div>

              <div style={{ marginTop: 14 }}>
                <label className="form-field">
                  <span>{openRfq.has_response ? 'Replace completed RFQ (PDF only)' : 'Upload completed RFQ returned by the supplier (PDF only)'}</span>
                  <input
                    type="file"
                    accept={acceptAttr(UPLOAD_KINDS.COMPLETED_RFQ)}
                    disabled={uploadingId === openRfq.id}
                    onChange={(e) => {
                      const picked = e.target.files?.[0] || null
                      if (picked) {
                        const check = validateFile(picked, UPLOAD_KINDS.COMPLETED_RFQ)
                        if (!check.ok) { window.alert(check.error); e.target.value = ''; return }
                        uploadCompleted(openRfq, picked)
                      }
                    }}
                  />
                </label>
              </div>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setOpenRfq(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const AdminRFQManagement = ({ apiBaseUrl }) => {
  const [groups, setGroups] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')
  const [filter, setFilter] = React.useState('all')
  const [sort, setSort] = React.useState('newest_pr')
  const [searchInput, setSearchInput] = React.useState('')
  const [search, setSearch] = React.useState('')
  const [expandedPrId, setExpandedPrId] = React.useState(null)
  const [viewer, setViewer] = React.useState(null)
  const [detail, setDetail] = React.useState(null) // { mode: 'pr' | 'rfq', group, rfq? }

  const base = apiBaseUrl.replace(/\/$/, '')

  React.useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput.trim()), 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  const load = React.useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ group_by: 'pr', sort })
      if (filter !== 'all') params.set('status', filter)
      if (search) params.set('search', search)
      const response = await apiFetch(`${base}/api/rfqs/responses/?${params.toString()}`)
      if (!response.ok) throw new Error('Unable to load RFQ Management data.')
      const data = await response.json()
      setGroups(Array.isArray(data.purchase_requests) ? data.purchase_requests : [])
    } catch (loadError) {
      setError(loadError.message || 'Unable to load RFQ Management data.')
    } finally {
      setLoading(false)
    }
  }, [base, filter, sort, search])

  React.useEffect(() => { load() }, [load])

  const openDocument = (url, title) => setViewer({ url: bustCache(url), title })
  const closeViewer = () => setViewer(null)

  let content
  if (detail?.mode === 'rfq') {
    content = (
      <RFQDetailView
        group={detail.group}
        rfq={detail.rfq}
        onBack={() => setDetail(null)}
        onView={openDocument}
      />
    )
  } else if (detail?.mode === 'pr') {
    content = (
      <PRResponsesView
        group={detail.group}
        onBack={() => setDetail(null)}
        onOpenRfq={(rfq) => setDetail({ mode: 'rfq', group: detail.group, rfq })}
        onView={openDocument}
      />
    )
  } else {
    content = (
      <>
        <div className="supplier-header">
          <h1>RFQ Management</h1>
          <p>RFQs grouped by Purchase Request. See how many suppliers were sent an RFQ for each PR and which have responded.</p>
        </div>

        <div className="rfq-mgmt-toolbar">
          <div className="rfq-mgmt-filter-group">
            {RFQ_MGMT_FILTERS.map(([value, label]) => (
              <button key={value} type="button" className={`btn-sm ${filter === value ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFilter(value)}>{label}</button>
            ))}
          </div>
          <div className="rfq-mgmt-toolbar-right">
            <div className="rfq-mgmt-search">
              <Search size={14} />
              <input type="search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search PR no, RFQ no, or supplier" />
            </div>
            <select className="rfq-mgmt-sort" value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort Purchase Requests">
              {RFQ_MGMT_SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <button type="button" className="btn-sm btn-secondary" onClick={load} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
            </button>
          </div>
        </div>

        {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

        {loading ? <SkeletonRows count={4} /> : groups.length === 0 ? (
          <div className="empty-state">
            <FileText size={48} />
            <h3>No RFQs found</h3>
            <p>{search || filter !== 'all' ? 'No Purchase Requests match the current filters.' : 'No RFQs have been generated yet.'}</p>
          </div>
        ) : (
          <div className="rfq-mgmt-groups">
            {groups.map((group) => {
              const pr = group.purchase_request
              const summary = group.rfq_summary
              const statusMeta = PR_RFQ_STATUS_META[summary.status] || PR_RFQ_STATUS_META.no_rfqs
              const expanded = expandedPrId === pr.id
              return (
                <div key={pr.id} className={`rfq-mgmt-group ${expanded ? 'expanded' : ''}`}>
                  <button type="button" className="rfq-mgmt-group-header" onClick={() => setExpandedPrId(expanded ? null : pr.id)} aria-expanded={expanded}>
                    <span className="rfq-mgmt-chevron">{expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span>
                    <span className="rfq-mgmt-group-title">
                      <strong>{pr.pr_no}</strong>
                      <span className="rfq-mgmt-group-category">{pr.category || 'Category not assigned'}</span>
                    </span>
                    <span className="rfq-mgmt-group-counts">
                      {summary.category_count ? `${summary.category_count} ${summary.category_count === 1 ? 'Category' : 'Categories'} • ` : ''}
                      {summary.sent} RFQ{summary.sent !== 1 ? 's' : ''} • {summary.responses_received} Response{summary.responses_received !== 1 ? 's' : ''}
                    </span>
                    <span className={`status-badge ${statusMeta.className}`}>{statusMeta.label}</span>
                  </button>

                  {expanded && (
                    <div className="rfq-mgmt-group-body">
                      <div className="rfq-mgmt-progress">
                        <span>{summary.sent} Sent</span>
                        <span className="rfq-resp-indicator received">✓ {summary.responses_received} Received</span>
                        <span className="rfq-resp-indicator awaiting">⏳ {summary.awaiting_response} Awaiting</span>
                        {summary.responses_received > 0 && (
                          <button type="button" className="btn-sm btn-primary" onClick={() => setDetail({ mode: 'pr', group })}>View All Responses</button>
                        )}
                      </div>
                      {(group.categories && group.categories.length
                        ? group.categories
                        : [{ category: pr.category || 'Uncategorized', rfqs: group.rfqs, rfq_count: group.rfqs.length, response_count: group.rfqs.filter((r) => r.has_response).length, item_count: 0 }]
                      ).map((catGroup) => (
                        <div key={catGroup.category} className="rfq-mgmt-category">
                          <div className="rfq-mgmt-category-head">
                            <strong>{catGroup.category}</strong>
                            <span className="rfq-mgmt-group-counts">
                              {catGroup.item_count ? `${catGroup.item_count} Item${catGroup.item_count !== 1 ? 's' : ''} · ` : ''}
                              {catGroup.rfq_count} RFQ{catGroup.rfq_count !== 1 ? 's' : ''} · {catGroup.response_count} Response{catGroup.response_count !== 1 ? 's' : ''}
                            </span>
                          </div>
                          <div className="table-shell">
                            <table className="enterprise-table">
                              <thead>
                                <tr><th>Supplier</th><th>Quotation No.</th><th>Sent</th><th>Received</th><th>Status</th><th>Actions</th></tr>
                              </thead>
                              <tbody>
                                {catGroup.rfqs.map((rfq) => {
                                  const indicator = rfqResponseIndicator(rfq)
                                  return (
                                    <tr key={rfq.id}>
                                      <td>{rfq.supplier?.company_name || rfq.manual_supplier_name || rfq.supplier_name}</td>
                                      <td><strong>{rfq.rfq_no || '—'}</strong></td>
                                      <td>{rfq.sent_at ? new Date(rfq.sent_at).toLocaleDateString() : '—'}</td>
                                      <td>{rfq.submitted_at ? new Date(rfq.submitted_at).toLocaleDateString() : '—'}</td>
                                      <td><span className={`rfq-resp-indicator ${indicator.className}`}>{indicator.icon} {indicator.label}</span></td>
                                      <td>
                                        <div className="rfq-mgmt-row-actions">
                                          <button type="button" className="btn-sm btn-secondary" onClick={() => setDetail({ mode: 'rfq', group, rfq })}>View RFQ</button>
                                          {rfq.generated_pdf_url && (
                                            <button type="button" className="btn-sm btn-secondary" onClick={() => openDocument(rfq.generated_pdf_url, `Generated RFQ · ${rfq.rfq_no}`)}>View Generated</button>
                                          )}
                                          {rfq.submitted_pdf_url ? (
                                            <>
                                              <button type="button" className="btn-sm btn-primary" onClick={() => openDocument(rfq.submitted_pdf_url, `Supplier Submitted RFQ · ${rfq.rfq_no}`)}>View Response</button>
                                              <a className="btn-sm btn-secondary" href={rfq.submitted_pdf_url} download target="_blank" rel="noreferrer"><Download size={13} /> Download</a>
                                            </>
                                          ) : (
                                            <span className="supplier-subtext">No response yet</span>
                                          )}
                                        </div>
                                      </td>
                                    </tr>
                                  )
                                })}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </>
    )
  }

  return (
    <div className="supplier-section">
      {content}
      <RFQDocumentViewerModal viewer={viewer} onClose={closeViewer} />
    </div>
  )
}

const Admin = () => {
  const navigate = useNavigate()
  const [currentTab, setCurrentTab] = React.useState('dashboard')
  const [workflowPrId, setWorkflowPrId] = React.useState(null)
  const [prRecords, setPrRecords] = React.useState([])
  const [prLoading, setPrLoading] = React.useState(false)
  const [prError, setPrError] = React.useState('')
  const [prSavingId, setPrSavingId] = React.useState(null)
  const [prDeletingId, setPrDeletingId] = React.useState(null)
  const [prDeleteConfirmId, setPrDeleteConfirmId] = React.useState(null)
  const [editingPr, setEditingPr] = React.useState(null)
  const [editPrForm, setEditPrForm] = React.useState(null)
  const [editPrLoading, setEditPrLoading] = React.useState(false)
  const [editPrSaving, setEditPrSaving] = React.useState(false)
  const [editPrNumberMode, setEditPrNumberMode] = React.useState('automatic')
  const [editPrCustomNumber, setEditPrCustomNumber] = React.useState('')
  const [editPrSourceUrl, setEditPrSourceUrl] = React.useState('')
  const [editPrSourceFilename, setEditPrSourceFilename] = React.useState('')
  const [editPrSignatureValidation, setEditPrSignatureValidation] = React.useState(null)
  const [editPrSignatureChecking, setEditPrSignatureChecking] = React.useState(false)
  const [dashboardStats, setDashboardStats] = React.useState(null)
  const [dashboardLoading, setDashboardLoading] = React.useState(false)
  const [dashboardError, setDashboardError] = React.useState('')
  const [exportingSuppliers, setExportingSuppliers] = React.useState(false)
  const [exportingPrs, setExportingPrs] = React.useState(false)
  const [exportError, setExportError] = React.useState('')
  const [prNumberFormat, setPrNumberFormat] = React.useState(null)
  const [prNumberFormatDraft, setPrNumberFormatDraft] = React.useState(null)
  const [prNumberFormatLoading, setPrNumberFormatLoading] = React.useState(false)
  const [prNumberFormatSaving, setPrNumberFormatSaving] = React.useState(false)
  const [prNumberFormatError, setPrNumberFormatError] = React.useState('')
  const [prNumberFormatMessage, setPrNumberFormatMessage] = React.useState('')
  const [prNotificationSettingsDraft, setPrNotificationSettingsDraft] = React.useState(null)
  const [prNotificationSettingsLoading, setPrNotificationSettingsLoading] = React.useState(false)
  const [prNotificationSettingsSaving, setPrNotificationSettingsSaving] = React.useState(false)
  const [prNotificationSettingsError, setPrNotificationSettingsError] = React.useState('')
  const [prNotificationSettingsMessage, setPrNotificationSettingsMessage] = React.useState('')
  const [editingStatusById, setEditingStatusById] = React.useState({})
  const [pendingStatusById, setPendingStatusById] = React.useState({})
  const [supplierRegistrations, setSupplierRegistrations] = React.useState([])
  const [supplierLoading, setSupplierLoading] = React.useState(false)
  const [supplierError, setSupplierError] = React.useState('')
  const [supplierActioningId, setSupplierActioningId] = React.useState(null)
  const [supplierSearch, setSupplierSearch] = React.useState('')
  const [supplierDetails, setSupplierDetails] = React.useState({})
  const [selectedSupplierId, setSelectedSupplierId] = React.useState(null)
  const [selectedSupplierDetails, setSelectedSupplierDetails] = React.useState(null)
  const [reviewRemarks, setReviewRemarks] = React.useState('')
  const [reviewAction, setReviewAction] = React.useState(null)
  const [supplierDeleteConfirm, setSupplierDeleteConfirm] = React.useState(null)
  const [supplierDeletingId, setSupplierDeletingId] = React.useState(null)
  const [documentStatusDrafts, setDocumentStatusDrafts] = React.useState({})
  const [previewDoc, setPreviewDoc] = React.useState(null)
  const [previewVisible, setPreviewVisible] = React.useState(false)
  const [navCollapsed, setNavCollapsed] = React.useState(false)
  const [buyerAccountForm, setBuyerAccountForm] = React.useState({ username: '', fullName: '', email: '', unitOffice: '', password: '', confirmPassword: '' })
  const [buyerAccountSaving, setBuyerAccountSaving] = React.useState(false)
  const [buyerAccountMessage, setBuyerAccountMessage] = React.useState('')
  const [buyerAccountError, setBuyerAccountError] = React.useState('')
  const [showBuyerPassword, setShowBuyerPassword] = React.useState(false)
  const [buyerAccounts, setBuyerAccounts] = React.useState([])
  const [buyerAccountsLoading, setBuyerAccountsLoading] = React.useState(false)
  const [buyerAccountSearch, setBuyerAccountSearch] = React.useState('')
  const [buyerAccountActionId, setBuyerAccountActionId] = React.useState(null)
  const [buyerDeleteConfirm, setBuyerDeleteConfirm] = React.useState(null)
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  const prStatusOptions = [
    { value: 'uploaded', label: 'Uploaded' },
    { value: 'in_review', label: 'In Review' },
    { value: 'matched', label: 'Matched' },
    { value: 'approved', label: 'Completed' },
    { value: 'rejected', label: 'Rejected' },
  ]

  const handleLogout = () => {
    apiFetch(`${apiBaseUrl}/api/logout/`, { method: 'POST' }).catch(() => {})
    authStore.clear()
    navigate('/login')
  }

  const loadBuyerAccounts = React.useCallback(async () => {
    setBuyerAccountsLoading(true)
    try {
      const response = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/buyer-accounts/`)
      if (!response.ok) throw new Error('Unable to load End User accounts.')
      setBuyerAccounts(await response.json())
    } catch (error) {
      setBuyerAccountError(error?.message || 'Unable to load End User accounts.')
    } finally {
      setBuyerAccountsLoading(false)
    }
  }, [apiBaseUrl])

  const handleBuyerAccountSubmit = async (event) => {
    event.preventDefault()
    setBuyerAccountMessage('')
    setBuyerAccountError('')
    if (buyerAccountForm.password !== buyerAccountForm.confirmPassword) {
      setBuyerAccountError('Passwords do not match.')
      return
    }
    if (buyerAccountForm.password.length < 8) {
      setBuyerAccountError('Password must be at least 8 characters long.')
      return
    }

    setBuyerAccountSaving(true)
    try {
      const response = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: buyerAccountForm.username.trim(),
          fullName: buyerAccountForm.fullName.trim(),
          email: buyerAccountForm.email.trim(),
          unitOffice: buyerAccountForm.unitOffice.trim(),
          password: buyerAccountForm.password,
          role: 'buyer',
        }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.message || 'Unable to create End User account.')
      setBuyerAccountMessage('End User account created successfully.')
      setBuyerAccountForm({ username: '', fullName: '', email: '', unitOffice: '', password: '', confirmPassword: '' })
      loadBuyerAccounts()
    } catch (error) {
      setBuyerAccountError(error?.message || 'Unable to create End User account.')
    } finally {
      setBuyerAccountSaving(false)
    }
  }

  const filteredBuyerAccounts = React.useMemo(() => {
    const query = buyerAccountSearch.trim().toLowerCase()
    if (!query) return buyerAccounts
    return buyerAccounts.filter((account) => [account.full_name, account.username, account.email, account.unit_office]
      .filter(Boolean).join(' ').toLowerCase().includes(query))
  }, [buyerAccountSearch, buyerAccounts])

  const handleDeleteBuyerAccount = async (account) => {
    setBuyerAccountActionId(account.id)
    setBuyerAccountError('')
    try {
      const response = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/buyer-accounts/${account.id}/`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        const result = await response.json().catch(() => ({}))
        throw new Error(result.message || 'Unable to delete End User account.')
      }
      setBuyerAccounts((current) => current.filter((item) => item.id !== account.id))
      setBuyerDeleteConfirm(null)
    } catch (error) {
      setBuyerAccountError(error?.message || 'Unable to delete End User account.')
    } finally {
      setBuyerAccountActionId(null)
    }
  }

  const handleContinueMatching = React.useCallback((prId) => {
    setWorkflowPrId(prId)
    setCurrentTab('supplier-matching')
  }, [])

  const loadSupplierRegistrations = React.useCallback(async () => {
    setSupplierLoading(true)
    setSupplierError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/`)
      if (!res.ok) {
        throw new Error('Failed to load supplier registrations')
      }
      const data = await res.json()
      setSupplierRegistrations(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error(error)
      setSupplierError(error?.message || 'Failed to load supplier registrations')
    } finally {
      setSupplierLoading(false)
    }
  }, [apiBaseUrl])

  const loadDashboardStats = React.useCallback(async () => {
    setDashboardLoading(true)
    setDashboardError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/admin/dashboard-summary/`)
      if (!res.ok) throw new Error('Failed to load dashboard data')
      setDashboardStats(await res.json())
    } catch (error) {
      console.error(error)
      setDashboardError(error?.message || 'Failed to load dashboard data')
    } finally {
      setDashboardLoading(false)
    }
  }, [apiBaseUrl])

  const handleExportSuppliers = React.useCallback(async () => {
    setExportError('')
    setExportingSuppliers(true)
    await downloadCsvExport(apiBaseUrl, '/api/admin/export/suppliers/', 'suppliers.csv', setExportError)
    setExportingSuppliers(false)
  }, [apiBaseUrl])

  const handleExportPurchaseRequests = React.useCallback(async () => {
    setExportError('')
    setExportingPrs(true)
    await downloadCsvExport(apiBaseUrl, '/api/admin/export/purchase-requests/', 'purchase_requests.csv', setExportError)
    setExportingPrs(false)
  }, [apiBaseUrl])

  const loadPrNumberFormat = React.useCallback(async () => {
    setPrNumberFormatLoading(true)
    setPrNumberFormatError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/admin/pr-number-format/`)
      if (!res.ok) throw new Error('Failed to load PR numbering settings')
      const data = await res.json()
      setPrNumberFormat(data)
      setPrNumberFormatDraft(data)
    } catch (error) {
      console.error(error)
      setPrNumberFormatError(error?.message || 'Failed to load PR numbering settings')
    } finally {
      setPrNumberFormatLoading(false)
    }
  }, [apiBaseUrl])

  const handleSavePrNumberFormat = async (event) => {
    event.preventDefault()
    setPrNumberFormatSaving(true)
    setPrNumberFormatError('')
    setPrNumberFormatMessage('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/admin/pr-number-format/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prefix: prNumberFormatDraft.prefix,
          date_granularity: prNumberFormatDraft.date_granularity,
          separator: prNumberFormatDraft.separator,
          sequence_digits: Number(prNumberFormatDraft.sequence_digits),
          reset_period: prNumberFormatDraft.reset_period,
        }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) throw new Error(data?.message || 'Failed to save PR numbering settings')
      setPrNumberFormat(data)
      setPrNumberFormatDraft(data)
      setPrNumberFormatMessage('PR numbering settings saved.')
    } catch (error) {
      console.error(error)
      setPrNumberFormatError(error?.message || 'Failed to save PR numbering settings')
    } finally {
      setPrNumberFormatSaving(false)
    }
  }

  // Mirrors backend _compose_pr_number() so the panel can preview the effect
  // of an unsaved edit without a round trip; the authoritative value always
  // comes back from the GET/PATCH response once loaded/saved.
  const previewPrNumber = (draft, sequence) => {
    if (!draft) return ''
    const now = new Date()
    const parts = []
    if (draft.prefix) parts.push(draft.prefix)
    if (draft.date_granularity === 'year' || draft.date_granularity === 'year_month') {
      parts.push(String(now.getFullYear()))
    }
    if (draft.date_granularity === 'year_month') {
      parts.push(String(now.getMonth() + 1).padStart(2, '0'))
    }
    const digits = Number(draft.sequence_digits) || 1
    parts.push(String(sequence).padStart(digits, '0'))
    return parts.join(draft.separator ?? '')
  }

  const loadPrNotificationSettings = React.useCallback(async () => {
    setPrNotificationSettingsLoading(true)
    setPrNotificationSettingsError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/admin/pr-notification-settings/`)
      if (!res.ok) throw new Error('Failed to load PR notification settings')
      const data = await res.json()
      setPrNotificationSettingsDraft(data)
    } catch (error) {
      console.error(error)
      setPrNotificationSettingsError(error?.message || 'Failed to load PR notification settings')
    } finally {
      setPrNotificationSettingsLoading(false)
    }
  }, [apiBaseUrl])

  const handleSavePrNotificationSettings = async (event) => {
    event.preventDefault()
    setPrNotificationSettingsSaving(true)
    setPrNotificationSettingsError('')
    setPrNotificationSettingsMessage('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/admin/pr-notification-settings/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prNotificationSettingsDraft),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) throw new Error(data?.message || 'Failed to save PR notification settings')
      setPrNotificationSettingsDraft(data)
      setPrNotificationSettingsMessage('PR notification settings saved.')
    } catch (error) {
      console.error(error)
      setPrNotificationSettingsError(error?.message || 'Failed to save PR notification settings')
    } finally {
      setPrNotificationSettingsSaving(false)
    }
  }

  const loadSupplierDetails = React.useCallback(async (supplierId) => {
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/${supplierId}/profile/`)
      if (!res.ok) {
        throw new Error('Failed to load supplier details')
      }
      const payload = await res.json()
      setSupplierDetails((prev) => ({ ...prev, [supplierId]: payload }))
      return payload
    } catch (error) {
      console.error(error)
      throw error
    }
  }, [apiBaseUrl])

  const handleSelectSupplier = async (supplier) => {
    setSelectedSupplierId(supplier.id)
    setReviewRemarks(supplier.review_remarks || '')
    setDocumentStatusDrafts({})

    if (supplierDetails[supplier.id]) {
      setSelectedSupplierDetails(supplierDetails[supplier.id])
      return
    }

    try {
      const payload = await loadSupplierDetails(supplier.id)
      setSelectedSupplierDetails(payload)
    } catch (error) {
      setSupplierError(error?.message || 'Failed to load supplier details')
    }
  }

  const handleDocumentStatusChange = (documentId, nextStatus) => {
    setDocumentStatusDrafts((prev) => ({ ...prev, [documentId]: nextStatus }))
    setSelectedSupplierDetails((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        documents: (prev.documents || []).map((document) => (
          document.id === documentId ? { ...document, verification_status: nextStatus } : document
        )),
      }
    })
  }

  const mergeDocumentStatuses = (documents, updates) => {
    if (!Array.isArray(documents) || !Array.isArray(updates)) return documents
    const statusById = new Map(updates.map((doc) => [doc.id, doc.verification_status]))
    return documents.map((document) => (
      statusById.has(document.id) ? { ...document, verification_status: statusById.get(document.id) } : document
    ))
  }

  const executeReviewDecision = async (supplierId, nextStatus, actionName) => {
    const trimmedRemarks = reviewRemarks.trim()
    if ((nextStatus === 'Rejected' || nextStatus === 'For Compliance') && !trimmedRemarks) {
      setSupplierError('Remarks are required before rejecting or requesting additional documents.')
      return
    }

    setSupplierActioningId(supplierId)
    setSupplierError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/${supplierId}/status/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: nextStatus,
          remarks: trimmedRemarks,
          document_statuses: documentStatusDrafts,
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        throw new Error(payload?.message || `Failed to ${actionName} supplier`)
      }

      const payload = await res.json().catch(() => null)
      const nextReviewRemarks = payload?.remarks || trimmedRemarks
      setSupplierRegistrations((prev) => prev.map((item) => (item.id === supplierId ? { ...item, status: nextStatus, review_remarks: nextReviewRemarks } : item)))
      setSelectedSupplierDetails((prev) => prev && prev.id === supplierId ? { ...prev, status: nextStatus, review_remarks: nextReviewRemarks, documents: mergeDocumentStatuses(prev.documents, payload?.documents) } : prev)
      setSupplierDetails((prev) => (prev[supplierId] ? { ...prev, [supplierId]: { ...prev[supplierId], status: nextStatus, review_remarks: nextReviewRemarks, documents: mergeDocumentStatuses(prev[supplierId].documents, payload?.documents) } } : prev))
      setReviewRemarks(nextReviewRemarks)
      setDocumentStatusDrafts({})
      setSupplierError('')
      setReviewAction(null)
    } catch (error) {
      console.error(error)
      setSupplierError(error?.message || `Failed to ${actionName} supplier`)
    } finally {
      setSupplierActioningId(null)
    }
  }

  const handleApplyDocumentChanges = async (supplierId) => {
    const currentStatus = selectedSupplierDetails?.status
    if (!supplierId || !currentStatus) return

    setSupplierActioningId(supplierId)
    setSupplierError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/${supplierId}/status/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: currentStatus,
          remarks: reviewRemarks.trim(),
          document_statuses: documentStatusDrafts,
        }),
      })
      const payload = await res.json().catch(() => null)
      if (!res.ok) {
        throw new Error(payload?.message || 'Failed to apply document changes')
      }
      setSelectedSupplierDetails((prev) => prev && prev.id === supplierId ? { ...prev, documents: mergeDocumentStatuses(prev.documents, payload?.documents) } : prev)
      setSupplierDetails((prev) => (prev[supplierId] ? { ...prev, [supplierId]: { ...prev[supplierId], documents: mergeDocumentStatuses(prev[supplierId].documents, payload?.documents) } } : prev))
      setDocumentStatusDrafts({})
      setSupplierError('')
    } catch (error) {
      console.error(error)
      setSupplierError(error?.message || 'Failed to apply document changes')
    } finally {
      setSupplierActioningId(null)
    }
  }

  const openReviewAction = (supplierId, nextStatus, actionName) => {
    const supplier = supplierRegistrations.find((item) => item.id === supplierId) || selectedSupplierDetails
    setReviewRemarks(supplier?.review_remarks || reviewRemarks)
    setReviewAction({ supplierId, nextStatus, actionName, companyName: supplier?.company_name || 'this supplier' })
    setSupplierError('')
  }

  const handleApprove = (supplierId) => openReviewAction(supplierId, 'Approved', 'approve')
  const handleReject = (supplierId) => openReviewAction(supplierId, 'Rejected', 'reject')
  const handleRequestCompliance = (supplierId) => openReviewAction(supplierId, 'For Compliance', 'request additional documents')

  const requestSupplierDelete = (supplierId) => {
    const supplier = supplierRegistrations.find((item) => item.id === supplierId)
      || (selectedSupplierDetails?.id === supplierId ? selectedSupplierDetails : null)
    setSupplierError('')
    setSupplierDeleteConfirm({ id: supplierId, companyName: supplier?.company_name || 'this supplier' })
  }

  const handleDeleteSupplier = async (supplierId) => {
    setSupplierDeletingId(supplierId)
    setSupplierError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/${supplierId}/`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        throw new Error(payload?.message || 'Failed to delete supplier account')
      }
      setSupplierRegistrations((prev) => prev.filter((item) => item.id !== supplierId))
      setSupplierDetails((prev) => {
        if (!prev[supplierId]) return prev
        const next = { ...prev }
        delete next[supplierId]
        return next
      })
      if (selectedSupplierId === supplierId) {
        setSelectedSupplierId(null)
        setSelectedSupplierDetails(null)
      }
      setSupplierDeleteConfirm(null)
    } catch (error) {
      console.error(error)
      setSupplierError(error?.message || 'Failed to delete supplier account')
    } finally {
      setSupplierDeletingId(null)
    }
  }

  const filteredSuppliers = React.useMemo(() => {
    const query = supplierSearch.trim().toLowerCase()
    if (!query) return supplierRegistrations

    return supplierRegistrations.filter((supplier) => {
      const haystack = [
        supplier.company_name,
        supplier.contact_person,
        supplier.email,
        supplier.business_type,
        supplier.categories?.join(' '),
      ].filter(Boolean).join(' ').toLowerCase()
      return haystack.includes(query)
    })
  }, [supplierRegistrations, supplierSearch])

  const selectedSupplier = React.useMemo(() => (
    supplierRegistrations.find((supplier) => supplier.id === selectedSupplierId) || null
  ), [selectedSupplierId, supplierRegistrations])

  const PR_STATUS_LABELS = { uploaded: 'Uploaded', in_review: 'In Review', matched: 'Matched', approved: 'Approved', rejected: 'Rejected' }

  const dashboardBreakdowns = React.useMemo(() => {
    const toBarItems = (rows, labels = {}) => (rows || []).map((row) => ({
      label: labels[row.status] || row.status,
      count: row.count,
    }))

    const categoryBreakdown = dashboardStats?.supplier_category_breakdown || []
    const categoryItems = categoryBreakdown
      .filter((row) => row.count > 0)
      .slice(0, 10)
      .map((row) => ({ label: row.category, count: row.count }))

    const rfq = dashboardStats?.rfq_stats || { total_sent: 0, with_response: 0, avg_quotations_per_rfq: 0 }
    const responseRate = rfq.total_sent > 0 ? Math.round((rfq.with_response / rfq.total_sent) * 100) : 0

    return {
      supplierStatus: toBarItems(dashboardStats?.supplier_status_breakdown),
      documentStatus: toBarItems(dashboardStats?.document_status_breakdown),
      prStatus: toBarItems(dashboardStats?.pr_status_breakdown, PR_STATUS_LABELS),
      categoryItems,
      categoryTotal: categoryBreakdown.length,
      categoryWithSuppliers: categoryBreakdown.filter((row) => row.count > 0).length,
      monthlyVolume: dashboardStats?.pr_monthly_volume || [],
      rfq,
      responseRate,
    }
  }, [dashboardStats])

  const getSupplierStatusMeta = (status) => {
    if (status === 'Approved') return { label: 'Approved', className: 'status-open' }
    if (status === 'Rejected') return { label: 'Rejected', className: 'status-merged' }
    if (status === 'For Compliance') return { label: 'For Compliance', className: 'status-review' }
    return { label: status || 'Pending Review', className: 'status-review' }
  }

  const getDocumentStatusMeta = (status) => {
    if (status === 'Verified') return { label: 'Verified', className: 'status-open' }
    if (status === 'Rejected') return { label: 'Rejected', className: 'status-merged' }
    return { label: status || 'Pending', className: 'status-review' }
  }

  const getDocumentLabel = (docType) => {
    const displayNames = {
      mayor_permit: "Mayor's Permit",
      business_permit: 'Business Permit',
      philgeps_registration: 'PhilGEPS Registration',
      bir_registration: 'BIR Registration',
      tax_clearance: 'Tax Clearance',
      dti_registration: 'DTI / SEC / CDA Registration',
      sec_registration: 'DTI / SEC / CDA Registration',
      cda_registration: 'DTI / SEC / CDA Registration',
      other_eligibility_requirement: 'Other Eligibility Requirements',
      other_eligibility: 'Other Eligibility Requirements',
    }
    return displayNames[docType] || docType || 'Document'
  }

  const openPreview = (document) => {
    setPreviewDoc(document)
    setPreviewVisible(true)
  }

  const closePreview = () => {
    setPreviewVisible(false)
    setPreviewDoc(null)
  }

  const closeSupplierReview = () => {
    setSelectedSupplierId(null)
    setSelectedSupplierDetails(null)
    setReviewRemarks('')
  }

  const loadPrRecords = React.useCallback(async () => {
    setPrLoading(true)
    setPrError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/list/`)
      if (!res.ok) {
        throw new Error('Failed to load PR records')
      }
      const data = await res.json()
      setPrRecords(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error(error)
      setPrError(error?.message || 'Failed to load PR records')
    } finally {
      setPrLoading(false)
    }
  }, [apiBaseUrl])

  React.useEffect(() => {
    if (currentTab === 'dashboard') {
      loadDashboardStats()
      loadPrRecords()
      loadSupplierRegistrations()
      const refreshTimer = window.setInterval(loadDashboardStats, 30000)
      return () => window.clearInterval(refreshTimer)
    }
    if (currentTab === 'suppliers') {
      loadSupplierRegistrations()
    }
    if (currentTab === 'buyer-accounts') {
      loadBuyerAccounts()
    }
    if (currentTab === 'pr-monitoring') {
      loadPrRecords()
    }
    if (currentTab === 'pr-numbering-settings') {
      loadPrNumberFormat()
    }
    if (currentTab === 'pr-notification-settings') {
      loadPrNotificationSettings()
    }
  }, [currentTab, loadBuyerAccounts, loadDashboardStats, loadPrNotificationSettings, loadPrNumberFormat, loadPrRecords, loadSupplierRegistrations])

  const handlePrStatusChange = async (prId, nextStatus) => {
    setPrSavingId(prId)
    setPrError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/${prId}/status/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        throw new Error(payload?.message || 'Failed to update PR status')
      }
      setPrRecords((prev) => prev.map((row) => (row.id === prId ? { ...row, status: nextStatus } : row)))
    } catch (error) {
      console.error(error)
      setPrError(error?.message || 'Failed to update PR status')
    } finally {
      setPrSavingId(null)
    }
  }

  const handlePrDelete = async (prId) => {
    setPrDeletingId(prId)
    setPrError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/${prId}/`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        throw new Error(payload?.message || 'Failed to delete PR')
      }
      setPrRecords((prev) => prev.filter((row) => row.id !== prId))
      setPrDeleteConfirmId(null)
    } catch (error) {
      console.error(error)
      setPrError(error?.message || 'Failed to delete PR')
    } finally {
      setPrDeletingId(null)
    }
  }

  const requestPrDelete = (prId) => setPrDeleteConfirmId(prId)

  const prStatusMeta = {
    uploaded: { label: 'Uploaded', className: 'status-review' },
    in_review: { label: 'In Review', className: 'status-review' },
    matched: { label: 'Matched', className: 'status-open' },
    approved: { label: 'Completed', className: 'status-open' },
    rejected: { label: 'Rejected', className: 'status-merged' },
  }

  const pesoFormatter = React.useMemo(() => new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: 'PHP',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }), [])

  const getPrStatusMeta = (status) => prStatusMeta[status] || { label: status || 'Unknown', className: 'status-review' }

  const formatPeso = (value) => {
    const numeric = Number(value)
    if (!Number.isFinite(numeric)) return pesoFormatter.format(0)
    return pesoFormatter.format(numeric)
  }

  const handleStartStatusEdit = (pr) => {
    setEditingStatusById((prev) => ({ ...prev, [pr.id]: true }))
    setPendingStatusById((prev) => ({ ...prev, [pr.id]: pr.status || 'uploaded' }))
  }

  const handleCancelStatusEdit = (prId) => {
    setEditingStatusById((prev) => ({ ...prev, [prId]: false }))
    setPendingStatusById((prev) => ({ ...prev, [prId]: undefined }))
  }

  const handleSaveStatusEdit = async (pr) => {
    const nextStatus = pendingStatusById[pr.id] || pr.status || 'uploaded'
    await handlePrStatusChange(pr.id, nextStatus)
    setEditingStatusById((prev) => ({ ...prev, [pr.id]: false }))
  }

  const handleViewPr = (pr) => {
    window.alert(`PR #${pr.pr_no || pr.id}\nEntity: ${pr.entity_name || 'N/A'}\nStatus: ${getPrStatusMeta(pr.status).label}`)
  }

  const handleEditPr = async (pr) => {
    setEditingPr(pr)
    setEditPrForm(null)
    setEditPrLoading(true)
    setPrError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/${pr.id}/details/`)
      if (!res.ok) throw new Error('Failed to load Purchase Request details')
      const details = await res.json()
      setEditPrForm({
        pr_no: details.pr_no || '',
        entity_name: details.entity_name || '',
        category: details.category || '',
        fund_cluster: details.fund_cluster || '',
        office_section: details.office_section || '',
        responsibility_center_code: details.responsibility_center_code || '',
        date: details.date || '',
        purpose: details.purpose || '',
        requested_by: details.requested_by || '',
        funds_available_by: details.funds_available_by || '',
        approved_by: details.approved_by || '',
        twg_verified_by: details.twg_verified_by || '',
        items: (details.items || []).map((item) => ({
          stock_property_no: item.stock_property_no || '',
          unit: item.unit || '',
          item_description: item.item_description || '',
          quantity: item.quantity ?? 0,
          unit_cost: item.unit_cost ?? 0,
          category: item.category || '',
        })),
      })
      setEditPrNumberMode(details.pr_no ? 'existing' : 'automatic')
      setEditPrCustomNumber(details.pr_no || '')
      setEditPrSourceUrl(details.source_file_url || '')
      setEditPrSourceFilename(details.source_filename || '')
      setEditPrSignatureValidation(null)
      if (details.source_filename) {
        checkEditPrSignatures(details.source_filename, {
          requested_by_name: details.requested_by || '',
          funds_available_name: details.funds_available_by || '',
          approved_by_name: details.approved_by || '',
          twg_name: details.twg_verified_by || '',
        })
      }
    } catch (error) {
      setPrError(error?.message || 'Failed to load Purchase Request details')
      setEditingPr(null)
    } finally {
      setEditPrLoading(false)
    }
  }

  const checkEditPrSignatures = async (filename, signatoryFields) => {
    if (!filename) return
    setEditPrSignatureChecking(true)
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/recheck-signatures/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, fields: signatoryFields }),
      })
      const data = await res.json().catch(() => null)
      if (res.ok && data?.signature_validation) {
        setEditPrSignatureValidation(data.signature_validation)
      }
    } catch {
      // Non-fatal - the BAC reviewer can still edit the PR without the
      // signature panel; they can retry via the "Recheck Signatures" button.
    } finally {
      setEditPrSignatureChecking(false)
    }
  }

  const handleRecheckEditPrSignatures = () => {
    if (!editPrForm || !editPrSourceFilename) return
    checkEditPrSignatures(editPrSourceFilename, {
      requested_by_name: editPrForm.requested_by || '',
      funds_available_name: editPrForm.funds_available_by || '',
      approved_by_name: editPrForm.approved_by || '',
      twg_name: editPrForm.twg_verified_by || '',
    })
  }

  const closeEditPr = () => {
    if (editPrSaving) return
    setEditingPr(null)
    setEditPrForm(null)
    setEditPrSignatureValidation(null)
    setEditPrSourceFilename('')
  }

  const handleSavePrEdit = async (finalizeReview = false) => {
    if (!editPrForm || !editingPr) return
    setEditPrSaving(true)
    setPrError('')
    try {
      const res = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/${editingPr.id}/edit/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...editPrForm,
          finalize_review: finalizeReview,
          pr_number_mode: editPrNumberMode === 'custom' ? 'custom' : 'automatic',
          custom_pr_number: editPrCustomNumber,
        }),
      })
      const payload = await res.json().catch(() => null)
      if (!res.ok) throw new Error(payload?.message || 'Failed to update Purchase Request')
      setPrRecords((prev) => prev.map((row) => row.id === editingPr.id ? {
        ...row,
        entity_name: editPrForm.entity_name,
        office_section: editPrForm.office_section,
        purpose: editPrForm.purpose,
        grand_total: payload.grand_total,
        items_count: editPrForm.items.length,
        pr_no: payload.pr_no || row.pr_no,
        status: payload.status || row.status,
      } : row))
      closeEditPr()
      return true
    } catch (error) {
      setPrError(error?.message || 'Failed to update Purchase Request')
      return false
    } finally {
      setEditPrSaving(false)
    }
  }

  const matchedSupplierCards = prRecords.flatMap((pr) => {
    const suppliers = Array.isArray(pr.matched_suppliers) ? pr.matched_suppliers : []
    return suppliers.map((supplier, index) => ({
      id: `${pr.id}-${supplier.id || supplier.company_name || index}`,
      prId: pr.id,
      prNo: pr.pr_no || `PR-${pr.id}`,
      supplier,
    }))
  })

  const unnumberedPrRecords = prRecords.filter((pr) => !pr.pr_no?.trim())
  const numberedPrRecords = prRecords.filter((pr) => pr.pr_no?.trim())

  const handleSelectMatchedSupplier = (card) => {
    const name = card?.supplier?.company_name || card?.supplier?.name || 'supplier'
    window.alert(`Selected ${name} for ${card.prNo}.`)
  }

  return (
    <div className={`admin-layout ${navCollapsed ? 'collapsed-nav' : ''}`}>
      {/* Admin Navbar */}
      <Sidebar
        portalLabel="Admin Portal"
        activeId={currentTab}
        onSelect={setCurrentTab}
        navCollapsed={navCollapsed}
        onToggleNav={() => setNavCollapsed((v) => !v)}
        userPrimary="Administrator"
        userSecondary="admin@ctu.edu.ph"
        onLogout={handleLogout}
        groups={[
          { section: 'MAIN', items: [
            { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
          ] },
          { section: 'PROCUREMENT', items: [
            { id: 'pr-monitoring', label: 'PR Review & Monitoring', icon: ClipboardList },
            { id: 'rfq-responses', label: 'RFQ Management', icon: FileText },
            { id: 'manual-rfqs', label: 'Manual RFQs', icon: FileText },
          ] },
          { section: 'ACCOUNTS', items: [
            { id: 'suppliers', label: 'Supplier Management', icon: Users },
            { id: 'buyer-accounts', label: 'End User Accounts', icon: Users },
          ] },
          { section: 'SETTINGS', items: [
            { id: 'pr-numbering-settings', label: 'PR Numbering', icon: Settings },
            { id: 'pr-notification-settings', label: 'PR Notifications', icon: Bell },
          ] },
        ]}
      />

      {/* Admin Content */}
      <div className="admin-content">
        {currentTab === 'dashboard' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>Admin Dashboard</h1>
              <p>System overview and management controls</p>
            </div>
            {dashboardError && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{dashboardError}</div>}

            {dashboardLoading && !dashboardStats ? (
              <div className="admin-dashboard-grid">
                <section className="admin-dashboard-panel"><SkeletonRows count={5} /></section>
                <section className="admin-dashboard-panel"><SkeletonRows count={5} /></section>
              </div>
            ) : (
              <>
                <div className="admin-dashboard-grid">
                  <section className="admin-dashboard-panel">
                    <div className="admin-dashboard-panel-header">
                      <div>
                        <span className="section-kicker">Supplier network</span>
                        <h2>Suppliers by Status</h2>
                      </div>
                      <span className="admin-panel-total">{dashboardStats?.total_suppliers ?? 0} total</span>
                    </div>
                    <BreakdownBarList items={dashboardBreakdowns.supplierStatus} emptyLabel="No suppliers registered yet." />
                  </section>

                  <section className="admin-dashboard-panel">
                    <div className="admin-dashboard-panel-header">
                      <div>
                        <span className="section-kicker">Eligibility documents</span>
                        <h2>Document Verification Status</h2>
                      </div>
                      <span className="admin-panel-total">{dashboardBreakdowns.documentStatus.reduce((sum, item) => sum + item.count, 0)} documents</span>
                    </div>
                    <BreakdownBarList items={dashboardBreakdowns.documentStatus} emptyLabel="No documents uploaded yet." />
                  </section>

                  <section className="admin-dashboard-panel">
                    <div className="admin-dashboard-panel-header">
                      <div>
                        <span className="section-kicker">Procurement categories</span>
                        <h2>Verified Suppliers by Category</h2>
                      </div>
                      <span className="admin-panel-total">{dashboardBreakdowns.categoryWithSuppliers}/{dashboardBreakdowns.categoryTotal} covered</span>
                    </div>
                    <BreakdownBarList items={dashboardBreakdowns.categoryItems} emptyLabel="No approved suppliers are assigned to a category yet." />
                  </section>

                  <section className="admin-dashboard-panel">
                    <div className="admin-dashboard-panel-header">
                      <div>
                        <span className="section-kicker">Procurement</span>
                        <h2>Purchase Request Pipeline</h2>
                      </div>
                      <span className="admin-panel-total">{dashboardStats?.total_purchase_requests ?? 0} total</span>
                    </div>
                    <BreakdownBarList items={dashboardBreakdowns.prStatus} emptyLabel="No purchase requests yet." />
                  </section>

                  <section className="admin-dashboard-panel admin-dashboard-panel-wide">
                    <div className="admin-dashboard-panel-header">
                      <div>
                        <span className="section-kicker">Trend</span>
                        <h2>Purchase Request Volume (Last 6 Months)</h2>
                      </div>
                    </div>
                    <MonthlyTrendChart data={dashboardBreakdowns.monthlyVolume} />
                  </section>

                  <section className="admin-dashboard-panel admin-dashboard-panel-wide">
                    <div className="admin-dashboard-panel-header">
                      <div>
                        <span className="section-kicker">Supplier engagement</span>
                        <h2>RFQ Response Summary</h2>
                      </div>
                    </div>
                    <div className="admin-cards">
                      <div className="admin-card">
                        <div className="admin-card-eyebrow">Issued</div>
                        <div className="admin-card-value">{dashboardBreakdowns.rfq.total_sent}</div>
                        <div className="admin-card-label">RFQs Sent</div>
                      </div>
                      <div className="admin-card">
                        <div className="admin-card-eyebrow">Engaged</div>
                        <div className="admin-card-value">{dashboardBreakdowns.rfq.with_response}</div>
                        <div className="admin-card-label">RFQs with a Quotation</div>
                      </div>
                      <div className="admin-card">
                        <div className="admin-card-eyebrow">Rate</div>
                        <div className="admin-card-value">{dashboardBreakdowns.responseRate}%</div>
                        <div className="admin-card-label">RFQ Response Rate</div>
                      </div>
                      <div className="admin-card">
                        <div className="admin-card-eyebrow">Competitiveness</div>
                        <div className="admin-card-value">{dashboardBreakdowns.rfq.avg_quotations_per_rfq}</div>
                        <div className="admin-card-label">Avg. Quotations per RFQ</div>
                      </div>
                    </div>
                  </section>
                </div>
              </>
            )}

            <div className="admin-dashboard-grid">
              <section className="admin-dashboard-panel">
                <div className="admin-dashboard-panel-header">
                  <div>
                    <span className="section-kicker">Latest records</span>
                    <h2>Recent Purchase Requests</h2>
                  </div>
                  <button type="button" className="btn-sm btn-secondary" onClick={() => setCurrentTab('pr-monitoring')}>View all</button>
                </div>
                {prLoading && prRecords.length === 0 ? <SkeletonRows count={4} /> : prRecords.length === 0 ? (
                  <div className="dashboard-empty-state"><ClipboardList size={20} /><span>No Purchase Requests found.</span></div>
                ) : (
                  <div className="dashboard-activity-list">
                    {prRecords.slice(0, 5).map((pr) => {
                      const statusMeta = getPrStatusMeta(pr.status)
                      return (
                        <button key={pr.id} type="button" className="dashboard-activity-row" onClick={() => handleViewPr(pr)}>
                          <span className="dashboard-activity-id">{pr.pr_no || `PR-${pr.id}`}</span>
                          <span className="dashboard-activity-main"><strong>{pr.entity_name || 'Unnamed entity'}</strong><small>{pr.office_section || 'Office not specified'}</small></span>
                          <span className={`status-badge ${statusMeta.className}`}>{statusMeta.label}</span>
                          <span className="dashboard-activity-value">{formatPeso(pr.grand_total)}</span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </section>
              <section className="admin-dashboard-panel">
                <div className="admin-dashboard-panel-header">
                  <div>
                    <span className="section-kicker">Supplier network</span>
                    <h2>Recent Registrations</h2>
                  </div>
                  <button type="button" className="btn-sm btn-secondary" onClick={() => setCurrentTab('suppliers')}>Manage</button>
                </div>
                {supplierLoading && supplierRegistrations.length === 0 ? <SkeletonRows count={4} /> : supplierRegistrations.length === 0 ? (
                  <div className="dashboard-empty-state"><Users size={20} /><span>No supplier registrations found.</span></div>
                ) : (
                  <div className="dashboard-activity-list">
                    {supplierRegistrations.slice(0, 5).map((supplier) => {
                      const statusMeta = getSupplierStatusMeta(supplier.status)
                      return (
                        <button key={supplier.id} type="button" className="dashboard-activity-row" onClick={() => { setCurrentTab('suppliers'); handleSelectSupplier(supplier) }}>
                          <span className="dashboard-activity-id">#{supplier.id}</span>
                          <span className="dashboard-activity-main"><strong>{supplier.company_name || 'Unnamed supplier'}</strong><small>{supplier.email || 'Email not specified'}</small></span>
                          <span className={`status-badge ${statusMeta.className}`}>{statusMeta.label}</span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        {currentTab === 'suppliers' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>Supplier Verification & Approval</h1>
              <p>Review supplier registrations, verify uploaded documents, and approve or reject submissions.</p>
            </div>

            {supplierError && (
              <div className="alert alert-error" style={{ marginBottom: '16px' }}>
                <strong>Review action blocked.</strong> {supplierError}
              </div>
            )}
            {exportError && (
              <div className="alert alert-error" style={{ marginBottom: '16px' }}>{exportError}</div>
            )}

            <div className="supplier-verification-shell">
              <div className="supplier-verification-list-card">
                <div className="supplier-verification-toolbar">
                  <div>
                    <h3>Supplier Registrations</h3>
                    <p>Search and select a supplier to review.</p>
                  </div>
                  <div className="supplier-search-box">
                    <Search size={16} />
                    <input
                      type="text"
                      value={supplierSearch}
                      onChange={(event) => setSupplierSearch(event.target.value)}
                      placeholder="Search suppliers"
                      aria-label="Search suppliers"
                    />
                  </div>
                  <button
                    type="button"
                    className="btn-sm btn-secondary"
                    onClick={handleExportSuppliers}
                    disabled={exportingSuppliers}
                  >
                    <Download size={14} />
                    {exportingSuppliers ? 'Exporting...' : 'Export Report'}
                  </button>
                </div>

                <div className="supplier-verification-table">
                  {supplierLoading && supplierRegistrations.length === 0 && (
                    <div className="supplier-verification-row-card">Loading supplier registrations...</div>
                  )}

                  {!supplierLoading && filteredSuppliers.length === 0 && (
                    <div className="supplier-verification-row-card">No supplier registrations found.</div>
                  )}

                  {filteredSuppliers.map((item) => {
                    const statusMeta = getSupplierStatusMeta(item.status)
                    const isSelected = selectedSupplierId === item.id
                    return (
                      <div
                        key={item.id}
                        className={`supplier-verification-row-card ${isSelected ? 'selected' : ''}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => handleSelectSupplier(item)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            handleSelectSupplier(item)
                          }
                        }}
                      >
                        <div className="supplier-card-main">
                          <div className="supplier-card-heading">
                            <div className="supplier-card-title-group">
                              <span className="supplier-id-pill">#{item.id}</span>
                              <div>
                                <div className="supplier-name">{item.company_name || 'Unnamed Supplier'}</div>
                                <div className="supplier-subtext">{item.business_type || 'N/A'}</div>
                              </div>
                            </div>
                            <span className={`status-badge ${statusMeta.className}`}>{statusMeta.label}</span>
                          </div>

                          <div className="supplier-card-details">
                            <div className="supplier-card-detail-row">
                              <span className="supplier-info-label">Contact</span>
                              <span>{item.contact_person || item.email || 'N/A'}</span>
                            </div>
                            <div className="supplier-card-detail-row">
                              <span className="supplier-info-label">Email</span>
                              <span>{item.email || 'N/A'}</span>
                            </div>
                          </div>

                          <div className="supplier-card-actions">
                            <button
                              className="supplier-inline-action-btn view"
                              type="button"
                              title="Review"
                              onClick={(event) => {
                                event.stopPropagation()
                                handleSelectSupplier(item)
                              }}
                            >
                              <Eye size={14} />
                              <span>View Details</span>
                            </button>
                            {item.status !== 'Approved' && (
                              <>
                                <button
                                  className="supplier-inline-action-btn approve"
                                  type="button"
                                  title="Approve"
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    handleApprove(item.id)
                                  }}
                                  disabled={supplierActioningId === item.id}
                                >
                                  <Check size={14} />
                                  <span>Approve</span>
                                </button>
                                <button
                                  className="supplier-inline-action-btn reject"
                                  type="button"
                                  title="Reject"
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    handleReject(item.id)
                                  }}
                                  disabled={supplierActioningId === item.id}
                                >
                                  <X size={14} />
                                  <span>Reject</span>
                                </button>
                              </>
                            )}
                            <button
                              className="supplier-inline-action-btn reject"
                              type="button"
                              title="Delete Account"
                              onClick={(event) => {
                                event.stopPropagation()
                                requestSupplierDelete(item.id)
                              }}
                              disabled={supplierDeletingId === item.id}
                            >
                              <Trash2 size={14} />
                              <span>Delete Account</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {selectedSupplierId && (
                <div className="supplier-preview-overlay" role="dialog" aria-modal="true" aria-labelledby="supplier-review-title" onClick={closeSupplierReview}>
                  <div className="supplier-preview-modal supplier-review-modal" onClick={(event) => event.stopPropagation()}>
                    {!selectedSupplierDetails ? (
                      <div className="supplier-empty-state">
                        <Building2 size={24} />
                        <h3>Loading supplier review</h3>
                        <p>Loading the supplier profile and compliance documents.</p>
                      </div>
                    ) : (
                  <>
                    <div className="supplier-detail-header">
                      <div>
                        <div className="eyebrow">BAC Administrator Review</div>
                        <h3 id="supplier-review-title">{selectedSupplierDetails.company_name}</h3>
                        <p>{selectedSupplierDetails.business_type || 'Business registration review'}</p>
                      </div>
                      <div className="supplier-review-header-actions">
                        <span className={`status-badge ${getSupplierStatusMeta(selectedSupplierDetails.status).className}`}>
                          {getSupplierStatusMeta(selectedSupplierDetails.status).label}
                        </span>
                        <button className="icon-action-btn" type="button" onClick={closeSupplierReview} aria-label="Close supplier review">
                          <X size={14} />
                        </button>
                      </div>
                    </div>

                    <div className="supplier-detail-grid">
                      <div className="supplier-detail-panel">
                        <div className="supplier-panel-title">Company Information</div>
                        <div className="supplier-info-grid">
                          <div><span className="supplier-info-label">Company Name</span><div>{selectedSupplierDetails.company_name || 'N/A'}</div></div>
                          <div><span className="supplier-info-label">Business Type</span><div>{selectedSupplierDetails.business_type || 'N/A'}</div></div>
                          <div><span className="supplier-info-label">Business Address</span><div>{selectedSupplierDetails.business_address || 'N/A'}</div></div>
                          <div><span className="supplier-info-label">Contact Person</span><div>{selectedSupplierDetails.contact_person || 'N/A'}</div></div>
                          <div><span className="supplier-info-label">Email</span><div>{selectedSupplierDetails.email || 'N/A'}</div></div>
                          <div><span className="supplier-info-label">Phone Number</span><div>{selectedSupplierDetails.contact_phone || 'N/A'}</div></div>
                        </div>
                      </div>

                      <div className="supplier-detail-panel supplier-categories-panel">
                        <div className="supplier-category-heading">
                          <div>
                            <div className="supplier-panel-title">Supplier Categories</div>
                            <div className="supplier-subtext">Registered procurement areas</div>
                          </div>
                          <span className="supplier-category-count">{selectedSupplierDetails.categories?.length || 0}</span>
                        </div>
                        <div className="supplier-badge-list supplier-category-list">
                          {(selectedSupplierDetails.categories && selectedSupplierDetails.categories.length > 0) ? (
                            selectedSupplierDetails.categories.map((category) => <span key={category} className="supplier-category-badge">{category}</span>)
                          ) : (
                            <div className="supplier-subtext">No categories captured.</div>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="supplier-detail-panel">
                      <div className="supplier-panel-title">Products / Services</div>
                      <div className="supplier-readonly-card">
                        {selectedSupplierDetails.products_services || selectedSupplierDetails.goods_services || 'No products or services description provided.'}
                      </div>
                    </div>

                    <div className="supplier-detail-panel">
                      <div className="supplier-panel-title">Document Verification</div>
                      <div className="supplier-document-list">
                        {(selectedSupplierDetails.documents || []).map((document) => {
                          const currentStatus = documentStatusDrafts[document.id] || document.verification_status || 'Pending'
                          const statusMeta = getDocumentStatusMeta(currentStatus)
                          return (
                            <div key={document.id} className="supplier-document-card">
                              <div className="supplier-document-head">
                                <div>
                                  <div className="supplier-document-name">{getDocumentLabel(document.doc_type)}</div>
                                  <div className="supplier-document-meta">{document.original_name || document.doc_type}</div>
                                </div>
                                <span className={`status-badge ${statusMeta.className}`}>{statusMeta.label}</span>
                              </div>
                              <div className="supplier-document-body">
                                <div><span className="supplier-info-label">Upload Status</span><div>{document.filename ? 'Uploaded' : 'Missing'}</div></div>
                                <div><span className="supplier-info-label">Uploaded File Name</span><div>{document.original_name || 'N/A'}</div></div>
                                <div><span className="supplier-info-label">File Type</span><div>{document.doc_type || 'N/A'}</div></div>
                                <div><span className="supplier-info-label">Upload Date</span><div>{document.uploaded_at ? new Date(document.uploaded_at).toLocaleDateString() : 'N/A'}</div></div>
                              </div>
                              <div className="supplier-document-actions">
                                <div className="document-verification-actions" aria-label={`Verification actions for ${getDocumentLabel(document.doc_type)}`}>
                                  <button type="button" className={`btn-sm document-status-btn document-status-verify ${currentStatus === 'Verified' ? 'selected' : ''}`} onClick={() => handleDocumentStatusChange(document.id, 'Verified')}>Verify</button>
                                  <button type="button" className={`btn-sm document-status-btn document-status-reject ${currentStatus === 'Rejected' ? 'selected' : ''}`} onClick={() => handleDocumentStatusChange(document.id, 'Rejected')}>Reject</button>
                                </div>
                                <button className="btn-sm btn-secondary document-preview-btn" type="button" onClick={() => openPreview(document)}>Preview</button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    <div className="supplier-detail-panel">
                      <div className="supplier-panel-title">Administrative Review</div>
                      <p className="supplier-subtext">Capture review notes and finalize the supplier decision.</p>
                      <label className="supplier-review-label" htmlFor="review-remarks">Review Remarks</label>
                      <textarea
                        id="review-remarks"
                        className="supplier-review-textarea"
                        value={reviewRemarks}
                        onChange={(event) => setReviewRemarks(event.target.value)}
                        placeholder="Example: Business Permit is expired."
                      />
                      <div className="supplier-action-section">
                        <div className="supplier-action-heading">Actions</div>
                        <div className="supplier-action-row">
                          {Object.keys(documentStatusDrafts).length > 0 && (
                            <button className="btn btn-login supplier-action-btn supplier-action-btn-primary" type="button" onClick={() => handleApplyDocumentChanges(selectedSupplierDetails.id)} disabled={supplierActioningId === selectedSupplierDetails.id}>
                              <Check size={16} />
                              {supplierActioningId === selectedSupplierDetails.id ? 'Saving...' : 'Apply Document Changes'}
                            </button>
                          )}
                          {selectedSupplierDetails.status !== 'Approved' && (
                            <>
                            <button className="btn btn-login supplier-action-btn supplier-action-btn-primary" type="button" onClick={() => handleApprove(selectedSupplierDetails.id)} disabled={supplierActioningId === selectedSupplierDetails.id}>
                              <Check size={16} />
                              Approve Registration
                            </button>
                            <button className="btn btn-danger supplier-action-btn supplier-action-btn-danger" type="button" onClick={() => handleReject(selectedSupplierDetails.id)} disabled={supplierActioningId === selectedSupplierDetails.id}>
                              <X size={16} />
                              Reject Registration
                            </button>
                            </>
                          )}
                          <button className="btn btn-secondary supplier-action-btn supplier-action-btn-outline" type="button" onClick={() => handleRequestCompliance(selectedSupplierDetails.id)} disabled={supplierActioningId === selectedSupplierDetails.id}>
                            <FileText size={16} />
                            Request Additional Documents
                          </button>
                          <button className="btn btn-danger supplier-action-btn supplier-action-btn-danger" type="button" onClick={() => requestSupplierDelete(selectedSupplierDetails.id)} disabled={supplierDeletingId === selectedSupplierDetails.id}>
                            <Trash2 size={16} />
                            Delete Account
                          </button>
                        </div>
                      </div>
                    </div>
                  </>
                    )}
                  </div>
                </div>
              )}
            </div>

            {previewVisible && previewDoc && (
              <div className="supplier-preview-overlay" role="dialog" aria-modal="true" onClick={closePreview}>
                <div className="supplier-preview-modal" onClick={(event) => event.stopPropagation()}>
                  <div className="supplier-preview-header">
                    <div>
                      <div className="supplier-panel-title">Document Preview</div>
                      <div className="supplier-subtext">{previewDoc.original_name || previewDoc.doc_type}</div>
                    </div>
                    <button className="icon-action-btn" type="button" onClick={closePreview} aria-label="Close preview">
                      <X size={14} />
                    </button>
                  </div>
                  {String(previewDoc.file_url || '').toLowerCase().endsWith('.pdf') ? (
                    <iframe className="supplier-preview-frame" src={previewDoc.file_url} title={previewDoc.original_name || previewDoc.doc_type} />
                  ) : (
                    <div className="supplier-preview-placeholder">
                      <img src={previewDoc.file_url} alt={previewDoc.original_name || previewDoc.doc_type} />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {currentTab === 'buyer-accounts' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>End User Accounts</h1>
              <p>Create and manage End User accounts for Purchase Request submission.</p>
            </div>
            <div className="buyer-account-layout">
              <section className="card buyer-account-panel">
                <div className="panel-header">
                  <div>
                    <h2>Create End User Account</h2>
                    <p className="supplier-subtext">New accounts are created with access to PR upload.</p>
                  </div>
                </div>
                <form className="buyer-account-form" onSubmit={handleBuyerAccountSubmit}>
                <label className="form-field">
                  <span>Full Name</span>
                  <input required value={buyerAccountForm.fullName} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, fullName: event.target.value }))} placeholder="End User name" />
                </label>
                <label className="form-field">
                  <span>Username</span>
                  <input required value={buyerAccountForm.username} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, username: event.target.value }))} placeholder="enduser.username" />
                </label>
                <label className="form-field">
                  <span>Email</span>
                  <input required type="email" value={buyerAccountForm.email} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="enduser@office.edu" />
                </label>
                <label className="form-field">
                  <span>Unit / Office</span>
                  <input required value={buyerAccountForm.unitOffice} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, unitOffice: event.target.value }))} placeholder="Procurement Office" />
                </label>
                <label className="form-field buyer-password-field">
                  <span>Password</span>
                  <div className="password-input-wrapper">
                    <input required type={showBuyerPassword ? 'text' : 'password'} minLength={8} value={buyerAccountForm.password} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, password: event.target.value }))} placeholder="At least 8 characters" />
                    <button type="button" className="password-toggle" onClick={() => setShowBuyerPassword((current) => !current)}>{showBuyerPassword ? 'Hide' : 'Show'}</button>
                  </div>
                </label>
                <label className="form-field buyer-password-field">
                  <span>Confirm Password</span>
                  <div className="password-input-wrapper">
                    <input required type={showBuyerPassword ? 'text' : 'password'} minLength={8} value={buyerAccountForm.confirmPassword} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, confirmPassword: event.target.value }))} placeholder="Re-enter password" />
                    <button type="button" className="password-toggle" onClick={() => setShowBuyerPassword((current) => !current)}>{showBuyerPassword ? 'Hide' : 'Show'}</button>
                  </div>
                </label>
                {buyerAccountError && <div className="alert alert-error" role="alert">{buyerAccountError}</div>}
                {buyerAccountMessage && <div className="alert alert-success" role="status">{buyerAccountMessage}</div>}
                <div className="form-actions">
                  <button type="submit" className="btn btn-primary" disabled={buyerAccountSaving}>{buyerAccountSaving ? 'Creating Account...' : 'Create End User Account'}</button>
                </div>
                </form>
              </section>

              <section className="card buyer-accounts-list-panel">
                <div className="buyer-accounts-list-header">
                  <div>
                    <h2>Managed Accounts</h2>
                    <p className="supplier-subtext">{buyerAccounts.length} End User account{buyerAccounts.length === 1 ? '' : 's'} registered</p>
                  </div>
                  <div className="buyer-account-search">
                    <Search size={16} />
                    <input type="search" value={buyerAccountSearch} onChange={(event) => setBuyerAccountSearch(event.target.value)} placeholder="Search accounts" aria-label="Search End User accounts" />
                  </div>
                </div>
                {buyerAccountsLoading ? (
                  <div className="buyer-accounts-empty">Loading accounts...</div>
                ) : filteredBuyerAccounts.length === 0 ? (
                  <div className="buyer-accounts-empty">No End User accounts found.</div>
                ) : (
                  <div className="buyer-accounts-list">
                    {filteredBuyerAccounts.map((account) => (
                      <article className="buyer-account-record" key={account.id}>
                        <div className="buyer-account-record-main">
                          <strong>{account.full_name || account.username}</strong>
                          <span>@{account.username}</span>
                          <small>{account.unit_office || 'Office not specified'} · {account.email || 'No email'}</small>
                        </div>
                        <div className="buyer-account-record-actions">
                          <button type="button" className="btn-sm btn-danger" onClick={() => setBuyerDeleteConfirm(account)} disabled={buyerAccountActionId === account.id}>
                            <Trash2 size={14} />
                            {buyerAccountActionId === account.id ? 'Deleting...' : 'Delete'}
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        {currentTab === 'pr-numbering-settings' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>PR Numbering</h1>
              <p>Configure how Purchase Request numbers are formatted and when the running sequence resets.</p>
            </div>
            <div className="buyer-account-layout">
              <section className="card buyer-account-panel">
                <div className="panel-header">
                  <div>
                    <h2>Number Format</h2>
                    <p className="supplier-subtext">Changes apply to PR numbers generated from now on - existing numbers are never rewritten.</p>
                  </div>
                </div>
                {prNumberFormatLoading && !prNumberFormatDraft ? (
                  <SkeletonRows count={5} />
                ) : !prNumberFormatDraft ? (
                  <div className="dashboard-empty-state"><span>Unable to load PR numbering settings.</span></div>
                ) : (
                  <form className="buyer-account-form" onSubmit={handleSavePrNumberFormat}>
                    <label className="form-field">
                      <span>Prefix (optional)</span>
                      <input
                        value={prNumberFormatDraft.prefix}
                        onChange={(event) => setPrNumberFormatDraft((prev) => ({ ...prev, prefix: event.target.value }))}
                        placeholder="e.g. CTU"
                        maxLength={20}
                      />
                    </label>
                    <label className="form-field">
                      <span>Date in number</span>
                      <select
                        value={prNumberFormatDraft.date_granularity}
                        onChange={(event) => setPrNumberFormatDraft((prev) => ({ ...prev, date_granularity: event.target.value }))}
                      >
                        <option value="none">No date</option>
                        <option value="year">Year only (YYYY)</option>
                        <option value="year_month">Year and month (YYYY-MM)</option>
                      </select>
                    </label>
                    <label className="form-field">
                      <span>Separator</span>
                      <input
                        value={prNumberFormatDraft.separator}
                        onChange={(event) => setPrNumberFormatDraft((prev) => ({ ...prev, separator: event.target.value }))}
                        placeholder="-"
                        maxLength={5}
                      />
                    </label>
                    <label className="form-field">
                      <span>Sequence digits</span>
                      <input
                        type="number"
                        min={2}
                        max={6}
                        value={prNumberFormatDraft.sequence_digits}
                        onChange={(event) => setPrNumberFormatDraft((prev) => ({ ...prev, sequence_digits: event.target.value }))}
                      />
                    </label>
                    <label className="form-field">
                      <span>Sequence resets</span>
                      <select
                        value={prNumberFormatDraft.reset_period}
                        onChange={(event) => setPrNumberFormatDraft((prev) => ({ ...prev, reset_period: event.target.value }))}
                      >
                        <option value="never">Never (accumulate forever)</option>
                        <option value="yearly">Yearly</option>
                        <option value="monthly">Monthly</option>
                      </select>
                    </label>

                    <div className="number-preview" aria-live="polite">
                      <span>Next PR number will look like</span>
                      <strong>{previewPrNumber(prNumberFormatDraft, prNumberFormat?.next_sequence || 1)}</strong>
                      <small>Recalculated once you save, based on existing PR numbers.</small>
                    </div>

                    {prNumberFormatError && <div className="alert alert-error" role="alert">{prNumberFormatError}</div>}
                    {prNumberFormatMessage && <div className="alert alert-success" role="status">{prNumberFormatMessage}</div>}
                    <div className="form-actions">
                      <button type="submit" className="btn btn-primary" disabled={prNumberFormatSaving}>
                        {prNumberFormatSaving ? 'Saving...' : 'Save PR Numbering Settings'}
                      </button>
                    </div>
                  </form>
                )}
              </section>
            </div>
          </div>
        )}

        {currentTab === 'pr-notification-settings' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>PR Notifications</h1>
              <p>Configure when End Users are emailed about their Purchase Request's status.</p>
            </div>
            <div className="buyer-account-layout">
              <section className="card buyer-account-panel">
                <div className="panel-header">
                  <div>
                    <h2>Status Email Settings</h2>
                    <p className="supplier-subtext">Applies to notifications going forward - already-sent emails are unaffected.</p>
                  </div>
                </div>
                {prNotificationSettingsLoading && !prNotificationSettingsDraft ? (
                  <SkeletonRows count={5} />
                ) : !prNotificationSettingsDraft ? (
                  <div className="dashboard-empty-state"><span>Unable to load PR notification settings.</span></div>
                ) : (
                  <form className="buyer-account-form" onSubmit={handleSavePrNotificationSettings}>
                    <div className="settings-toggle-list">
                      <label className="settings-toggle-row">
                        <input
                          type="checkbox"
                          checked={prNotificationSettingsDraft.enabled}
                          onChange={(event) => setPrNotificationSettingsDraft((prev) => ({ ...prev, enabled: event.target.checked }))}
                        />
                        <span>
                          <span className="settings-toggle-label">Enable PR status email notifications</span>
                          <small className="settings-toggle-hint">Master switch. Turn off to stop all PR status-change emails to End Users.</small>
                        </span>
                      </label>
                    </div>

                    <hr className="settings-toggle-divider" />

                    <div className="settings-toggle-list">
                      <span className="form-field-label">Notify when a PR reaches</span>
                      {[
                        ['notify_in_review', 'In Review'],
                        ['notify_matched', 'Matched'],
                        ['notify_approved', 'Approved'],
                        ['notify_rejected', 'Rejected'],
                      ].map(([field, label]) => (
                        <label key={field} className={`settings-toggle-row ${!prNotificationSettingsDraft.enabled ? 'is-disabled' : ''}`}>
                          <input
                            type="checkbox"
                            disabled={!prNotificationSettingsDraft.enabled}
                            checked={prNotificationSettingsDraft[field]}
                            onChange={(event) => setPrNotificationSettingsDraft((prev) => ({ ...prev, [field]: event.target.checked }))}
                          />
                          <span className="settings-toggle-label">{label}</span>
                        </label>
                      ))}
                    </div>

                    <hr className="settings-toggle-divider" />

                    <div className="settings-toggle-list">
                      <label className={`settings-toggle-row ${!prNotificationSettingsDraft.enabled ? 'is-disabled' : ''}`}>
                        <input
                          type="checkbox"
                          disabled={!prNotificationSettingsDraft.enabled}
                          checked={prNotificationSettingsDraft.mute_automatic_transitions}
                          onChange={(event) => setPrNotificationSettingsDraft((prev) => ({ ...prev, mute_automatic_transitions: event.target.checked }))}
                        />
                        <span>
                          <span className="settings-toggle-label">Don't notify for automatic status changes during category assignment</span>
                          <small className="settings-toggle-hint">
                            Prevents repeated emails while an admin is actively re-categorizing a PR's items (the automatic Matched/In Review
                            flip). Explicit status changes made from PR Review &amp; Monitoring always still notify, per the toggles above.
                          </small>
                        </span>
                      </label>
                    </div>

                    {prNotificationSettingsError && <div className="alert alert-error" role="alert">{prNotificationSettingsError}</div>}
                    {prNotificationSettingsMessage && <div className="alert alert-success" role="status">{prNotificationSettingsMessage}</div>}
                    <div className="form-actions">
                      <button type="submit" className="btn btn-primary" disabled={prNotificationSettingsSaving}>
                        {prNotificationSettingsSaving ? 'Saving...' : 'Save PR Notification Settings'}
                      </button>
                    </div>
                  </form>
                )}
              </section>
            </div>
          </div>
        )}

        {currentTab === 'assign-categories' && workflowPrId && (
          <AssignCategories
            prId={workflowPrId}
            apiBase={apiBaseUrl}
            onComplete={(prId) => setCurrentTab('supplier-matching')}
            onBack={() => setCurrentTab('pr-monitoring')}
          />
        )}

        {currentTab === 'supplier-matching' && !workflowPrId && (
          <UnmatchedPurchaseRequests
            apiBase={apiBaseUrl}
            onContinue={handleContinueMatching}
          />
        )}

        {currentTab === 'supplier-matching' && workflowPrId && (
          <SupplierMatchingView
            prId={workflowPrId}
            apiBase={apiBaseUrl}
            onBack={() => setCurrentTab('assign-categories')}
          />
        )}

        {currentTab === 'rfq-responses' && <AdminRFQManagement apiBaseUrl={apiBaseUrl} />}
        {currentTab === 'manual-rfqs' && <ManualRFQsView apiBaseUrl={apiBaseUrl} />}

        {currentTab === 'pr-monitoring' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>PR Review & Monitoring</h1>
              <p>Review unnumbered Purchase Requests and monitor numbered requests through the procurement workflow.</p>
            </div>

            <div className="admin-actions" style={{ marginBottom: '16px' }}>
              <button className="btn-sm btn-secondary" onClick={loadPrRecords} disabled={prLoading}>
                <RefreshCw size={14} className={prLoading ? 'spin' : ''} />
                {prLoading ? 'Refreshing...' : 'Refresh'}
              </button>
              <button
                type="button"
                className="btn-sm btn-secondary"
                onClick={handleExportPurchaseRequests}
                disabled={exportingPrs}
              >
                <Download size={14} />
                {exportingPrs ? 'Exporting...' : 'Export Report'}
              </button>
            </div>

            {prError && (
              <div className="alert alert-error" style={{ marginBottom: '16px' }}>
                <strong>Unable to load PR records.</strong> {prError}
              </div>
            )}
            {exportError && (
              <div className="alert alert-error" style={{ marginBottom: '16px' }}>{exportError}</div>
            )}

            <div className="admin-checklist pr-review-queue" style={{ marginBottom: '16px' }}>
              <div className="pr-review-queue-header">
                <div>
                  <h3>Purchase Requests Awaiting PR Number</h3>
                  <p>Review and complete these saved requests before they enter PR monitoring.</p>
                </div>
              </div>
              {unnumberedPrRecords.length === 0 ? (
                <div className="dashboard-empty-state"><CheckCircle size={20} /><span>No Purchase Requests are awaiting a PR number.</span></div>
              ) : (
                <div className="pr-review-queue-list">
                  {unnumberedPrRecords.map((pr) => (
                    <div className="pr-review-queue-row" key={pr.id}>
                      <div><strong>#{pr.id}</strong><span>{pr.entity_name || 'Unnamed entity'}</span><small>{pr.office_section || 'Office not specified'}</small></div>
                      <span className={`status-badge ${getPrStatusMeta(pr.status).className}`}>{getPrStatusMeta(pr.status).label}</span>
                      <button
                        type="button"
                        className="btn-sm pr-review-action-btn pr-review-btn"
                        onClick={() => handleEditPr(pr)}
                      >
                        <Pencil size={14} />
                        Review PR
                      </button>
                      <button
                        type="button"
                        className="btn-sm btn-danger pr-queue-delete-btn"
                        title="Delete Purchase Request"
                        onClick={() => requestPrDelete(pr.id)}
                        disabled={prDeletingId === pr.id}
                      >
                        <Trash2 size={14} />
                        {prDeletingId === pr.id ? 'Deleting...' : 'Delete'}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pr-monitor-table-shell">
              <div className="pr-monitor-table-wrapper">
                <div className="pr-monitor-table-head">
                  <span>ID</span>
                  <span>PR Number</span>
                  <span>Entity</span>
                  <span>Office</span>
                  <span>Items</span>
                  <span>Grand Total</span>
                  <span>Status</span>
                  <span>Created</span>
                  <span>Next Step</span>
                  <span>Actions</span>
                </div>

                {numberedPrRecords.length === 0 && !prLoading && (
                  <div className="pr-monitor-table-row">
                    <span className="admin-entry-name" style={{ gridColumn: '1 / -1' }}>No numbered Purchase Requests found yet.</span>
                  </div>
                )}

                {prLoading && prRecords.length === 0 && (
                  <div className="pr-monitor-table-row" style={{ gridColumn: '1 / -1' }}>
                    <SkeletonRows count={4} />
                  </div>
                )}

                {numberedPrRecords.map((pr) => {
                  const isEditing = Boolean(editingStatusById[pr.id])
                  const statusMeta = getPrStatusMeta(pr.status)
                  return (
                    <div key={pr.id} className="pr-monitor-table-row">
                      <span className="admin-entry-id">{pr.id}</span>
                      <span>
                        <button
                          type="button"
                          className="pr-number-link"
                          title="View Purchase Request"
                          onClick={() => handleViewPr(pr)}
                        >
                          {pr.pr_no || 'N/A'}
                        </button>
                      </span>
                      <span className="admin-entry-name">{pr.entity_name || 'N/A'}</span>
                      <span>{pr.office_section || 'N/A'}</span>
                      <span>{pr.items_count ?? 0}</span>
                      <span className="pr-currency">{formatPeso(pr.grand_total ?? 0)}</span>
                      <span>
                        {!isEditing ? (
                          <span className={`status-badge ${statusMeta.className}`}>
                            {statusMeta.label}
                          </span>
                        ) : (
                          <select
                            value={pendingStatusById[pr.id] || pr.status || 'uploaded'}
                            disabled={prSavingId === pr.id || prDeletingId === pr.id}
                            onChange={(e) => setPendingStatusById((prev) => ({ ...prev, [pr.id]: e.target.value }))}
                            className="pr-status-select"
                          >
                            {prStatusOptions.map((option) => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                          </select>
                        )}
                      </span>
                      <span>{pr.created_at ? new Date(pr.created_at).toLocaleString() : 'N/A'}</span>
                      <span className="pr-matching-action">
                        {pr.status !== 'uploaded' && !pr.has_quotation && (
                          <button
                            type="button"
                            className="btn-sm btn-primary"
                            onClick={() => {
                              setWorkflowPrId(pr.id)
                              setCurrentTab(pr.category?.trim() ? 'supplier-matching' : 'assign-categories')
                            }}
                          >
                            {pr.category?.trim() ? 'Continue Matching' : 'Category Selection'}
                          </button>
                        )}
                      </span>
                      <span className="pr-row-actions">
                        <button
                          type="button"
                          className="icon-action-btn"
                          title="View"
                          aria-label="View"
                          onClick={() => handleViewPr(pr)}
                        >
                          <Eye size={14} />
                        </button>
                        {!isEditing ? (
                          <button
                            type="button"
                            className="icon-action-btn"
                            title="Edit Purchase Request"
                            aria-label="Edit Purchase Request"
                            disabled={prSavingId === pr.id || prDeletingId === pr.id}
                            onClick={() => handleEditPr(pr)}
                          >
                            <Pencil size={14} />
                          </button>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="icon-action-btn"
                              title="Save"
                              aria-label="Save"
                              disabled={prSavingId === pr.id || prDeletingId === pr.id}
                              onClick={() => handleSaveStatusEdit(pr)}
                            >
                              <Check size={14} />
                            </button>
                            <button
                              type="button"
                              className="icon-action-btn"
                              title="Cancel"
                              aria-label="Cancel"
                              disabled={prSavingId === pr.id || prDeletingId === pr.id}
                              onClick={() => handleCancelStatusEdit(pr.id)}
                            >
                              <X size={14} />
                            </button>
                          </>
                        )}
                        {!isEditing && (
                          <button
                            type="button"
                            className="icon-action-btn"
                            title="Edit Status"
                            aria-label="Edit Status"
                            disabled={prSavingId === pr.id || prDeletingId === pr.id}
                            onClick={() => handleStartStatusEdit(pr)}
                          >
                            <Settings size={14} />
                          </button>
                        )}
                        <button
                          type="button"
                          className="icon-action-btn delete"
                          title={prDeletingId === pr.id ? 'Deleting...' : 'Delete'}
                          aria-label="Delete"
                          disabled={prDeletingId === pr.id || prSavingId === pr.id}
                          onClick={() => requestPrDelete(pr.id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>

            {editingPr && (
              <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="edit-pr-title" onClick={closeEditPr}>
                <div className="modal-content pr-edit-modal" onClick={(event) => event.stopPropagation()}>
                  <div className="modal-header">
                    <h2 id="edit-pr-title">Edit Purchase Request {editingPr.pr_no || `#${editingPr.id}`}</h2>
                    <button type="button" className="modal-close" onClick={closeEditPr} aria-label="Close edit Purchase Request">×</button>
                  </div>
                  {editPrLoading || !editPrForm ? (
                    <div className="modal-body"><SkeletonRows count={4} /></div>
                  ) : (
                    <>
                      <div className="modal-body pr-edit-body">
                        <div className="pr-review-split">
                          <aside className="pr-review-preview-pane card">
                            <header className="panel-header">
                              <h3>Original PR Document</h3>
                              {editPrSourceUrl && (
                                <a className="btn-sm btn-secondary" href={editPrSourceUrl} target="_blank" rel="noreferrer">Open document</a>
                              )}
                            </header>
                            {editPrSourceUrl ? (
                              <iframe src={editPrSourceUrl} title="Original Purchase Request document" />
                            ) : (
                              <div className="empty-state pr-review-preview-empty">
                                <p>No original document on file.</p>
                              </div>
                            )}
                          </aside>

                          <div className="pr-upload-grid">
                            <section className="card form-panel">
                              <header className="panel-header">
                                <h3><Search size={18} /> Purchase Request Details</h3>
                              </header>

                              {!editPrForm.pr_no && (
                                <div className="pr-review-numbering">
                                  <span className="form-field-label">Assign Final PR Number</span>
                                  <div className="numbering-options">
                                    <label><input type="radio" name="review-pr-numbering" checked={editPrNumberMode === 'automatic'} onChange={() => setEditPrNumberMode('automatic')} /> Automatic</label>
                                    <label><input type="radio" name="review-pr-numbering" checked={editPrNumberMode === 'custom'} onChange={() => setEditPrNumberMode('custom')} /> Custom</label>
                                  </div>
                                  {editPrNumberMode === 'automatic' ? (
                                    <div className="pr-review-number-preview">
                                      <span>Next available number</span>
                                      <small>Will be assigned when you click "Assign PR Number" below.</small>
                                    </div>
                                  ) : (
                                    <div className="pr-review-custom-number">
                                      <label htmlFor="review-custom-pr-number">Custom PR Number</label>
                                      <input id="review-custom-pr-number" value={editPrCustomNumber} onChange={(event) => setEditPrCustomNumber(event.target.value)} placeholder="e.g. 2026-09-001" />
                                      <small>Must match the PR number format configured in PR Numbering settings.</small>
                                    </div>
                                  )}
                                </div>
                              )}

                              <div className="floating-grid">
                                {editPrForm.pr_no && (
                                  <FieldShell id="edit-pr-no" label="Assigned PR Number" value={editPrForm.pr_no} readOnly full />
                                )}
                                <FieldShell
                                  id="edit-entity-name"
                                  label="Entity Name *"
                                  value={editPrForm.entity_name}
                                  onChange={(value) => setEditPrForm((prev) => ({ ...prev, entity_name: value }))}
                                  full
                                />
                                <FieldShell
                                  id="edit-fund-cluster"
                                  label="Fund Cluster"
                                  value={editPrForm.fund_cluster}
                                  onChange={(value) => setEditPrForm((prev) => ({ ...prev, fund_cluster: value }))}
                                />
                                <FieldShell
                                  id="edit-office-section"
                                  label="Office / Section"
                                  value={editPrForm.office_section}
                                  onChange={(value) => setEditPrForm((prev) => ({ ...prev, office_section: value }))}
                                />
                                <FieldShell
                                  id="edit-rc-code"
                                  label="Responsibility Center Code"
                                  value={editPrForm.responsibility_center_code}
                                  onChange={(value) => setEditPrForm((prev) => ({ ...prev, responsibility_center_code: value }))}
                                  full
                                />
                                <FieldShell
                                  id="edit-date"
                                  label="Date"
                                  type="date"
                                  value={editPrForm.date}
                                  onChange={(value) => setEditPrForm((prev) => ({ ...prev, date: value }))}
                                />
                                <FieldShell
                                  id="edit-purpose"
                                  label="Purpose"
                                  value={editPrForm.purpose}
                                  onChange={(value) => setEditPrForm((prev) => ({ ...prev, purpose: value }))}
                                  full
                                  isTextarea
                                />
                              </div>

                              <div className="signature-grid">
                                {[
                                  ['requested_by', 'Requested By'],
                                  ['funds_available_by', 'Funds Available'],
                                  ['approved_by', 'Approved By'],
                                  ['twg_verified_by', 'Technical Working Group'],
                                ].map(([field, title]) => (
                                  <SignatureBlock
                                    key={field}
                                    title={title}
                                    nameKey={field}
                                    fields={editPrForm}
                                    onFieldChange={(key, value) => setEditPrForm((prev) => ({ ...prev, [key]: value }))}
                                    signatureState={editPrSignatureValidation?.signatories?.[ADMIN_SIGNATORY_DETECTOR_KEY[field]] || null}
                                  />
                                ))}
                              </div>

                              <SignatureValidationPanel
                                validation={editPrSignatureValidation}
                                onRecheck={handleRecheckEditPrSignatures}
                                rechecking={editPrSignatureChecking}
                                hasDocument={Boolean(editPrSourceFilename)}
                              />

                              <div className="requested-items-block">
                                <div className="items-header">
                                  <h4>Requested Items</h4>
                                  <div className="items-header-actions">
                                    <button
                                      type="button"
                                      className="btn btn-secondary"
                                      onClick={() => setEditPrForm((prev) => ({ ...prev, items: [...prev.items, { stock_property_no: '', unit: '', item_description: '', quantity: 0, unit_cost: 0, category: '' }] }))}
                                    >
                                      <Plus size={16} />
                                      Add Item
                                    </button>
                                  </div>
                                </div>

                                <div className="table-shell">
                                  <table className="enterprise-table items-table requested-items-table">
                                    <thead>
                                      <tr>
                                        <th style={{ width: '48px' }}>Item No.</th>
                                        <th style={{ width: '130px' }}>Stock/Property No.</th>
                                        <th className="requested-item-unit-cell" style={{ width: '100px' }}>Unit</th>
                                        <th className="requested-item-description-cell">Description</th>
                                        <th style={{ width: '80px' }}>Qty</th>
                                        <th style={{ width: '120px' }}>Unit Cost</th>
                                        <th style={{ width: '120px' }}>Total</th>
                                        <th style={{ width: '160px' }}>Category</th>
                                        <th style={{ width: '56px' }}>Actions</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {editPrForm.items.length > 0 ? editPrForm.items.map((item, index) => {
                                        const qty = parseFloat(item.quantity) || 0
                                        const unitCost = parseFloat(item.unit_cost) || 0
                                        const total = (qty * unitCost).toFixed(2)
                                        const updateItem = (patch) => setEditPrForm((prev) => ({
                                          ...prev,
                                          items: prev.items.map((current, itemIndex) => itemIndex === index ? { ...current, ...patch } : current),
                                        }))
                                        return (
                                          <tr key={`${editingPr.id}-item-${index}`}>
                                            <td>{index + 1}</td>
                                            <td>
                                              <input aria-label={`Item ${index + 1} stock number`} value={item.stock_property_no} onChange={(event) => updateItem({ stock_property_no: event.target.value })} />
                                            </td>
                                            <td className="requested-item-unit-cell">
                                              <input aria-label={`Item ${index + 1} unit`} value={item.unit} onChange={(event) => updateItem({ unit: event.target.value })} />
                                            </td>
                                            <td className="requested-item-description-cell">
                                              <AutoGrowTextarea
                                                value={item.item_description}
                                                onChange={(event) => updateItem({ item_description: event.target.value })}
                                                className="requested-item-description"
                                                aria-label={`Item ${index + 1} description`}
                                              />
                                            </td>
                                            <td>
                                              <input aria-label={`Item ${index + 1} quantity`} type="number" min="0" step="0.01" value={item.quantity} onChange={(event) => updateItem({ quantity: event.target.value })} />
                                            </td>
                                            <td>
                                              <input aria-label={`Item ${index + 1} unit cost`} type="number" min="0" step="0.01" value={item.unit_cost} onChange={(event) => updateItem({ unit_cost: event.target.value })} />
                                            </td>
                                            <td>{total}</td>
                                            <td>
                                              <input aria-label={`Item ${index + 1} category`} value={item.category} onChange={(event) => updateItem({ category: event.target.value })} />
                                            </td>
                                            <td>
                                              <button
                                                type="button"
                                                className="icon-action-btn delete-icon-btn"
                                                aria-label={`Remove item ${index + 1}`}
                                                onClick={() => setEditPrForm((prev) => ({ ...prev, items: prev.items.filter((_, itemIndex) => itemIndex !== index) }))}
                                              >
                                                <Trash2 size={15} />
                                              </button>
                                            </td>
                                          </tr>
                                        )
                                      }) : (
                                        <tr>
                                          <td colSpan={9}>
                                            <div className="table-empty-state">
                                              <p>No line items yet.</p>
                                            </div>
                                          </td>
                                        </tr>
                                      )}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            </section>
                          </div>
                        </div>
                      </div>
                      <div className="modal-actions">
                        <button type="button" className="btn btn-outline" onClick={closeEditPr} disabled={editPrSaving}>Cancel</button>
                        <button type="button" className="btn btn-secondary" onClick={() => handleSavePrEdit(false)} disabled={editPrSaving || !editPrForm.entity_name.trim()}>{editPrSaving ? 'Saving...' : 'Save Corrections'}</button>
                        {!editPrForm.pr_no && (
                          <button type="button" className="btn btn-primary" onClick={() => handleSavePrEdit(true)} disabled={editPrSaving || !editPrForm.entity_name.trim()}>
                            {editPrSaving ? 'Assigning...' : 'Assign PR Number'}
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            <div className="admin-checklist">
              <h3>Monitoring Notes</h3>
              <ul>
                <li>Purchase Requests are submitted by End Users; review them here before supplier matching.</li>
                <li>Use this list as the source set for upcoming supplier matching logic.</li>
                <li>Refresh after saving a PR to display latest records.</li>
              </ul>
            </div>

            <div className="admin-checklist" style={{ marginTop: '16px' }}>
              <h3>Matched Suppliers</h3>
              <p style={{ marginTop: 0, marginBottom: 16, color: '#64748b' }}>
                Review matched supplier suggestions and confirm assignment per Purchase Request.
              </p>

              <div className="supplier-match-grid">
                {matchedSupplierCards.map((card) => {
                  const supplier = card.supplier || {}
                  const companyName = supplier.company_name || supplier.name || 'Unnamed Supplier'
                  const category = supplier.category || supplier.industry || 'General'
                  const contact = supplier.contact_person || supplier.contact || 'N/A'
                  const email = supplier.email || 'N/A'
                  const address = supplier.address || 'N/A'
                  const verified = Boolean(supplier.verified || supplier.is_verified)
                  const score = Number(supplier.match_percentage ?? supplier.score ?? 0)

                  return (
                    <article key={card.id} className="supplier-match-card">
                      <div className="supplier-match-head">
                        <h4>{companyName}</h4>
                        <span className={`status-badge ${verified ? 'status-open' : 'status-review'}`}>
                          {verified ? 'Verified' : 'Pending'}
                        </span>
                      </div>
                      <div className="supplier-match-meta">PR: {card.prNo}</div>
                      <div className="supplier-match-body">
                        <div><strong>Category:</strong> {category}</div>
                        <div><strong>Contact:</strong> {contact}</div>
                        <div><strong>Email:</strong> {email}</div>
                        <div><strong>Address:</strong> {address}</div>
                      </div>
                      <div className="supplier-match-foot">
                        <span className="match-pill">Match: {Number.isFinite(score) ? `${score.toFixed(0)}%` : '0%'}</span>
                        <button className="btn-sm btn-primary" onClick={() => handleSelectMatchedSupplier(card)}>Select</button>
                      </div>
                    </article>
                  )
                })}

                {!matchedSupplierCards.length && (
                  <div className="supplier-match-empty">
                    No matched suppliers available yet. Upload and process more PR records to generate supplier matches.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        {prDeleteConfirmId && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-pr-title" onClick={() => !prDeletingId && setPrDeleteConfirmId(null)}>
            <div className="modal-content delete-confirm-modal" onClick={(event) => event.stopPropagation()}>
              <div className="modal-header"><h3 id="delete-pr-title">Delete Purchase Request</h3><button type="button" className="modal-close" onClick={() => setPrDeleteConfirmId(null)} disabled={Boolean(prDeletingId)}>×</button></div>
              <div className="modal-body"><p>Are you sure you want to delete Purchase Request <strong>#{prDeleteConfirmId}</strong>?</p><p className="helper-text">This action cannot be undone.</p></div>
              <div className="modal-actions"><button type="button" className="btn btn-secondary" onClick={() => setPrDeleteConfirmId(null)} disabled={Boolean(prDeletingId)}>Cancel</button><button type="button" className="btn btn-danger" onClick={() => handlePrDelete(prDeleteConfirmId)} disabled={Boolean(prDeletingId)}>{prDeletingId ? 'Deleting...' : 'Confirm Delete'}</button></div>
            </div>
          </div>
        )}
        {supplierDeleteConfirm && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-supplier-title" onClick={() => !supplierDeletingId && setSupplierDeleteConfirm(null)}>
            <div className="modal-content delete-confirm-modal" onClick={(event) => event.stopPropagation()}>
              <div className="modal-header"><h3 id="delete-supplier-title">Delete Supplier Account</h3><button type="button" className="modal-close" onClick={() => setSupplierDeleteConfirm(null)} disabled={Boolean(supplierDeletingId)}>×</button></div>
              <div className="modal-body"><p>Permanently delete <strong>{supplierDeleteConfirm.companyName}</strong>?</p><p className="helper-text">This removes the supplier login, its registration, documents, RFQs, and submitted quotations. This action cannot be undone.</p></div>
              <div className="modal-actions"><button type="button" className="btn btn-secondary" onClick={() => setSupplierDeleteConfirm(null)} disabled={Boolean(supplierDeletingId)}>Cancel</button><button type="button" className="btn btn-danger" onClick={() => handleDeleteSupplier(supplierDeleteConfirm.id)} disabled={Boolean(supplierDeletingId)}>{supplierDeletingId ? 'Deleting...' : 'Delete Account'}</button></div>
            </div>
          </div>
        )}
        {buyerDeleteConfirm && (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-buyer-title" onClick={() => !buyerAccountActionId && setBuyerDeleteConfirm(null)}>
            <div className="modal-content delete-confirm-modal" onClick={(event) => event.stopPropagation()}>
              <div className="modal-header"><h3 id="delete-buyer-title">Delete End User Account</h3><button type="button" className="modal-close" onClick={() => setBuyerDeleteConfirm(null)} disabled={Boolean(buyerAccountActionId)}>×</button></div>
              <div className="modal-body"><p>Permanently delete the account for <strong>{buyerDeleteConfirm.full_name || buyerDeleteConfirm.username}</strong>?</p><p className="helper-text">The user will no longer be able to sign in. This action cannot be undone.</p></div>
              <div className="modal-actions"><button type="button" className="btn btn-secondary" onClick={() => setBuyerDeleteConfirm(null)} disabled={Boolean(buyerAccountActionId)}>Cancel</button><button type="button" className="btn btn-danger" onClick={() => handleDeleteBuyerAccount(buyerDeleteConfirm)} disabled={Boolean(buyerAccountActionId)}>{buyerAccountActionId ? 'Deleting...' : 'Delete Account'}</button></div>
            </div>
          </div>
        )}
      </div>
      {reviewAction && (
        <div className="supplier-preview-overlay" role="dialog" aria-modal="true" onClick={() => !supplierActioningId && setReviewAction(null)}>
          <div className="supplier-review-modal" onClick={(event) => event.stopPropagation()}>
            <div className="supplier-preview-header">
              <div>
                <div className="supplier-panel-title">{reviewAction.actionName === 'approve' ? 'Approve Supplier' : reviewAction.actionName === 'reject' ? 'Reject Supplier' : 'Request Additional Documents'}</div>
                <div className="supplier-subtext">{reviewAction.companyName}</div>
              </div>
              <button className="icon-action-btn" type="button" onClick={() => setReviewAction(null)} disabled={Boolean(supplierActioningId)} aria-label="Close review action modal"><X size={14} /></button>
            </div>
            <p>Confirm this action and provide review remarks for the supplier record.</p>
            <label className="supplier-review-label" htmlFor="review-action-remarks">Review Remarks{reviewAction.nextStatus !== 'Approved' ? ' *' : ''}</label>
            <textarea id="review-action-remarks" className="supplier-review-textarea" value={reviewRemarks} onChange={(event) => setReviewRemarks(event.target.value)} placeholder="Enter review remarks" autoFocus />
            {supplierError && <div className="alert alert-error" style={{ marginTop: 12 }}>{supplierError}</div>}
            <div className="form-actions">
              <button type="button" className="btn-secondary" onClick={() => setReviewAction(null)} disabled={Boolean(supplierActioningId)}>Cancel</button>
              <button type="button" className={reviewAction.nextStatus === 'Rejected' ? 'btn-danger' : 'btn-primary'} onClick={() => executeReviewDecision(reviewAction.supplierId, reviewAction.nextStatus, reviewAction.actionName)} disabled={Boolean(supplierActioningId)}>{supplierActioningId ? 'Saving...' : 'Confirm'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const UploadForm = () => {
  const [file, setFile] = React.useState(null)
  const [uploading, setUploading] = React.useState(false)
  const [result, setResult] = React.useState(null)

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000'

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return alert('Please choose a file')
    setUploading(true)
    setResult(null)

    try {
      const fd = new FormData()
      fd.append('file', file)

      const res = await apiFetch(`${apiBaseUrl}/api/upload/`, {
        method: 'POST',
        body: fd,
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data?.message || 'Upload failed')
      setResult(data)
    } catch (err) {
      console.error(err)
      alert('Upload failed: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <div style={{ marginBottom: 12 }}>
        <input type="file" accept=".pdf,image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn-primary" type="submit" disabled={uploading}>{uploading ? 'Uploading...' : 'Upload and Scan'}</button>
        <button type="button" className="btn-secondary" onClick={() => { setFile(null); setResult(null) }}>Reset</button>
      </div>

      {result && (
        <div style={{ marginTop: 16 }}>
          <h3>Extracted Fields</h3>
          <pre style={{ whiteSpace: 'pre-wrap', background: '#f7f7f7', padding: 12 }}>{JSON.stringify(result.fields, null, 2)}</pre>
          <details style={{ marginTop: 8 }}>
            <summary>Raw text (truncated)</summary>
            <pre style={{ whiteSpace: 'pre-wrap', background: '#fff', padding: 12, maxHeight: 300, overflow: 'auto' }}>{(result.rawText || '').slice(0, 2000)}</pre>
          </details>
        </div>
      )}
    </form>
  )
}

const Register = () => {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  const [formData, setFormData] = React.useState({
    companyName: '',
    businessType: '',
    legalEntity: '',
    registrationNumber: '',
    dateEstablished: '',
    businessAddress: '',
    tin: '',
    philgepsNumber: '',
    contactName: '',
    contactTitle: '',
    contactEmail: '',
    username: '',
    password: '',
    confirmPassword: '',
    contactPhone: '',
    altContactName: '',
    altContactEmail: '',
    authorizedRepName: '',
    authorizedRepTitle: '',
    authorizedRepEmail: '',
    authorizedRepPhone: '',
    industryCategory: '',
    productServiceLines: '',
    supplierCategory: '',
    ownershipClassification: '',
    preferentialEligibility: '',
    businessPermitIssue: '',
    businessPermitExpiry: '',
    birIssueDate: '',
    birExpiryDate: '',
    philgepsExpiry: '',
  })

  const [uploads, setUploads] = React.useState({
    dtiCertificate: null,
    secRegistration: null,
    cdaRegistration: null,
    businessPermit: null,
    bir2303: null,
    taxClearance: null,
    philgepsCertificate: null,
  })

  const [message, setMessage] = React.useState('')

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleFileChange = (e) => {
    const { name, files } = e.target
    setUploads(prev => ({ ...prev, [name]: files[0] || null }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    const requiredFields = [
      'companyName',
      'businessType',
      'legalEntity',
      'registrationNumber',
      'businessAddress',
      'contactName',
      'contactTitle',
      'contactEmail',
      'username',
      'password',
      'confirmPassword',
      'contactPhone',
      'productServiceLines',
      'tin',
      'philgepsNumber',
    ]
    const missingFields = requiredFields.filter(field => !formData[field]?.trim())
    if (missingFields.length) {
      setMessage(`Please complete required fields: ${missingFields.join(', ')}`)
      return
    }

    if (!uploads.businessPermit || !uploads.bir2303 || !uploads.taxClearance || !uploads.philgepsCertificate) {
      setMessage('Please upload all required documents before submitting registration.')
      return
    }

    if (formData.password.length < 8) {
      setMessage('Password must be at least 8 characters long.')
      return
    }

    if (formData.password !== formData.confirmPassword) {
      setMessage('Passwords do not match.')
      return
    }

    const registrationDocRequired = {
      SoleProprietorship: 'dtiCertificate',
      Corporation: 'secRegistration',
      Partnership: 'secRegistration',
      Cooperative: 'cdaRegistration',
    }
    const docKey = registrationDocRequired[formData.legalEntity]
    if (docKey && !uploads[docKey]) {
      setMessage(`Please upload the required ${docKey.replace(/([A-Z])/g, ' $1')} for the selected legal entity.`)
      return
    }

    const submissionBusinessType = {
      SoleProprietorship: 'Sole Proprietorship',
      Corporation: 'Corporation',
      Partnership: 'Partnership',
      Cooperative: 'Cooperative',
    }[formData.legalEntity] || formData.businessType || 'Sole Proprietorship'

    const payload = new FormData()
    payload.append('companyName', formData.companyName.trim())
    payload.append('businessType', submissionBusinessType)
    payload.append('businessAddress', formData.businessAddress.trim())
    payload.append('tin', formData.tin.trim())
    payload.append('contactPerson', formData.contactName.trim())
    payload.append('contactNumber', formData.contactPhone.trim())
    payload.append('email', formData.contactEmail.trim())
    payload.append('username', formData.username.trim())
    payload.append('password', formData.password)
    payload.append('confirmPassword', formData.confirmPassword)
    payload.append('productsServices', formData.productServiceLines.trim())
    payload.append('categories', 'General')
    payload.append('legalEntity', formData.legalEntity)

    const fileMap = {
      bir2303: 'bir_registration',
      taxClearance: 'tax_clearance',
      philgepsCertificate: 'philgeps_registration',
      dtiCertificate: 'dti_registration',
      secRegistration: 'sec_registration',
      cdaRegistration: 'cda_registration',
    }

    Object.entries(fileMap).forEach(([sourceKey, targetKey]) => {
      const file = uploads[sourceKey]
      if (file) {
        payload.append(targetKey, file, file.name)
      }
    })

    const permitFile = uploads.businessPermit
    if (permitFile) {
      payload.append('mayor_permit', permitFile, permitFile.name)
      payload.append('business_permit', permitFile, permitFile.name)
    }

    try {
      const response = await apiFetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/register`, {
        method: 'POST',
        body: payload,
      })

      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        const details = Array.isArray(data?.errors) && data.errors.length
          ? data.errors.join(' ')
          : data?.message || 'Failed to submit supplier registration.'
        throw new Error(details)
      }

      setMessage(data?.message || 'Registration submitted successfully. BAC review is now pending.')
    } catch (error) {
      console.error(error)
      setMessage(error?.message || 'Failed to submit supplier registration.')
    }
  }

  const fileLabel = (file) => file ? file.name : 'No file selected'

  return (
    <div className="page-content">
      <h1>Supplier Registration</h1>
      <p>Submit your supplier profile and required BAC documents for registration and approval.</p>

      <form className="register-form" onSubmit={handleSubmit} style={{display:'grid',gap:24}}>
        <div className="form-columns">
          <section className="section-block">
            <h2>Supplier Information</h2>
            <div className="form-field">
              <input name="companyName" type="text" value={formData.companyName} onChange={handleChange} placeholder="Company / Supplier Name" required />
            </div>
            <div className="form-field">
              <input name="businessType" type="text" value={formData.businessType} onChange={handleChange} placeholder="Business Type (e.g. Goods, Services)" required />
            </div>
            <div className="form-field">
              <select name="legalEntity" value={formData.legalEntity} onChange={handleChange} required>
                <option value="">Legal Entity Type</option>
                <option value="SoleProprietorship">Sole Proprietorship</option>
                <option value="Corporation">Corporation</option>
                <option value="Partnership">Partnership</option>
                <option value="Cooperative">Cooperative</option>
              </select>
            </div>
            <div className="form-field">
              <input name="registrationNumber" type="text" value={formData.registrationNumber} onChange={handleChange} placeholder="Business Registration Number" required />
            </div>
            <div className="form-field">
              <input name="businessAddress" type="text" value={formData.businessAddress} onChange={handleChange} placeholder="Business Address" required />
            </div>
            <div className="form-field">
              <textarea name="productServiceLines" value={formData.productServiceLines} onChange={handleChange} placeholder="Product / Service Lines" rows={3} required />
            </div>
          </section>

          <section className="section-block">
            <h2>Contact Information</h2>
            <div className="form-field">
              <input name="contactName" type="text" value={formData.contactName} onChange={handleChange} placeholder="Primary Contact Name" required />
            </div>
            <div className="form-field">
              <input name="contactTitle" type="text" value={formData.contactTitle} onChange={handleChange} placeholder="Primary Contact Title" required />
            </div>
            <div className="form-field">
              <input name="contactEmail" type="email" value={formData.contactEmail} onChange={handleChange} placeholder="Primary Contact Email" required />
            </div>
            <div className="form-field">
              <input name="contactPhone" type="tel" value={formData.contactPhone} onChange={handleChange} placeholder="Primary Contact Phone" required />
            </div>
            <div className="form-field">
              <input name="altContactName" type="text" value={formData.altContactName} onChange={handleChange} placeholder="Alternate Contact Name" />
            </div>
            <div className="form-field">
              <input name="altContactEmail" type="email" value={formData.altContactEmail} onChange={handleChange} placeholder="Alternate Contact Email" />
            </div>
            <div className="form-field">
              <input name="authorizedRepName" type="text" value={formData.authorizedRepName} onChange={handleChange} placeholder="Authorized Representative Name" />
            </div>
            <div className="form-field">
              <input name="authorizedRepTitle" type="text" value={formData.authorizedRepTitle} onChange={handleChange} placeholder="Authorized Representative Title" />
            </div>
            <div className="form-field">
              <input name="authorizedRepEmail" type="email" value={formData.authorizedRepEmail} onChange={handleChange} placeholder="Authorized Representative Email" />
            </div>
            <div className="form-field">
              <input name="authorizedRepPhone" type="tel" value={formData.authorizedRepPhone} onChange={handleChange} placeholder="Authorized Representative Phone" />
            </div>
          </section>
        </div>

        <div className="form-columns">
          <section className="section-block">
            <h2>Supplier Account</h2>
            <div className="form-field">
              <input name="username" type="text" value={formData.username} onChange={handleChange} placeholder="Desired Username" required />
            </div>
            <div className="form-field">
              <input name="password" type="password" value={formData.password} onChange={handleChange} placeholder="Desired Password" required />
            </div>
            <div className="form-field">
              <input name="confirmPassword" type="password" value={formData.confirmPassword} onChange={handleChange} placeholder="Confirm Password" required />
            </div>
          </section>

          <section className="section-block">
            <h2>Business and Compliance Details</h2>
            <div className="form-field">
              <label>Tax Identification Number (TIN)</label>
              <input name="tin" type="text" value={formData.tin} onChange={handleChange} placeholder="Enter TIN" required />
            </div>
            <div className="form-field">
              <label>PhilGEPS Registration Number</label>
              <input name="philgepsNumber" type="text" value={formData.philgepsNumber} onChange={handleChange} placeholder="Enter PhilGEPS number" required />
            </div>
          </section>
        </div>

        <section className="section-block">
          <h2>Document Uploads</h2>
          <p>Upload required documents for supplier registration. Each document file should be PDF, JPG, or PNG.</p>

          <div className="form-columns">
            <div className="form-field">
              <label>Business Registration Documents</label>
              <input type="file" name="dtiCertificate" onChange={handleFileChange} accept=".pdf,.jpg,.jpeg,.png" />
              <small>{fileLabel(uploads.dtiCertificate)}</small>
            </div>
            <div className="form-field">
              <label>Mayor's / Business Permit</label>
              <input type="file" name="businessPermit" onChange={handleFileChange} accept=".pdf,.jpg,.jpeg,.png" />
              <small>{fileLabel(uploads.businessPermit)}</small>
            </div>

            <div className="form-field">
              <input type="file" name="secRegistration" onChange={handleFileChange} accept=".pdf,.jpg,.jpeg,.png" />
              <small>{fileLabel(uploads.secRegistration)}</small>
            </div>
            <div className="form-field">
              <label>BIR Requirements</label>
              <input type="file" name="bir2303" onChange={handleFileChange} accept=".pdf,.jpg,.jpeg,.png" />
              <small>{fileLabel(uploads.bir2303)}</small>
            </div>

            <div className="form-field">
              <input type="file" name="cdaRegistration" onChange={handleFileChange} accept=".pdf,.jpg,.jpeg,.png" />
              <small>{fileLabel(uploads.cdaRegistration)}</small>
            </div>
            <div className="form-field">
              <input type="file" name="taxClearance" onChange={handleFileChange} accept=".pdf,.jpg,.jpeg,.png" />
              <small>{fileLabel(uploads.taxClearance)}</small>
            </div>

            <div className="form-field">
              <label>PhilGEPS Certificate</label>
              <input type="file" name="philgepsCertificate" onChange={handleFileChange} accept=".pdf,.jpg,.jpeg,.png" />
              <small>{fileLabel(uploads.philgepsCertificate)}</small>
            </div>
          </div>
        </section>

        <section className="section-block">
          <h2>Submission Summary</h2>
          <div className="status-summary" style={{display:'grid',gap:10}}>
            <div><strong>Document Verification:</strong> All uploaded documents will be verified by BAC staff after submission.</div>
            <div><strong>Expiration Tracking:</strong> Permit and certificate expiry dates are recorded for renewal reminders.</div>
            <div><strong>Approval Workflow:</strong> BAC administrators will review, approve, or reject documents and will provide comments.</div>
          </div>
        </section>

        <div className="form-actions" style={{display:'flex',gap:10,flexWrap:'wrap'}}>
          <button type="submit" className="btn-login">Submit Registration</button>
        </div>
        {message && <div className="form-message" style={{color:'#b91c1c',fontWeight:600}}>{message}</div>}
      </form>
    </div>
  )
}

const Buyer = () => {
  const navigate = useNavigate()
  const user = React.useMemo(() => getStoredUser(), [])
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  const [currentTab, setCurrentTab] = React.useState('dashboard')
  const [navCollapsed, setNavCollapsed] = React.useState(false)
  const buyerStorageKey = `buyer_pr_ids_${user?.username || 'current'}`
  const [submittedPrIds, setSubmittedPrIds] = React.useState(() => {
    try {
      return JSON.parse(localStorage.getItem(buyerStorageKey) || '[]')
    } catch {
      return []
    }
  })

  const handlePrSubmitted = (prId) => {
    setSubmittedPrIds((current) => {
      const next = [prId, ...current.filter((id) => id !== prId)].slice(0, 10)
      localStorage.setItem(buyerStorageKey, JSON.stringify(next))
      return next
    })
  }

  const handleLogout = () => {
    apiFetch(`${apiBaseUrl}/api/logout/`, { method: 'POST' }).catch(() => {})
    authStore.clear()
    navigate('/login')
  }

  return (
    <div className={`admin-layout ${navCollapsed ? 'collapsed-nav' : ''}`}>
      {/* Buyer Sidebar Navigation */}
      <Sidebar
        portalLabel="End User Portal"
        activeId={currentTab}
        onSelect={setCurrentTab}
        navCollapsed={navCollapsed}
        onToggleNav={() => setNavCollapsed((v) => !v)}
        userPrimary={user?.name || user?.username || 'End User'}
        userSecondary={user?.email || ''}
        onLogout={handleLogout}
        groups={[
          { items: [
            { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
            { id: 'live-status', label: 'Live Status', icon: TrendingUp },
          ] },
        ]}
      />

      {/* Buyer Content */}
      <div className="admin-content">
        {currentTab === 'dashboard' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>End User Dashboard</h1>
              <p>Welcome back, {user?.name || 'End User'}. Submit and track Purchase Requests.</p>
            </div>

            <section className="buyer-pr-upload-section">
              <div className="supplier-header">
                <h2>Submit a Purchase Request</h2>
                <p>Upload a signed PR for OCR extraction. BAC Secretariat will review, number, and continue it to supplier matching.</p>
              </div>
              {submittedPrIds.length > 0 && (
                <div className="alert alert-success" role="status">
                  Purchase Request submitted for BAC review. The status viewer below tracks the same database record.
                </div>
              )}
              <DragDropUpload reviewOnly submittedBy={user?.username || ''} onSaved={handlePrSubmitted} />
            </section>
          </div>
        )}

        {currentTab === 'live-status' && (
          <div className="supplier-section">
            <BuyerPRStatusViewer prIds={submittedPrIds} username={user?.username || ''} />
          </div>
        )}
      </div>
    </div>
  )
}

const BUYER_PR_STAGES = [
  { key: 'submitted', label: 'Submitted' },
  { key: 'under_review', label: 'Under BAC Review' },
  { key: 'supplier_matching', label: 'Supplier Matching' },
  { key: 'rfq_sent', label: 'RFQ Sent' },
  { key: 'supplier_response', label: 'Supplier Response' },
  { key: 'completed', label: 'Completed' },
]

const buyerPeso = (value) => {
  const numeric = Number(value ?? 0)
  return `₱${(Number.isFinite(numeric) ? numeric : 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const buyerLongDate = (value) => {
  if (!value) return ''
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? ''
    : parsed.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}

const buyerStatusBadgeClass = (stage) => {
  if (stage === 'rejected') return 'status-merged'
  if (stage === 'completed' || stage === 'supplier_response') return 'status-open'
  return 'status-review'
}

const BUYER_STAGE_LABELS = {
  submitted: 'Submitted',
  under_review: 'Under BAC Review',
  supplier_matching: 'Supplier Matching',
  rfq_sent: 'RFQ Sent',
  supplier_response: 'Supplier Response',
  completed: 'Completed',
  rejected: 'Rejected',
}

// The backend (pr_list) is the source of truth via display_stage. This is only a
// fallback so the timeline still advances if that field is momentarily absent
// (e.g. the API server has not picked up the new response shape yet).
const buyerStageFor = (record) => {
  if (record.display_stage) return record.display_stage
  const status = record.status
  if (status === 'rejected') return 'rejected'
  if (status === 'approved') return 'completed'
  if ((record.rfq_response_count ?? 0) > 0) return 'supplier_response'
  if ((record.rfq_sent_count ?? 0) > 0) return 'rfq_sent'
  if (status === 'matched') return 'supplier_matching'
  if (status === 'in_review') return 'under_review'
  return 'submitted'
}

const BuyerPRTimeline = ({ record }) => {
  const stage = buyerStageFor(record)
  const timestamps = record.stage_timestamps || {}

  if (stage === 'rejected') {
    const nodes = [
      { label: 'Submitted', state: 'done', at: timestamps.submitted },
      { label: 'Under BAC Review', state: 'done' },
      { label: 'Rejected', state: 'rejected' },
    ]
    return (
      <ol className="buyer-timeline" aria-label="Purchase Request progress">
        {nodes.map((node) => (
          <li key={node.label} className={`buyer-timeline-node is-${node.state}`}>
            <span className="buyer-timeline-marker" aria-hidden="true">{node.state === 'rejected' ? '✕' : '✓'}</span>
            <div className="buyer-timeline-body">
              <span className="buyer-timeline-label">{node.label}</span>
              {node.at && <span className="buyer-timeline-time">{buyerLongDate(node.at)}</span>}
            </div>
          </li>
        ))}
      </ol>
    )
  }

  const currentIndex = Math.max(0, BUYER_PR_STAGES.findIndex((item) => item.key === stage))
  return (
    <ol className="buyer-timeline" aria-label="Purchase Request progress">
      {BUYER_PR_STAGES.map((item, index) => {
        const state = index < currentIndex ? 'done' : index === currentIndex ? 'current' : 'upcoming'
        const at = timestamps[item.key]
        return (
          <li key={item.key} className={`buyer-timeline-node is-${state}`}>
            <span className="buyer-timeline-marker" aria-hidden="true">
              {state === 'done' ? '✓' : state === 'current' ? '●' : '○'}
            </span>
            <div className="buyer-timeline-body">
              <span className="buyer-timeline-label">{item.label}</span>
              {at && (state === 'done' || state === 'current') && (
                <span className="buyer-timeline-time">{buyerLongDate(at)}</span>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

const BuyerPRStatusCard = ({ record }) => {
  const [showDetails, setShowDetails] = React.useState(false)
  const stage = buyerStageFor(record)
  const statusLabel = record.display_status || BUYER_STAGE_LABELS[stage] || 'Submitted'

  return (
    <article className="buyer-status-record">
      <div className="buyer-status-record-head">
        <div>
          <strong>{record.pr_no || `Reference #${record.id}`}</strong>
          <span>{record.entity_name || 'Purchase Request'}</span>
        </div>
        <span className={`status-badge ${buyerStatusBadgeClass(stage)}`}>{statusLabel}</span>
      </div>

      <dl className="buyer-status-facts">
        <div>
          <dt>PR Number</dt>
          <dd>
            {record.pr_no
              ? <strong className="buyer-pr-number">{record.pr_no}</strong>
              : <span className="buyer-pr-pending">Awaiting BAC assignment</span>}
          </dd>
        </div>
        {!record.pr_no && (
          <div><dt>Reference</dt><dd>#{record.id}</dd></div>
        )}
        <div><dt>Requesting Office</dt><dd>{record.office_section || record.entity_name || '—'}</dd></div>
        {record.date && <div><dt>PR Date</dt><dd>{buyerLongDate(record.date)}</dd></div>}
        <div><dt>Submitted</dt><dd>{buyerLongDate(record.created_at) || '—'}</dd></div>
        <div><dt>Total</dt><dd>{buyerPeso(record.grand_total)}</dd></div>
        <div>
          <dt>Original Document</dt>
          <dd>
            {record.source_file_url
              ? <a href={record.source_file_url} target="_blank" rel="noreferrer">View submitted document</a>
              : '—'}
          </dd>
        </div>
      </dl>

      <div className="buyer-status-current">
        <span className="buyer-status-current-kicker">Current Status</span>
        <span className="buyer-status-current-value">{statusLabel}</span>
        {record.status_description && <p>{record.status_description}</p>}
      </div>

      <BuyerPRTimeline record={record} />

      <div className="form-actions">
        <button type="button" className="btn-sm btn-secondary" onClick={() => setShowDetails((open) => !open)} aria-expanded={showDetails}>
          {showDetails ? 'Hide Details' : 'View Details'}
        </button>
      </div>

      {showDetails && (
        <div className="buyer-status-details">
          <div className="buyer-status-facts" style={{ border: 'none', padding: 0, margin: 0 }}>
            <div><dt>Requesting Office</dt><dd>{record.office_section || '—'}</dd></div>
            <div><dt>Requested By</dt><dd>{record.requested_by || '—'}</dd></div>
            <div><dt>Category</dt><dd>{record.category || 'Not yet assigned'}</dd></div>
            <div><dt>Line Items</dt><dd>{record.items_count ?? 0}</dd></div>
            <div><dt>RFQs Issued</dt><dd>{record.rfq_sent_count ?? 0}</dd></div>
            <div><dt>Supplier Responses</dt><dd>{record.rfq_response_count ?? 0}</dd></div>
          </div>
          {record.purpose && (
            <div>
              <span className="buyer-status-current-kicker">Purpose</span>
              <p>{record.purpose}</p>
            </div>
          )}
          <p className="supplier-subtext" style={{ margin: 0 }}>
            Supplier selection and evaluation are handled by the BAC Secretariat and are not shown here.
          </p>
        </div>
      )}
    </article>
  )
}

const BuyerPRStatusViewer = ({ prIds, username }) => {
  const [records, setRecords] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  const loadRecords = React.useCallback(async () => {
    if (!prIds.length && !username) return
    setLoading(true)
    setError('')
    try {
      const response = await apiFetch(
        `${apiBaseUrl.replace(/\/$/, '')}/api/pr/list/?submitted_by=${encodeURIComponent(username)}&t=${Date.now()}`,
        { cache: 'no-store' },
      )
      if (!response.ok) throw new Error('Unable to load your Purchase Requests')
      const databaseRecords = await response.json()
      setRecords(Array.isArray(databaseRecords) ? databaseRecords : [])
    } catch (loadError) {
      setError(loadError?.message || 'Unable to load Purchase Request status')
    } finally {
      setLoading(false)
    }
  }, [apiBaseUrl, prIds, username])

  React.useEffect(() => {
    loadRecords()
    const refreshTimer = window.setInterval(loadRecords, 30000)
    return () => window.clearInterval(refreshTimer)
  }, [loadRecords])

  if (!prIds.length && !username) return null

  return (
    <>
      <div className="supplier-header">
        <h1>Live Status</h1>
        <p>Track each Purchase Request you submitted through the procurement workflow.</p>
      </div>
      <section className="buyer-status-viewer dashboard-section">
        <div className="supplier-header">
          <div>
            <span className="section-kicker">Purchase Requests</span>
            <h2>My Purchase Requests</h2>
          </div>
          <button type="button" className="btn-sm btn-secondary" onClick={loadRecords} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        {!error && !loading && records.length === 0 && (
          <div className="empty-state"><ClipboardList size={48} /><h3>No Purchase Requests yet</h3><p>Submitted Purchase Requests will appear here with their live procurement status.</p></div>
        )}
        <div className="buyer-status-list">
          {records.map((record) => <BuyerPRStatusCard key={record.id} record={record} />)}
        </div>
      </section>
    </>
  )
}

const Supplier = () => {
  const navigate = useNavigate()
  const user = React.useMemo(() => getStoredUser(), [])
  const [currentPage, setCurrentPage] = React.useState('dashboard')
  const [navCollapsed, setNavCollapsed] = React.useState(false)
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  const supplierId = user?.supplier_id || authStore.get('supplier_id')
  const supplierStatus = user?.supplier_status || authStore.get('supplier_status') || 'Pending Review'

  const handleLogout = () => {
    apiFetch(`${apiBaseUrl}/api/logout/`, { method: 'POST' }).catch(() => {})
    authStore.clear()
    navigate('/login')
  }

  const handlePageChange = (page) => {
    setCurrentPage(page)
    window.scrollTo(0, 0)
  }

  const normalizedStatus = (supplierStatus || '').toLowerCase().replace(/\s+/g, '-')
  const isApproved = supplierStatus === 'Approved'
  const isCompliance = supplierStatus === 'For Compliance'
  const isPending = supplierStatus === 'Pending Review'
  const isRejected = supplierStatus === 'Rejected'

  if (!supplierId) {
    return (
      <div className="supplier-content-inner">
        <div className="supplier-status-card">
          <h2>Supplier account not linked</h2>
          <p>Your login session is missing a linked supplier profile. Please contact BAC support to restore access.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`admin-layout ${navCollapsed ? 'collapsed-nav' : ''}`}>
      <SupplierNav 
        currentPage={currentPage} 
        onPageChange={handlePageChange} 
        onLogout={handleLogout}
        navCollapsed={navCollapsed}
        onToggleNav={() => setNavCollapsed((v) => !v)}
        supplierId={supplierId}
        apiBaseUrl={apiBaseUrl}
      />
      <div className="admin-content">
        {currentPage === 'dashboard' && <SupplierDashboard supplierId={supplierId} apiBaseUrl={apiBaseUrl} supplierStatus={supplierStatus} />}
        {currentPage === 'opportunities' && (isApproved ? <ProcurementOpportunities supplierId={supplierId} apiBaseUrl={apiBaseUrl} /> : <SupplierAccessStatus status={supplierStatus} isRejected={isRejected} isCompliance={isCompliance} isPending={isPending} />)}
        {currentPage === 'quotations' && (isApproved ? <MyQuotations supplierId={supplierId} apiBaseUrl={apiBaseUrl} /> : <SupplierAccessStatus status={supplierStatus} isRejected={isRejected} isCompliance={isCompliance} isPending={isPending} />)}
        {currentPage === 'rfqs' && (isApproved ? <SupplierRFQs supplierId={supplierId} apiBaseUrl={apiBaseUrl} /> : <SupplierAccessStatus status={supplierStatus} isRejected={isRejected} isCompliance={isCompliance} isPending={isPending} />)}
        {currentPage === 'profile' && <CompanyProfile supplierId={supplierId} apiBaseUrl={apiBaseUrl} />}
        {currentPage === 'notifications' && <SupplierNotifications supplierId={supplierId} apiBaseUrl={apiBaseUrl} />}
      </div>
    </div>
  )
}

const SupplierAccessStatus = ({ status, isRejected, isCompliance, isPending }) => (
  <div className="supplier-content-inner supplier-status-page">
    <div className="supplier-status-card">
      <span className={`status-pill ${isRejected || isCompliance ? 'danger' : isPending ? 'warning' : ''}`}>
        {status}
      </span>
      <h2>{isRejected ? 'Registration was not approved' : isCompliance ? 'Additional documents are required' : 'Your supplier account is still under review'}</h2>
      <p>
        {isRejected
          ? 'Your registration has been rejected. Please contact BAC for guidance on reapplication or document updates.'
          : isCompliance
            ? 'BAC is requesting additional documentation or clarifications before your supplier account can be activated.'
            : 'Your registration is being reviewed by BAC administrators. You will receive updates once the review is complete.'}
      </p>
      <ul>
        <li>Use the dashboard to see your current registration status.</li>
        <li>Review your profile details and uploaded documents.</li>
        <li>Contact BAC if you need to update or resubmit any required information.</li>
      </ul>
    </div>
  </div>
)

const rfqSupplierStatusLabel = (rfq) => rfq?.status_label || ({
  draft: 'Draft',
  sent: 'Awaiting Supplier Response',
  quotation_received: 'Response Submitted',
  completed: 'Completed',
}[rfq?.status] || rfq?.status || 'Unknown')

const SupplierRFQs = ({ supplierId, apiBaseUrl }) => {
  const [rfqs, setRfqs] = React.useState([])
  const [selectedRfqId, setSelectedRfqId] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  const loadRFQs = React.useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/rfqs/`)
      if (!response.ok) throw new Error('Unable to load RFQs')
      const data = await response.json()
      setRfqs(Array.isArray(data.rfqs) ? data.rfqs : [])
    } catch (loadError) {
      setError(loadError.message || 'Unable to load RFQs')
    } finally {
      setLoading(false)
    }
  }, [apiBaseUrl, supplierId])

  React.useEffect(() => { loadRFQs() }, [loadRFQs])

  const selectedRfq = rfqs.find((rfq) => rfq.id === selectedRfqId) || null

  if (selectedRfq) {
    return (
      <SupplierRFQDetail
        rfq={selectedRfq}
        supplierId={supplierId}
        apiBaseUrl={apiBaseUrl}
        onBack={() => setSelectedRfqId(null)}
        onChange={(updated) => setRfqs((current) => current.map((item) => item.id === updated.id ? updated : item))}
      />
    )
  }

  return (
    <div className="supplier-content-inner">
      <div className="supplier-header"><h2>Requests for Quotation</h2><p>Download each RFQ, complete and sign it, then upload the completed document.</p></div>
      {error && <div className="alert alert-error">{error}</div>}
      {loading ? <SkeletonRows count={4} /> : rfqs.length === 0 ? <div className="empty-state"><Send size={48} /><h3>No RFQs received</h3><p>New requests for quotation will appear here.</p></div> : (
        <div className="rfq-supplier-list">
          {rfqs.map((rfq) => {
            const pr = rfq.purchase_request
            const responded = rfq.status === 'quotation_received' || rfq.status === 'completed'
            return (
              <article className="card rfq-supplier-card" key={rfq.id}>
                <div className="rfq-supplier-card-head">
                  <div>
                    <h3>Request for Quotation</h3>
                    <p className="supplier-subtext">{rfq.rfq_no} · PR {pr.pr_no || pr.id}</p>
                  </div>
                  <span className={`status-badge ${responded ? 'status-open' : 'status-review'}`}>{rfqSupplierStatusLabel(rfq)}</span>
                </div>
                <div className="rfq-supplier-card-body">
                  <div><strong>From:</strong> {pr.office_section || pr.entity_name || 'N/A'}</div>
                  <div><strong>Category:</strong> {pr.category || 'N/A'}</div>
                  {rfq.submitted_at && <div><strong>Submitted:</strong> {new Date(rfq.submitted_at).toLocaleString()}</div>}
                </div>
                <div className="form-actions">
                  <button type="button" className="btn-primary" onClick={() => setSelectedRfqId(rfq.id)}>View RFQ</button>
                  {rfq.generated_pdf_url && (
                    <a className="btn-secondary" href={rfq.generated_pdf_url} download target="_blank" rel="noreferrer"><Download size={14} /> Download RFQ</a>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

const SupplierRFQDetail = ({ rfq: initialRfq, supplierId, apiBaseUrl, onBack, onChange }) => {
  const [uploadedRfq, setUploadedRfq] = React.useState(null)
  const [file, setFile] = React.useState(null)
  const [uploading, setUploading] = React.useState(false)
  const [error, setError] = React.useState('')
  const [notice, setNotice] = React.useState('')
  const [replacing, setReplacing] = React.useState(false)

  const rfq = uploadedRfq || initialRfq
  const pr = rfq.purchase_request
  const generatedUrl = rfq.generated_pdf_url || rfq.pdf_url || ''
  const submittedUrl = rfq.submitted_pdf_url || ''
  const hasResponse = Boolean(submittedUrl)
  const responseOpen = rfq.status === 'sent' || rfq.status === 'quotation_received'

  const handleUpload = async () => {
    if (!file) { setError('Choose the completed RFQ PDF first.'); return }
    const check = validateFile(file, UPLOAD_KINDS.COMPLETED_RFQ)
    if (!check.ok) { setError(check.error); return }
    setUploading(true); setError(''); setNotice('')
    try {
      const body = new FormData()
      body.append('file', file)
      const res = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/rfqs/${rfq.id}/response/`, { method: 'POST', body })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.message || data.error || 'Upload failed. Please try again.')
      setUploadedRfq(data)
      setFile(null)
      setReplacing(false)
      setNotice(data.replaced ? 'Completed RFQ replaced successfully.' : 'Completed RFQ uploaded successfully.')
      if (onChange) onChange(data)
    } catch (uploadError) {
      setError(uploadError.message || 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="supplier-content-inner">
      <button type="button" className="back-link" onClick={onBack}><ChevronLeft size={18} /> Back to RFQs</button>
      <div className="supplier-header">
        <h2>Request for Quotation</h2>
        <p>{rfq.rfq_no} · PR {pr.pr_no || pr.id}</p>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="card rfq-review-card">
        <div className="detail-grid">
          <div><strong>RFQ No.: </strong><span>{rfq.rfq_no}</span></div>
          <div><strong>PR No.: </strong><span>{pr.pr_no || `PR-${pr.id}`}</span></div>
          <div><strong>From: </strong><span>{pr.office_section || pr.entity_name || 'N/A'}</span></div>
          <div><strong>Category: </strong><span>{pr.category || 'N/A'}</span></div>
          <div><strong>Status: </strong><span>{rfqSupplierStatusLabel(rfq)}</span></div>
          {rfq.submitted_at && <div><strong>Submitted: </strong><span>{new Date(rfq.submitted_at).toLocaleString()}</span></div>}
        </div>
        <h3>RFQ Message</h3>
        <div className="supplier-readonly-card" style={{ whiteSpace: 'pre-wrap' }}>{rfq.message}</div>
      </div>

      <div className="card rfq-review-card">
        <h3>Requested Items</h3>
        <div className="opportunity-table-wrapper"><table className="opportunity-table">
          <thead><tr><th>Unit</th><th>Description</th><th>Quantity</th><th>Category</th></tr></thead>
          <tbody>{pr.items.map((item) => <tr key={item.id}><td>{item.unit || 'N/A'}</td><td>{item.item_description || 'N/A'}</td><td>{item.quantity}</td><td>{item.category || 'N/A'}</td></tr>)}</tbody>
        </table></div>
      </div>

      <div className="card rfq-review-card">
        <h3>Generated RFQ Document</h3>
        {generatedUrl ? (
          <>
            <p className="supplier-subtext">This document is generated by the BAC and cannot be edited online. Print it, fill in the supplier fields, and sign it.</p>
            <iframe title="RFQ document" src={generatedUrl} style={{ width: '100%', minHeight: 620, border: '1px solid #d1d5db', borderRadius: 8 }} />
          </>
        ) : (
          <p className="supplier-subtext">The RFQ document is not yet available. Please check back shortly.</p>
        )}
      </div>

      <div className="card rfq-review-card">
        <h3>Completed RFQ Submission</h3>
        <ol className="rfq-workflow-steps">
          <li>
            <div><strong>1. Download</strong><span>Download the RFQ PDF.</span></div>
            {generatedUrl && <a className="btn-secondary" href={generatedUrl} download target="_blank" rel="noreferrer"><Download size={14} /> Download RFQ PDF</a>}
          </li>
          <li><div><strong>2. Complete</strong><span>Print the RFQ and fill in the required supplier fields — brand/model, unit prices, total quotation amounts, and contact information.</span></div></li>
          <li><div><strong>3. Sign</strong><span>Sign the completed document.</span></div></li>
          <li><div><strong>4. Submit</strong><span>Scan or photograph it as a single PDF and upload it below.</span></div></li>
        </ol>

        {hasResponse && !replacing ? (
          <div className="rfq-response-confirmed">
            <p className="rfq-response-confirmed-title"><CheckCircle size={18} /> Completed RFQ uploaded successfully</p>
            <div className="detail-grid" style={{ margin: '4px 0 10px' }}>
              <div><strong>RFQ No.: </strong><span>{rfq.rfq_no}</span></div>
              <div><strong>PR No.: </strong><span>{pr.pr_no || `PR-${pr.id}`}</span></div>
              <div><strong>Submitted: </strong><span>{rfq.submitted_at ? new Date(rfq.submitted_at).toLocaleString() : '—'}</span></div>
              {rfq.submitted_filename && <div><strong>File: </strong><span>{rfq.submitted_filename}</span></div>}
              <div><strong>Response Status: </strong><span>{rfqSupplierStatusLabel(rfq)}</span></div>
            </div>
            <div className="form-actions">
              <a className="btn-secondary" href={submittedUrl} target="_blank" rel="noreferrer">View Submitted RFQ</a>
              <a className="btn-secondary" href={submittedUrl} download target="_blank" rel="noreferrer">Download Submitted RFQ</a>
              {responseOpen && <button type="button" className="btn-secondary" onClick={() => { setReplacing(true); setNotice('') }}>Replace Submission</button>}
            </div>
          </div>
        ) : responseOpen ? (
          <div className="rfq-upload-area">
            <label className="form-field">
              <span>Upload Completed RFQ — accepted file type: {acceptedTypesLabel(UPLOAD_KINDS.COMPLETED_RFQ)}, max 10 MB</span>
              <input
                type="file"
                accept={acceptAttr(UPLOAD_KINDS.COMPLETED_RFQ)}
                onChange={(event) => {
                  const picked = event.target.files?.[0] || null
                  if (picked) {
                    const check = validateFile(picked, UPLOAD_KINDS.COMPLETED_RFQ)
                    if (!check.ok) { setFile(null); setError(check.error); event.target.value = ''; return }
                  }
                  setFile(picked); setError('')
                }}
              />
            </label>
            {file && <p className="supplier-subtext">✓ {file.name} · {fileTypeLabel(file)} • {formatFileSize(file.size)}</p>}
            <div className="form-actions">
              {replacing && <button type="button" className="btn-secondary" onClick={() => { setReplacing(false); setFile(null) }} disabled={uploading}>Cancel</button>}
              <button type="button" className="btn-primary" onClick={handleUpload} disabled={uploading || !file}>{uploading ? 'Uploading...' : 'Upload Completed RFQ'}</button>
            </div>
          </div>
        ) : (
          <p className="supplier-subtext">This RFQ is no longer open for a response.</p>
        )}
      </div>
    </div>
  )
}

const SupplierNav = ({ currentPage, onPageChange, onLogout, navCollapsed, onToggleNav, supplierId, apiBaseUrl }) => {
  const [supplierDetails, setSupplierDetails] = React.useState(null)

  React.useEffect(() => {
    if (!supplierId) return

    const fetchSupplierDetails = async () => {
      try {
        const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/profile/`)
        if (!response.ok) return

        const data = await response.json()
        setSupplierDetails(data)
      } catch (error) {
        console.error('Failed to fetch supplier details:', error)
      }
    }

    fetchSupplierDetails()
  }, [supplierId, apiBaseUrl])

  return (
    <Sidebar
      portalLabel="Supplier Portal"
      activeId={currentPage}
      onSelect={onPageChange}
      navCollapsed={navCollapsed}
      onToggleNav={onToggleNav}
      userPrimary={supplierDetails?.company_name || 'Supplier Account'}
      userSecondary={supplierDetails?.email || supplierDetails?.contact_email || 'Portal'}
      onLogout={onLogout}
      groups={[
        { section: 'MAIN', items: [
          { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
        ] },
        { section: 'PROCUREMENT', items: [
          { id: 'opportunities', label: 'Opportunities', icon: BriefcaseBusiness },
          { id: 'rfqs', label: 'RFQs', icon: Send },
          { id: 'quotations', label: 'Quotations', icon: FileText },
        ] },
        { section: 'ACCOUNT', items: [
          { id: 'profile', label: 'Profile', icon: Building2 },
          { id: 'notifications', label: 'Notifications', icon: Bell },
        ] },
      ]}
    />
  )
}

const SupplierDashboard = ({ supplierId, apiBaseUrl, supplierStatus }) => {
  const [summary, setSummary] = React.useState(null)
  const [opportunities, setOpportunities] = React.useState([])
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    const fetchDashboard = async () => {
      try {
        setLoading(true)
        const [summaryRes, opportunitiesRes] = await Promise.all([
          apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/dashboard/`),
          apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/opportunities/`)
        ])

        if (summaryRes.ok) {
          const data = await summaryRes.json()
          setSummary(data)
        }

        if (opportunitiesRes.ok) {
          const data = await opportunitiesRes.json()
          setOpportunities(data.opportunities.slice(0, 3))
        }
      } catch (error) {
        console.error('Failed to fetch dashboard:', error)
      } finally {
        setLoading(false)
      }
    }

    if (supplierId) fetchDashboard()
  }, [supplierId, apiBaseUrl])

  if (loading) return <SkeletonRows count={6} />

  return (
    <div className="supplier-content-inner">
      <div className="supplier-header">
        <h2>Welcome back, {summary?.company_name}</h2>
        <p>Here's a quick overview of your procurement activities.</p>
      </div>

      <div className="supplier-status-card">
        <span className={`status-pill ${supplierStatus === 'Approved' ? 'success' : supplierStatus === 'For Compliance' || supplierStatus === 'Rejected' ? 'danger' : 'warning'}`}>
          {supplierStatus || 'Pending Review'}
        </span>
        <h2>{supplierStatus === 'Approved' ? 'Your supplier account is active' : supplierStatus === 'For Compliance' ? 'BAC needs additional information' : supplierStatus === 'Rejected' ? 'Registration requires action' : 'Your account is under review'}</h2>
        <p>
          {supplierStatus === 'Approved'
            ? 'Your account is active and you can review procurement opportunities, submit quotations, and monitor updates.'
            : supplierStatus === 'For Compliance'
              ? 'Please review BAC comments in your profile and upload any missing or corrected documents.'
              : supplierStatus === 'Rejected'
                ? 'Your registration was not approved. Please contact BAC for next steps.'
                : 'BAC is still reviewing your registration. You will see access unlock once your account is approved.'}
        </p>
      </div>

      <div className="dashboard-cards-grid">
        <div className="dashboard-card-stat">
          <div className="stat-icon" style={{ background: '#dbeafe' }}>
            <BriefcaseBusiness size={24} color="#0284c7" />
          </div>
          <div>
            <div className="stat-value">{summary?.open_opportunities || 0}</div>
            <div className="stat-label">Matching Opportunities</div>
          </div>
        </div>

        <div className="dashboard-card-stat">
          <div className="stat-icon" style={{ background: '#e9d5ff' }}>
            <FileText size={24} color="#7c3aed" />
          </div>
          <div>
            <div className="stat-value">{summary?.submitted_quotations || 0}</div>
            <div className="stat-label">Quotations Submitted</div>
          </div>
        </div>

        <div className="dashboard-card-stat">
          <div className="stat-icon" style={{ background: '#fed7aa' }}>
            <Clock size={24} color="#ea580c" />
          </div>
          <div>
            <div className="stat-value">{summary?.pending_quotations || 0}</div>
            <div className="stat-label">Under Review</div>
          </div>
        </div>

        <div className="dashboard-card-stat">
          <div className="stat-icon" style={{ background: '#fecaca' }}>
            <AlertCircle size={24} color="#dc2626" />
          </div>
          <div>
            <div className="stat-value">{summary?.rejected_quotations || 0}</div>
            <div className="stat-label">Not Selected</div>
          </div>
        </div>

        <div className="dashboard-card-stat">
          <div className="stat-icon" style={{ background: '#e9d5ff' }}>
            <CheckCircle size={24} color="#7c3aed" />
          </div>
          <div>
            <div className="stat-value approval-status-value">{summary?.verification_status || 'Pending'}</div>
            <div className="stat-label">Approval Status</div>
          </div>
        </div>
      </div>

      {opportunities.length > 0 && (
        <div className="supplier-section">
          <h3>Recent Matching Opportunities</h3>
          <div className="opportunities-grid">
            {opportunities.map((opp) => (
              <div key={opp.id} className="opportunity-card">
                <div className="opportunity-header">
                  <h4>{opp.pr_no}</h4>
                  <span className={`status-badge status-${opp.status}`}>{opp.status}</span>
                </div>
                <p className="opportunity-office">{opp.office_section}</p>
                <p className="opportunity-purpose">{opp.purpose}</p>
                <div className="opportunity-footer">
                  <div><strong>Budget:</strong> ₱{opp.grand_total.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
                  <div><strong>Category:</strong> {opp.category}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const ProcurementOpportunities = ({ supplierId, apiBaseUrl }) => {
  const navigate = useNavigate()
  const [opportunities, setOpportunities] = React.useState([])
  const [filteredOpportunities, setFilteredOpportunities] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [searchTerm, setSearchTerm] = React.useState('')
  const [selectedOpp, setSelectedOpp] = React.useState(null)

  React.useEffect(() => {
    const fetchOpportunities = async () => {
      try {
        setLoading(true)
        const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/opportunities/`)
        if (response.ok) {
          const data = await response.json()
          setOpportunities(data.opportunities)
          setFilteredOpportunities(data.opportunities)
        }
      } catch (error) {
        console.error('Failed to fetch opportunities:', error)
      } finally {
        setLoading(false)
      }
    }

    if (supplierId) fetchOpportunities()
  }, [supplierId, apiBaseUrl])

  const handleSearch = (term) => {
    setSearchTerm(term)
    const filtered = opportunities.filter(
      (opp) =>
        opp.pr_no.toLowerCase().includes(term.toLowerCase()) ||
        opp.entity_name.toLowerCase().includes(term.toLowerCase()) ||
        opp.purpose?.toLowerCase().includes(term.toLowerCase())
    )
    setFilteredOpportunities(filtered)
  }

  if (loading) return <SkeletonRows count={5} />

  if (selectedOpp) {
    return <OpportunityDetail opportunity={selectedOpp} onBack={() => setSelectedOpp(null)} apiBaseUrl={apiBaseUrl} />
  }

  return (
    <div className="supplier-content-inner">
      <div className="supplier-header">
        <h2>Procurement Opportunities</h2>
        <p>Explore purchase requests matching your registered services</p>
      </div>

      <div className="supplier-search-bar">
        <Search size={18} />
        <input
          type="text"
          placeholder="Search by PR number, office, or purpose..."
          value={searchTerm}
          onChange={(e) => handleSearch(e.target.value)}
        />
      </div>

      {filteredOpportunities.length > 0 ? (
        <div className="opportunities-table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th>PR Number</th>
                <th>Office</th>
                <th>Purpose</th>
                <th>Category</th>
                <th>Budget</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredOpportunities.map((opp) => (
                <tr key={opp.id}>
                  <td><strong>{opp.pr_no}</strong></td>
                  <td>{opp.office_section}</td>
                  <td>{opp.purpose}</td>
                  <td>{opp.category}</td>
                  <td>₱{opp.grand_total.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                  <td>
                    <span className={`status-badge status-${opp.status}`}>{opp.status}</span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="action-link"
                      onClick={() => setSelectedOpp(opp)}
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <BriefcaseBusiness size={48} />
          <h3>No matching opportunities</h3>
          <p>Check back later or update your company profile to see more opportunities.</p>
        </div>
      )}
    </div>
  )
}

const OpportunityDetail = ({ opportunity, onBack, apiBaseUrl }) => {
  const [prDetails, setPrDetails] = React.useState(null)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    const fetchDetails = async () => {
      try {
        const response = await apiFetch(`${apiBaseUrl}/api/pr/${opportunity.id}/details/`)
        if (response.ok) {
          const data = await response.json()
          setPrDetails(data)
        }
      } catch (error) {
        console.error('Failed to fetch PR details:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchDetails()
  }, [opportunity.id, apiBaseUrl])

  if (loading) return <SkeletonRows count={4} />

  return (
    <div className="supplier-content-inner">
      <button type="button" className="back-link" onClick={onBack}>
        <ChevronLeft size={18} /> Back to Opportunities
      </button>

      <div className="supplier-header">
        <h2>{prDetails?.pr_no}</h2>
        <p>{prDetails?.purpose}</p>
      </div>

      <div className="details-grid">
        <div className="detail-card">
          <h3>Purchase Request Details</h3>
          <div className="detail-row">
            <label>PR Number:</label>
            <span>{prDetails?.pr_no}</span>
          </div>
          <div className="detail-row">
            <label>Office/Entity:</label>
            <span>{prDetails?.entity_name}</span>
          </div>
          <div className="detail-row">
            <label>Purpose:</label>
            <span>{prDetails?.purpose}</span>
          </div>
          <div className="detail-row">
            <label>Category:</label>
            <span>{prDetails?.category}</span>
          </div>
          <div className="detail-row">
            <label>Grand Total:</label>
            <span>₱{(prDetails?.grand_total || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="detail-row">
            <label>Status:</label>
            <span className={`status-badge status-${prDetails?.status}`}>{prDetails?.status}</span>
          </div>
        </div>

        <div className="detail-card">
          <h3>Line Items</h3>
          {prDetails?.items && prDetails.items.length > 0 ? (
            <div className="items-table-container">
              <table className="admin-table items-table">
                <thead>
                  <tr>
                    <th>Description</th>
                    <th>Qty</th>
                    <th>Unit Cost</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {prDetails.items.map((item, idx) => (
                    <tr key={idx}>
                      <td>{item.item_description}</td>
                      <td>{item.quantity} {item.unit}</td>
                      <td>₱{item.unit_cost.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                      <td>₱{item.total_cost.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>No items available</p>
          )}
        </div>
      </div>

      <div className="detail-card">
        <p className="supplier-subtext">
          To respond to this opportunity, wait for the RFQ from the BAC and submit your quotation from the{' '}
          <strong>RFQs</strong> tab.
        </p>
      </div>
    </div>
  )
}

const MyQuotations = ({ supplierId, apiBaseUrl }) => {
  const [quotations, setQuotations] = React.useState([])
  const [filteredQuotations, setFilteredQuotations] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [searchTerm, setSearchTerm] = React.useState('')

  React.useEffect(() => {
    const fetchQuotations = async () => {
      try {
        setLoading(true)
        const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/quotations/`)
        if (response.ok) {
          const data = await response.json()
          setQuotations(data.quotations)
          setFilteredQuotations(data.quotations)
        }
      } catch (error) {
        console.error('Failed to fetch quotations:', error)
      } finally {
        setLoading(false)
      }
    }

    if (supplierId) fetchQuotations()
  }, [supplierId, apiBaseUrl])

  const handleSearch = (term) => {
    setSearchTerm(term)
    const filtered = quotations.filter(
      (q) =>
        q.pr_no.toLowerCase().includes(term.toLowerCase()) ||
        q.status.toLowerCase().includes(term.toLowerCase())
    )
    setFilteredQuotations(filtered)
  }

  if (loading) return <SkeletonRows count={5} />

  return (
    <div className="supplier-content-inner">
      <div className="supplier-header">
        <h2>My Quotations</h2>
        <p>Track the status of all your submitted quotations.</p>
      </div>

      <div className="supplier-search-bar">
        <Search size={18} />
        <input
          type="text"
          placeholder="Search by PR number or status..."
          value={searchTerm}
          onChange={(e) => handleSearch(e.target.value)}
        />
      </div>

      {filteredQuotations.length > 0 ? (
        <div className="quotations-table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th>PR Number</th>
                <th>Date Submitted</th>
                <th>Quoted Amount</th>
                <th>Est. Delivery</th>
                <th>Warranty</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredQuotations.map((q) => (
                <tr key={q.id}>
                  <td><strong>{q.pr_no}</strong></td>
                  <td>{new Date(q.created_at).toLocaleDateString()}</td>
                  <td>₱{q.quoted_amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                  <td>{q.estimated_delivery_days ? `${q.estimated_delivery_days} days` : '—'}</td>
                  <td>{q.warranty_months ? `${q.warranty_months} months` : '—'}</td>
                  <td>
                    <span className={`status-badge status-${q.status}`}>
                      {q.status.replace('_', ' ')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <FileText size={48} />
          <h3>No quotations yet</h3>
          <p>Submit your first quotation from Procurement Opportunities.</p>
        </div>
      )}
    </div>
  )
}

const CategorySelector = ({ categories, selectedCategories, onChange }) => {
  const selectedIds = new Set(selectedCategories.map((category) => category.id))

  const toggleCategory = (category) => {
    onChange(selectedIds.has(category.id)
      ? selectedCategories.filter((current) => current.id !== category.id)
      : [...selectedCategories, category])
  }

  return (
    <div className="profile-category-selector">
      <label>Supplier Categories</label>
      <p className="supplier-subtext">Select the products or services your company provides.</p>
      <div className="profile-category-options">
        {categories.length > 0 ? categories.map((category) => (
          <label key={category.id} className="profile-category-option">
            <input type="checkbox" checked={selectedIds.has(category.id)} onChange={() => toggleCategory(category)} />
            <span>{category.name}</span>
          </label>
        )) : <span className="supplier-subtext">No active categories available.</span>}
      </div>
    </div>
  )
}

const getSupplierDocumentLabel = (docType) => ({
  mayor_permit: "Mayor's Permit",
  business_permit: 'Business Permit',
  philgeps_registration: 'PhilGEPS Registration',
  bir_registration: 'BIR Registration',
  tax_clearance: 'Tax Clearance',
  dti_registration: 'DTI Registration',
  sec_registration: 'SEC Registration',
  cda_registration: 'CDA Registration',
  other_eligibility: 'Other Eligibility Requirement',
  other_eligibility_requirement: 'Other Eligibility Requirement',
}[docType] || String(docType || 'Supplier Document').replace(/_/g, ' '))

const getSupplierDocumentStatusMeta = (status) => {
  if (status === 'Verified') return { label: 'Verified', className: 'status-open' }
  if (status === 'Rejected') return { label: 'Rejected', className: 'status-merged' }
  return { label: 'Pending Re-evaluation', className: 'status-review' }
}

const CompanyProfile = ({ supplierId, apiBaseUrl }) => {
  const [profile, setProfile] = React.useState(null)
  const [categories, setCategories] = React.useState([])
  const [selectedCategories, setSelectedCategories] = React.useState([])
  const [editMode, setEditMode] = React.useState(false)
  const [formData, setFormData] = React.useState({})
  const [saving, setSaving] = React.useState(false)
  const [message, setMessage] = React.useState(null)
  const [showResubmitDocuments, setShowResubmitDocuments] = React.useState(false)
  const [resubmitFiles, setResubmitFiles] = React.useState({})
  const [resubmitting, setResubmitting] = React.useState('')
  const [resubmitConfirm, setResubmitConfirm] = React.useState(null)

  React.useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/profile/`)
        if (response.ok) {
          const data = await response.json()
          setProfile(data)
          setFormData(data)
          const categoriesResponse = await apiFetch(`${apiBaseUrl}/api/categories/`)
          const availableCategories = categoriesResponse.ok ? await categoriesResponse.json() : []
          setCategories(Array.isArray(availableCategories) ? availableCategories : [])
          const selectedIds = new Set(data.category_ids || [])
          setSelectedCategories((Array.isArray(availableCategories) ? availableCategories : []).filter((category) => selectedIds.has(category.id)))
        }
      } catch (error) {
        console.error('Failed to fetch profile:', error)
      }
    }

    if (supplierId) fetchProfile()
  }, [supplierId, apiBaseUrl])

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)

    try {
      const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/profile/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...formData, category_ids: selectedCategories.map((category) => category.id) }),
      })

      if (response.ok) {
        const data = await response.json()
        setProfile(data.supplier)
        setFormData((current) => ({ ...current, ...data.supplier }))
        setEditMode(false)
        setMessage({ type: 'success', text: 'Profile updated successfully!' })
        setTimeout(() => setMessage(null), 3000)
      } else {
        setMessage({ type: 'error', text: 'Failed to update profile' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'An error occurred' })
    } finally {
      setSaving(false)
    }
  }

  const handleResubmit = async (docType) => {
    const file = resubmitFiles[docType]
    if (!file) return
    const check = validateFile(file, UPLOAD_KINDS.SUPPLIER_REQUIREMENT)
    if (!check.ok) {
      setMessage({ type: 'error', text: `${file.name}: ${check.error}` })
      return
    }
    setResubmitting(docType)
    setMessage(null)
    try {
      const body = new FormData()
      body.append('doc_type', docType)
      body.append('file', file)
      const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/documents/resubmit/`, { method: 'POST', body })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.error || 'Unable to resubmit document')
      setProfile((current) => ({
        ...current,
        status: data.supplier_status || 'Pending Review',
        documents: [data.document, ...(current.documents || [])],
      }))
      authStore.set('supplier_status', data.supplier_status || 'Pending Review')
      setResubmitFiles((current) => ({ ...current, [docType]: null }))
      setMessage({ type: 'success', text: 'Document resubmitted. Your supplier status is now Pending Review.' })
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setResubmitting('')
    }
  }

  if (!profile) return <SkeletonRows count={5} />

  return (
    <div className="supplier-content-inner">
      <div className="supplier-header">
        <h2>Company Profile</h2>
        <p>View and manage your company information.</p>
      </div>

      {message && (
        <div className={`message-banner message-${message.type}`}>
          {message.text}
        </div>
      )}

      {!editMode ? (
        <div className="profile-view">
          <div className="profile-card">
            <h3>{profile.company_name}</h3>
            <div className="profile-row">
              <label>Business Type:</label>
              <span>{profile.business_type}</span>
            </div>
            <div className="profile-row">
              <label>Address:</label>
              <span>{profile.business_address}</span>
            </div>
            <div className="profile-row">
              <label>Email:</label>
              <span>{profile.email}</span>
            </div>
            <div className="profile-row">
              <label>Phone:</label>
              <span>{profile.contact_phone}</span>
            </div>
            <div className="profile-row">
              <label>Contact Person:</label>
              <span>{profile.contact_person}</span>
            </div>
            <div className="profile-row">
              <label>Nature of Business:</label>
              <span>{profile.nature_of_business}</span>
            </div>
            <div className="profile-row">
              <label>Goods/Services:</label>
              <span>{profile.goods_services}</span>
            </div>
            <div className="profile-row">
              <label>Verification Status:</label>
              <span className={`status-badge status-${profile.status.toLowerCase()}`}>
                {profile.status}
              </span>
            </div>

            <div className="profile-card" style={{ marginTop: '1rem' }}>
              <h3>Onboarding progress</h3>
              <p>
                {profile.status === 'Approved'
                  ? 'Your supplier account is active and ready for procurement activity.'
                  : profile.status === 'For Compliance'
                    ? 'BAC has requested updates or missing documents. Review the remarks below and resubmit the required materials.'
                    : profile.status === 'Rejected'
                      ? 'Your registration needs attention before it can be approved.'
                      : 'Your registration is still being reviewed by BAC.'}
              </p>
              {profile.review_remarks ? (
                <div className="message-banner message-error" style={{ marginTop: '0.75rem' }}>
                  <strong>BAC remarks:</strong> {profile.review_remarks}
                </div>
              ) : (
                <p style={{ marginTop: '0.75rem', color: '#475569' }}>No BAC remarks yet. You will see follow-up instructions here after review.</p>
              )}
            </div>

            <div className="profile-action-row">
              <button type="button" className="btn btn-primary profile-edit-btn" onClick={() => setEditMode(true)} aria-label="Edit supplier profile">
                <Edit2 size={16} /> Edit Profile
              </button>
              {profile.status === 'For Compliance' && (
                <button type="button" className="btn btn-secondary profile-edit-btn" onClick={() => setShowResubmitDocuments(true)}>
                  <FileText size={16} /> Resubmit Documents
                </button>
              )}
            </div>
            {profile.status === 'For Compliance' && showResubmitDocuments && (
              <div className="supplier-preview-overlay" role="dialog" aria-modal="true" onClick={() => setShowResubmitDocuments(false)}>
              <section className="supplier-preview-modal profile-resubmit-card" onClick={(event) => event.stopPropagation()}>
                <div className="supplier-preview-header"><div><h3>Resubmit Documents</h3><p className="supplier-subtext">Upload corrected or requested documents for BAC review.</p></div><button type="button" className="icon-action-btn" onClick={() => setShowResubmitDocuments(false)} aria-label="Close resubmit documents">×</button></div>
                <div className="profile-resubmit-list">
                  {(profile.documents || []).reduce((documents, document) => documents.some((item) => item.doc_type === document.doc_type) ? documents : [...documents, document], []).map((document) => (
                    <div className="profile-resubmit-row" key={document.doc_type}>
                      <div>
                        <strong>{getSupplierDocumentLabel(document.doc_type)}</strong>
                        <small className={`status-badge profile-resubmit-status ${getSupplierDocumentStatusMeta(document.verification_status).className}`}>
                          {getSupplierDocumentStatusMeta(document.verification_status).label}
                        </small>
                      </div>
                      {document.verification_status === 'Verified' ? (
                        <span className="profile-document-verified">Document verified by BAC</span>
                      ) : (
                        <>
                          <input type="file" accept={acceptAttr(UPLOAD_KINDS.SUPPLIER_REQUIREMENT)} onChange={(event) => {
                            const picked = event.target.files?.[0] || null
                            if (picked) {
                              const check = validateFile(picked, UPLOAD_KINDS.SUPPLIER_REQUIREMENT)
                              if (!check.ok) { setMessage({ type: 'error', text: `${picked.name}: ${check.error}` }); event.target.value = ''; return }
                            }
                            setResubmitFiles((current) => ({ ...current, [document.doc_type]: picked }))
                          }} />
              <button type="button" className="btn-sm btn-primary" onClick={() => setResubmitConfirm({ docType: document.doc_type, fileName: resubmitFiles[document.doc_type]?.name })} disabled={!resubmitFiles[document.doc_type] || resubmitting === document.doc_type}>{resubmitting === document.doc_type ? 'Submitting...' : 'Resubmit'}</button>
                        </>
                      )}
                    </div>
                  ))}
                </div>
      </section>
              </div>
            )}
          </div>
        </div>
      ) : (
        <form className="profile-form" onSubmit={handleSave}>
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="company_name">Company Name</label>
              <input
                type="text"
                id="company_name"
                value={formData.company_name || ''}
                onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="business_type">Business Type</label>
              <input
                type="text"
                id="business_type"
                value={formData.business_type || ''}
                onChange={(e) => setFormData({ ...formData, business_type: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="tin">TIN Number</label>
              <input
                type="text"
                id="tin"
                value={formData.tin || ''}
                onChange={(e) => setFormData({ ...formData, tin: e.target.value })}
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="business_address">Address</label>
              <textarea
                id="business_address"
                rows="3"
                value={formData.business_address || ''}
                onChange={(e) => setFormData({ ...formData, business_address: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                value={formData.email || ''}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="contact_phone">Phone</label>
              <input
                type="tel"
                id="contact_phone"
                value={formData.contact_phone || ''}
                onChange={(e) => setFormData({ ...formData, contact_phone: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="contact_person">Contact Person</label>
              <input
                type="text"
                id="contact_person"
                value={formData.contact_person || ''}
                onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="nature_of_business">Nature of Business</label>
              <input
                type="text"
                id="nature_of_business"
                value={formData.nature_of_business || ''}
                onChange={(e) => setFormData({ ...formData, nature_of_business: e.target.value })}
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="goods_services">Goods/Services</label>
              <textarea
                id="goods_services"
                rows="3"
                value={formData.goods_services || ''}
                onChange={(e) => setFormData({ ...formData, goods_services: e.target.value })}
              />
            </div>

            <div className="form-group full-width">
              <CategorySelector categories={categories} selectedCategories={selectedCategories} onChange={setSelectedCategories} />
            </div>
          </div>

          <div className="form-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setEditMode(false)
                setFormData(profile)
              }}
              disabled={saving}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      )}
      {resubmitConfirm && (
        <div className="modal-overlay resubmit-confirm-overlay" role="dialog" aria-modal="true" onClick={() => setResubmitConfirm(null)}>
          <div className="modal-content delete-confirm-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header"><h3>Confirm Document Resubmission</h3><button type="button" className="modal-close" onClick={() => setResubmitConfirm(null)}>×</button></div>
            <div className="modal-body"><p>Resubmit <strong>{getSupplierDocumentLabel(resubmitConfirm.docType)}</strong> for BAC verification?</p><p className="helper-text">File: {resubmitConfirm.fileName}</p></div>
            <div className="modal-actions"><button type="button" className="btn btn-secondary" onClick={() => setResubmitConfirm(null)}>Cancel</button><button type="button" className="btn btn-primary" onClick={() => { handleResubmit(resubmitConfirm.docType); setResubmitConfirm(null) }}>Confirm Resubmit</button></div>
          </div>
        </div>
      )}
    </div>
  )
}

const SupplierNotifications = ({ supplierId, apiBaseUrl }) => {
  const [notifications, setNotifications] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [selectedRfq, setSelectedRfq] = React.useState(null)

  React.useEffect(() => {
    const fetchNotifications = async () => {
      try {
        setLoading(true)
        const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/notifications/`)
        if (response.ok) {
          const data = await response.json()
          setNotifications(data.notifications)
        }
      } catch (error) {
        console.error('Failed to fetch notifications:', error)
      } finally {
        setLoading(false)
      }
    }

    if (supplierId) fetchNotifications()
  }, [supplierId, apiBaseUrl])

  if (loading) return <SkeletonRows count={5} />

  if (selectedRfq) {
    return <SupplierRFQDetail rfq={selectedRfq} supplierId={supplierId} apiBaseUrl={apiBaseUrl} onBack={() => setSelectedRfq(null)} />
  }

  const today = new Date()
  const groupedNotifications = notifications.reduce((groups, notif) => {
    const created = new Date(notif.created_at)
    const isToday = created.toDateString() === today.toDateString()
    const bucket = isToday ? 'Today' : 'Earlier'
    groups[bucket] = groups[bucket] || []
    groups[bucket].push(notif)
    return groups
  }, {})

  return (
    <div className="supplier-content-inner">
      <div className="supplier-header">
        <h2>Notifications</h2>
        <p>Stay updated on your quotations and procurement opportunities.</p>
      </div>

      {notifications.length > 0 ? (
        <div className="notifications-list">
          {Object.entries(groupedNotifications).map(([bucket, items]) => (
            <div key={bucket} className="notifications-group">
              <span className="admin-nav-section-label notifications-group-label">{bucket}</span>
              {items.map((notif) => (
                <div key={notif.id} className={`notification-item notification-${notif.type}`}>
                  <div className="notification-icon">
                    {notif.type === 'opportunity' && <BriefcaseBusiness size={20} />}
                    {notif.type === 'rfq_received' && <Send size={20} />}
                    {notif.type === 'quotation_submitted' && <CheckCircle size={20} />}
                    {notif.type === 'quotation_review' && <Clock size={20} />}
                    {notif.type === 'quotation_awarded' && <CheckCircle size={20} />}
                    {notif.type === 'quotation_rejected' && <AlertCircle size={20} />}
                    {notif.type === 'profile_approved' && <CheckCircle size={20} />}
                  </div>
                  <div className="notification-content">
                    <h4>{notif.title}</h4>
                    <p>{notif.message}</p>
                    <span className="notification-time">
                      {new Date(notif.created_at).toLocaleDateString()}
                    </span>
                    {notif.related_rfq_id && (
                      <button
                        type="button"
                        className="btn-sm btn-primary"
                        onClick={async () => {
                          const response = await apiFetch(`${apiBaseUrl}/api/suppliers/${supplierId}/rfqs/`)
                          if (response.ok) {
                            const data = await response.json()
                            setSelectedRfq((data.rfqs || []).find((rfq) => rfq.id === notif.related_rfq_id) || null)
                          }
                        }}
                      >
                        View RFQ
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <Bell size={48} />
          <h3>No notifications</h3>
          <p>You'll receive notifications about quotations and opportunities here.</p>
        </div>
      )}
    </div>
  )
}


const getStoredUser = () => {
  try {
    const stored = authStore.get('eProcureUser')
    if (!stored) return null

    const parsed = JSON.parse(stored)
    if (!parsed || typeof parsed !== 'object' || typeof parsed.role !== 'string' || typeof parsed.username !== 'string') {
      authStore.clear()
      return null
    }

    return parsed
  } catch (error) {
    console.warn('Clearing malformed stored user:', error)
    authStore.clear()
    return null
  }
}

const ProtectedRoute = ({ element, requiredRole }) => {
  const location = useLocation()
  const user = React.useMemo(() => getStoredUser(), [])

  if (!user || (requiredRole && user.role !== requiredRole)) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  return element
}

const AppLayout = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const [user, setUser] = React.useState(getStoredUser())
  const showMainNavbar = !location.pathname.startsWith('/admin') && location.pathname !== '/supplier' && location.pathname !== '/buyer'
  const homeLink = user?.role === 'buyer' ? '/buyer' : '/'

  React.useEffect(() => {
    setUser(getStoredUser())
  }, [location.pathname])

  React.useEffect(() => {
    const syncUser = () => setUser(getStoredUser())
    window.addEventListener('storage', syncUser)
    window.addEventListener('focus', syncUser)
    return () => {
      window.removeEventListener('storage', syncUser)
      window.removeEventListener('focus', syncUser)
    }
  }, [])

  return (
    <div className="app">
      {showMainNavbar && (
        <nav className="navbar">
          <div className="navbar-left navbar-brand-row">
            <Link to="/" className="navbar-logo-link">
              <img src={logo} alt="eProcure logo" className="navbar-logo" />
            </Link>
            <Link to="/" className="public-wordmark" aria-label="eProcure home">
              <strong>eProcure</strong>
              <span>Procurement Operations</span>
            </Link>
            <div className="navbar-links">
              <Link to={homeLink} className={`nav-item ${location.pathname === homeLink || (homeLink === '/' && location.pathname === '/') ? 'active' : ''}`}><House size={15} /> Home</Link>
              <Link to="/faq" className={`nav-item ${location.pathname === '/faq' ? 'active' : ''}`}><HelpCircle size={15} /> Help & FAQ</Link>
            </div>
          </div>

          <div className="navbar-right">
            {user ? (
              <button
                type="button"
                className="login-link"
                onClick={() => {
                  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
                  apiFetch(`${apiBaseUrl}/api/logout/`, { method: 'POST' }).catch(() => {})
                  authStore.clear()
                  setUser(null)
                  navigate('/login')
                }}
              >
                <LogOut size={15} />
                Log Out
              </button>
            ) : (
              <Link to="/login" className="login-link"><LogIn size={15} /> Log In</Link>
            )}
          </div>
        </nav>
      )}

      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/faq" element={<FAQ />} />
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/register" element={<Register />} />
          <Route path="/buyer" element={<ProtectedRoute requiredRole="buyer" element={<Buyer />} />} />
          <Route path="/supplier" element={<ProtectedRoute requiredRole="supplier" element={<Supplier />} />} />
          <Route path="/supplier/register" element={<SupplierRegistration />} />
          <Route path="/admin" element={<ProtectedRoute requiredRole="admin" element={<Admin />} />} />
        </Routes>
      </main>
      {!user && <Footer />}
    </div>
  )
}

const App = () => (
  <BrowserRouter>
    <AppLayout />
  </BrowserRouter>
)

export default App

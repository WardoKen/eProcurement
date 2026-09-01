import React from 'react'
import { BrowserRouter, Routes, Route, Link, Navigate, useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import {
  Check,
  Eye,
  BriefcaseBusiness,
  Pencil,
  CircleHelp,
  ClipboardList,
  House,
  LayoutDashboard,
  LogIn,
  LogOut,
  Menu,
  ChevronLeft,
  RefreshCw,
  ScanSearch,
  Search,
  Trash2,
  UploadCloud,
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
  Send,
  Settings,
  Building2,
  HelpCircle,
} from 'lucide-react'
import logo from './assets/logo.png'
import DragDropUpload from './components/DragDropUpload'
import SupplierRegistration from './components/SupplierRegistration'
import './index.css'

const SkeletonRows = ({ count = 4 }) => (
  <div className="skeleton-stack" aria-label="Loading content">
    {Array.from({ length: count }, (_, index) => (
      <div key={`skeleton-${index}`} className="skeleton-line" />
    ))}
  </div>
)

const verifyRecaptchaToken = async (token) => {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  if (!token) return false

  const response = await fetch(`${apiBaseUrl}/api/verify-recaptcha`, {
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

const bacNewsSlides = [
  {
    title: 'Register and manage supplier documents',
    description: 'Upload permits, BIR, and PhilGEPS requirements while keeping your supplier profile current.',
    buttonLabel: 'Register as Supplier',
    buttonTo: '/supplier/register',
    image: 'https://images.unsplash.com/photo-1517048676732-d65bc937f952?auto=format&fit=crop&w=1200&q=80',
  },
  {
    title: 'Track procurement progress and BAC updates',
    description: 'Stay informed with submission deadlines, review progress, and committee announcements.',
    buttonLabel: 'Go to Tracking',
    buttonTo: '/tracking',
    image: 'https://images.unsplash.com/photo-1520607162513-77705c0f0d4a?auto=format&fit=crop&w=1200&q=80',
  },
]

const BACNewsSlider = () => {
  const [activeIndex, setActiveIndex] = React.useState(0)

  React.useEffect(() => {
    const interval = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % bacNewsSlides.length)
    }, 5000)

    return () => window.clearInterval(interval)
  }, [])

  const showNextSlide = () => {
    setActiveIndex((current) => (current + 1) % bacNewsSlides.length)
  }

  const showPreviousSlide = () => {
    setActiveIndex((current) => (current - 1 + bacNewsSlides.length) % bacNewsSlides.length)
  }

  return (
    <section className="bac-news-slider-section">
      <div className="bac-news-slider-header">
        <div>
          <p className="eyebrow">Main features</p>
          <h2>Everything you need for BAC procurement</h2>
        </div>
        <div className="bac-news-nav" aria-label="News slider controls">
          <button type="button" className="bac-news-nav-button" onClick={showPreviousSlide} aria-label="Show previous news item">
            ←
          </button>
          <button type="button" className="bac-news-nav-button" onClick={showNextSlide} aria-label="Show next news item">
            →
          </button>
        </div>
      </div>

      <div className="bac-news-slider">
        {bacNewsSlides.map((slide, index) => (
          <div
            key={slide.title}
            className={`bac-news-slide ${index === activeIndex ? 'active' : ''}`}
            style={{ backgroundImage: `linear-gradient(90deg, rgba(15,23,42,0.9) 0%, rgba(15,23,42,0.4) 60%, rgba(15,23,42,0.2) 100%), url(${slide.image})` }}
          >
            <div className="bac-news-slide-content">
              <h3>{slide.title}</h3>
              <p>{slide.description}</p>
              <Link to={slide.buttonTo} className="btn-primary">{slide.buttonLabel}</Link>
            </div>
          </div>
        ))}
      </div>

      <div className="bac-news-dots" aria-label="Select news slide">
        {bacNewsSlides.map((slide, index) => (
          <button
            key={slide.title}
            type="button"
            className={`bac-news-dot ${index === activeIndex ? 'active' : ''}`}
            onClick={() => setActiveIndex(index)}
            aria-label={`Show slide ${index + 1}`}
          />
        ))}
      </div>
    </section>
  )
}

const Home = () => (
  <div className="page-content home-page">
    <BACNewsSlider />

    <div className="home-main-grid">
      <div className="home-announcements">
        <section className="home-cards">
          <div className="info-card">
            <h2>What BAC members can do</h2>
            <ul>
              <li>Review supplier documents and compliance records</li>
              <li>Monitor active procurement processes</li>
              <li>Approve or reject supplier credentials</li>
            </ul>
          </div>
          <div className="info-card">
            <h2>What suppliers can do</h2>
            <ul>
              <li>Register for university supplier status</li>
              <li>Upload official permits, BIR, and PhilGEPS documents</li>
              <li>Track bid invitations and submission deadlines</li>
            </ul>
          </div>
        </section>

        <section className="home-notices">
          <h2>Recent BAC updates</h2>
          <ul>
            <li>New supplier registration deadline for FY 2026 procurement cycle.</li>
            <li>Reminder: all service providers must upload updated BIR and PhilGEPS certificates.</li>
            <li>Upcoming BAC meeting to review campus renovation bids on July 3.</li>
          </ul>
        </section>
      </div>

      <section className="home-process">
        <h2>State University BAC Process</h2>
        <div className="process-steps">
          <div className="process-step">
            <h3>1. Post requirements</h3>
            <p>Publish bid opportunities and clear documentation requirements for each project.</p>
          </div>
          <div className="process-step">
            <h3>2. Register suppliers</h3>
            <p>Collect supplier credentials and verify compliance with university procurement policies.</p>
          </div>
          <div className="process-step">
            <h3>3. Evaluate submissions</h3>
            <p>Compare supplier bids, check documents, and prepare recommendations for BAC approval.</p>
          </div>
          <div className="process-step">
            <h3>4. Award contracts</h3>
            <p>Finalize award notices, issue purchase orders, and track contract fulfillment.</p>
          </div>
        </div>
      </section>
    </div>
  </div>
)

const Footer = () => (
  <footer className="site-footer">
    <div className="site-footer-inner">
      <div className="footer-left">
        <img src={logo} alt="logo" className="footer-logo" />
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
            <li>📞 +63 994 842 5992</li>
            <li>✉️ bereberhowardkenneth@gmail.com</li>
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
    fetch(`${apiBaseUrl}/api/categories/`)
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
    fetch(`${apiBaseUrl}/api/pr/list/?category=${encodeURIComponent(cat.name)}`)
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
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/list/`)
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
        const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/list/`)
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
            <p>Visit the login page and enter your credentials. If you don't have an account, you can register as either a buyer (university/department) or supplier. Make sure to use the correct login role.</p>
          </details>

          <details className="faq-item">
            <summary><strong>I forgot my password. What should I do?</strong></summary>
            <p>Please contact the BAC office directly with your username or registered email. Our team will help you reset your password or provide account recovery assistance.</p>
          </details>
        </section>

        {/* Buyer Section */}
        <section className="faq-section">
          <h2>Buyer Portal</h2>
          
          <details className="faq-item">
            <summary><strong>How do I submit a Purchase Request?</strong></summary>
            <p>Log in to your buyer account and navigate to the Dashboard. Upload your signed PR document (PDF or image). The OCR system will automatically extract key information. BAC staff will review and number the request before supplier matching begins.</p>
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
            <summary><strong>How do I submit a quotation for a procurement opportunity?</strong></summary>
            <p>Navigate to Opportunities or RFQs, select the item you're interested in, and click "Submit Quotation". Enter your quoted amount, estimated delivery time, warranty, and any remarks. Submit to be considered for the award.</p>
          </details>

          <details className="faq-item">
            <summary><strong>Can I modify a quotation after submission?</strong></summary>
            <p>Once submitted, quotations generally cannot be edited directly. Contact BAC if urgent changes are needed. For future opportunities, you'll be able to submit fresh quotations.</p>
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
      const tempAccounts = {
        buyer: { username: 'buyer1', password: 'buyer123', role: 'buyer', name: 'BAC Buyer' },
        supplier: { username: 'supplier1', password: 'supplier123', role: 'supplier', name: 'Supplier Partner', supplierId: 1 },
        admin: { username: 'admin', password: 'admin123', role: 'admin', name: 'BAC Admin' },
      }

      const credentials = tempAccounts[selectedRole]
      if (credentials && username === credentials.username && password === credentials.password) {
        const user = { username, role: selectedRole, name: credentials.name, supplier_id: credentials.supplierId, supplier_status: credentials.supplierStatus || 'Approved' }
        localStorage.setItem('eProcureUser', JSON.stringify(user))
        if (credentials.supplierId) {
          localStorage.setItem('supplier_id', credentials.supplierId.toString())
        }
        localStorage.setItem('supplier_status', user.supplier_status)
        alert(`Login successful as ${selectedRole}`)
        if (selectedRole === 'admin') {
          navigate('/admin')
        } else {
          navigate(`/${selectedRole}`)
        }
        return
      }

      try {
        const response = await fetch(`${apiBaseUrl}/api/login/`, {
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
        localStorage.setItem('eProcureUser', JSON.stringify(user))

        if (user.role === 'supplier') {
          if (user.supplier_id) {
            localStorage.setItem('supplier_id', user.supplier_id.toString())
          }
          if (user.supplier_status) {
            localStorage.setItem('supplier_status', user.supplier_status)
          }
        }

        // If supplier, fetch their supplier profile ID
        if (user.role === 'supplier' && !user.supplier_id) {
          try {
            const suppliersRes = await fetch(`${apiBaseUrl}/api/suppliers/`)
            if (suppliersRes.ok) {
              const suppliers = await suppliersRes.json()
              // Try to find supplier by email or other identifier
              if (suppliers.length > 0) {
                localStorage.setItem('supplier_id', suppliers[0].id.toString())
                user.supplier_id = suppliers[0].id
                localStorage.setItem('eProcureUser', JSON.stringify(user))
              }
            }
            if (user.supplier_status) {
              localStorage.setItem('supplier_status', user.supplier_status)
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
        <div className="login-form-container">
          <h2>LOG IN</h2>
          <form className="login-form" onSubmit={handleSubmit}>
            <div className="form-field">
              <select name="role" value={role} onChange={(e) => setRole(e.target.value)} className="form-select">
                <option value="">Select Login as</option>
                <option value="buyer">Buyer</option>
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
              <button type="button" className="btn-outline" onClick={() => alert('Forgot password flow not implemented yet.')}>Forgot Password</button>
              <button type="submit" className="btn-login">Log In</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

// ─── Workflow helpers ─────────────────────────────────────────────────────────

const _thS = { padding: '11px 14px', textAlign: 'left', fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }
const _tdS = { padding: '11px 14px', fontSize: 13, verticalAlign: 'middle' }

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
      fetch(`${apiBase}/api/categories/`).then((r) => { if (!r.ok) throw new Error('Failed to load categories'); return r.json() }),
      fetch(`${apiBase}/api/pr/${prId}/items/`).then((r) => { if (!r.ok) throw new Error('Failed to load PR items'); return r.json() }),
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

  const allAssigned = items.length > 0 && items.every((item) => assignments[item.id])
  const unassignedCount = items.filter((item) => !assignments[item.id]).length

  async function handleSave() {
    setTouched(true)
    if (!allAssigned) return
    setSaving(true)
    setError('')
    try {
      const res = await fetch(`${apiBase}/api/pr/${prId}/items/categories/`, {
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
              <th style={_thS}>#</th>
              <th style={_thS}>Item Description</th>
              <th style={_thS}>Qty</th>
              <th style={_thS}>Unit Cost</th>
              <th style={{ ..._thS, minWidth: 220 }}>Final Category</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => {
              const assigned = assignments[item.id] || ''
              const missing = touched && !assigned
              return (
                <tr key={item.id} className={`cat-assign-row${missing ? ' cat-row-missing' : ''}`} style={{ background: idx % 2 === 0 ? '#fff' : '#fbfcff' }}>
                  <td style={_tdS}>{idx + 1}</td>
                  <td style={{ ..._tdS, fontWeight: 500 }}>{item.item_description || '—'}</td>
                  <td style={_tdS}>{Number(item.quantity)}</td>
                  <td style={_tdS}>₱{Number(item.unit_cost).toLocaleString()}</td>
                  <td style={_tdS}>
                    <select
                      value={assigned}
                      onChange={(e) => setAssignments((prev) => ({ ...prev, [item.id]: e.target.value }))}
                      className={`cat-assign-select${missing ? ' cat-select-missing' : ''}`}
                    >
                      <option value="">— Select category —</option>
                      {categories.map((cat) => (
                        <option key={cat.id} value={cat.name}>{cat.name}</option>
                      ))}
                    </select>
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

// ─── SupplierMatchingView ─────────────────────────────────────────────────────

const RFQPreparation = ({ prId, apiBase, supplier, prDetails, onBack }) => {
  const [rfq, setRfq] = React.useState(null)
  const [subject, setSubject] = React.useState('')
  const [message, setMessage] = React.useState('')
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    fetch(`${apiBase}/api/pr/${prId}/rfq/`)
      .then((response) => response.ok ? response.json() : { rfqs: [] })
      .then((data) => {
        const existing = (data.rfqs || []).find((item) => item.supplier.id === supplier.id && item.status !== 'sent')
        if (existing) {
          setRfq(existing)
          setSubject(existing.subject)
          setMessage(existing.message)
        } else {
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
  }, [apiBase, prId, prDetails?.entity_name, prDetails?.pr_no, supplier.company_name, supplier.contact_person, supplier.id])

  const items = prDetails?.items || []
  const saveRfq = async (send = false) => {
    setSaving(true)
    setError('')
    try {
      const response = await fetch(`${apiBase}/api/pr/${prId}/rfq/`, {
        method: rfq ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          supplier_id: supplier.id,
          category: supplier.matched_category || prDetails?.category || items.find((item) => item.category)?.category || '',
          rfq_id: rfq?.id,
          subject,
          message,
          send,
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.message || 'Unable to save RFQ')
      setRfq(data)
      setSubject(data.subject)
      setMessage(data.message)
      if (send) window.alert(`RFQ sent successfully to ${supplier.company_name}.`)
    } catch (saveError) {
      setError(saveError.message || 'Unable to save RFQ')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="supplier-section">
      <WorkflowStepper current="rfq" />
      <div className="supplier-header" style={{ marginTop: 20 }}>
        <h1>Request for Quotation</h1>
        <p>Review the existing Purchase Request and supplier details before sending.</p>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="card rfq-review-card">
        <div className="detail-grid">
          <div><strong>PR No.: </strong><span>{prDetails?.pr_no || `PR-${prId}`}</span></div>
          <div><strong>PR Date: </strong><span>{prDetails?.date || 'N/A'}</span></div>
          <div><strong>Requesting Office / Entity: </strong><span>{prDetails?.office_section || prDetails?.entity_name || 'N/A'}</span></div>
          <div><strong>Category: </strong><span>{prDetails?.category || items.find((item) => item.category)?.category || 'N/A'}</span></div>
          <div><strong>Supplier: </strong><span>{supplier.company_name}</span></div>
          <div><strong>Supplier Contact: </strong><span>{supplier.contact_person || 'N/A'}</span></div>
          <div><strong>Supplier Email: </strong><span>{supplier.email || 'N/A'}</span></div>
          <div><strong>Status: </strong><span>{rfq?.status || 'Draft'}</span></div>
        </div>
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
        <label className="form-field"><span>Subject</span><input value={subject} onChange={(event) => setSubject(event.target.value)} placeholder={`Request for Quotation - PR ${prDetails?.pr_no || prId}`} /></label>
        <label className="form-field"><span>RFQ Message</span><textarea rows="12" value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Enter the RFQ message" /></label>
        <div className="rfq-attachment">
          <strong>Original PR Attachment</strong>
          {prDetails?.source_file_url ? <a href={prDetails.source_file_url} target="_blank" rel="noreferrer">{prDetails.source_filename || 'Open original PR'}</a> : <span>No uploaded PR document available.</span>}
        </div>
      </div>
      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onBack} disabled={saving}>Back to Matching</button>
        <button type="button" className="btn-secondary" onClick={() => saveRfq(false)} disabled={saving}>{saving ? 'Saving...' : 'Save RFQ'}</button>
        <button type="button" className="btn-primary" onClick={() => saveRfq(true)} disabled={saving || !supplier.email || !subject.trim() || !message.trim()}>{saving ? 'Sending...' : 'Send RFQ'}</button>
      </div>
    </div>
  )
}

const SupplierMatchingView = ({ prId, apiBase, onBack }) => {
  const [matches, setMatches] = React.useState([])
  const [prDetails, setPrDetails] = React.useState(null)
  const [selectedSupplier, setSelectedSupplier] = React.useState(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([
      fetch(`${apiBase}/api/pr/${prId}/supplier-match/`).then((r) => { if (!r.ok) throw new Error('Failed to load supplier matches'); return r.json() }),
      fetch(`${apiBase}/api/pr/${prId}/details/`).then((r) => { if (!r.ok) throw new Error('Failed to load Purchase Request details'); return r.json() }),
    ])
      .then(([matchData, details]) => { setMatches(matchData); setPrDetails(details); setLoading(false) })
      .catch((err) => { setError(err.message || 'Failed to load'); setLoading(false) })
  }, [prId, apiBase])

  if (selectedSupplier && prDetails) {
    return <RFQPreparation prId={prId} apiBase={apiBase} supplier={selectedSupplier} prDetails={prDetails} onBack={() => setSelectedSupplier(null)} />
  }

  return (
    <div className="supplier-section">
      <WorkflowStepper current="matching" />

      <div className="supplier-header" style={{ marginTop: 20 }}>
        <h1>Supplier Matching</h1>
        <p>Suppliers matched by item categories for Purchase Request <strong>#{prDetails?.pr_no || prId}</strong>.</p>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 14 }}>{error}</div>}

      {prDetails && (
        <div className="card" style={{ padding: 16, marginBottom: 18 }}>
          <div className="detail-grid">
            <div><strong>PR Number: </strong><span>{prDetails.pr_no || 'N/A'}</span></div>
            <div><strong>PR Date: </strong><span>{prDetails.date || prDetails.created_at?.slice(0, 10) || 'N/A'}</span></div>
            <div><strong>Entity Name: </strong><span>{prDetails.entity_name || 'N/A'}</span></div>
            <div><strong>Office / Section: </strong><span>{prDetails.office_section || 'N/A'}</span></div>
            <div><strong>Category: </strong><span>{prDetails.category || 'Not assigned'}</span></div>
            <div><strong>Grand Total: </strong><span>₱{Number(prDetails.grand_total || 0).toLocaleString()}</span></div>
            <div style={{ gridColumn: '1 / -1' }}><strong>Purpose: </strong><span>{prDetails.purpose || 'N/A'}</span></div>
          </div>
          {prDetails.items?.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <strong>Requested Items</strong>
              <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
                {prDetails.items.map((item) => (
                  <li key={item.id}>{item.item_description} ({item.quantity} {item.unit || 'units'})</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="skeleton-stack">
          {[1, 2, 3].map((n) => <div key={n} className="skeleton-line" style={{ height: 110 }} />)}
        </div>
      ) : matches.length === 0 ? (
        <div className="alert alert-info">No matching suppliers available yet. Register a supplier for this category to continue supplier matching.</div>
      ) : (
        matches.map((group) => (
          <div key={group.category} style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <span className="status-badge status-review" style={{ fontSize: 12 }}>{group.category}</span>
              <span style={{ fontSize: 14, color: '#64748b' }}>{group.suppliers.length} supplier{group.suppliers.length !== 1 ? 's' : ''} matched</span>
            </div>
            <div className="supplier-match-grid">
              {group.suppliers.length === 0 && (
                <div className="supplier-match-empty">No suppliers found for this category.</div>
              )}
              {group.suppliers.map((s) => {
                return (
                  <article key={s.id} className="supplier-match-card">
                    <div className="supplier-match-head">
                      <h4>{s.company_name}</h4>
                      <span className={`status-badge ${s.status === 'Approved' ? 'status-open' : 'status-review'}`}>
                        {s.status || 'Pending'}
                      </span>
                    </div>
                    <div className="supplier-match-body">
                      {s.contact_person && <div><strong>Contact:</strong> {s.contact_person}</div>}
                      {s.email && <div><strong>Email:</strong> {s.email}</div>}
                      {s.business_address && <div><strong>Address:</strong> {s.business_address}</div>}
                      {s.nature_of_business && <div><strong>Business:</strong> {s.nature_of_business}</div>}
                    </div>
                    <div className="supplier-match-foot">
                      <button type="button" className="btn-sm btn-primary" onClick={() => setSelectedSupplier({ ...s, matched_category: group.category })}>Select Supplier</button>
                    </div>
                  </article>
                )
              })}
            </div>
          </div>
        ))
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
    fetch(`${apiBase}/api/pr/unmatched/`)
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

const Admin = () => {
  const navigate = useNavigate()
  const [currentTab, setCurrentTab] = React.useState('suppliers')
  const [workflowPrId, setWorkflowPrId] = React.useState(null)
  const [prRecords, setPrRecords] = React.useState([])
  const [prLoading, setPrLoading] = React.useState(false)
  const [prError, setPrError] = React.useState('')
  const [prSavingId, setPrSavingId] = React.useState(null)
  const [prDeletingId, setPrDeletingId] = React.useState(null)
  const [editingPr, setEditingPr] = React.useState(null)
  const [editPrForm, setEditPrForm] = React.useState(null)
  const [editPrLoading, setEditPrLoading] = React.useState(false)
  const [editPrSaving, setEditPrSaving] = React.useState(false)
  const [editPrNumberMode, setEditPrNumberMode] = React.useState('automatic')
  const [editPrCustomNumber, setEditPrCustomNumber] = React.useState('')
  const [editPrSourceUrl, setEditPrSourceUrl] = React.useState('')
  const [dashboardStats, setDashboardStats] = React.useState(null)
  const [dashboardLoading, setDashboardLoading] = React.useState(false)
  const [dashboardError, setDashboardError] = React.useState('')
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
  const [documentStatusDrafts, setDocumentStatusDrafts] = React.useState({})
  const [previewDoc, setPreviewDoc] = React.useState(null)
  const [previewVisible, setPreviewVisible] = React.useState(false)
  const [navCollapsed, setNavCollapsed] = React.useState(false)
  const [buyerAccountForm, setBuyerAccountForm] = React.useState({ username: '', fullName: '', email: '', unitOffice: '', password: '', confirmPassword: '' })
  const [buyerAccountSaving, setBuyerAccountSaving] = React.useState(false)
  const [buyerAccountMessage, setBuyerAccountMessage] = React.useState('')
  const [buyerAccountError, setBuyerAccountError] = React.useState('')
  const [buyerAccounts, setBuyerAccounts] = React.useState([])
  const [buyerAccountsLoading, setBuyerAccountsLoading] = React.useState(false)
  const [buyerAccountSearch, setBuyerAccountSearch] = React.useState('')
  const [buyerAccountActionId, setBuyerAccountActionId] = React.useState(null)
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  const prStatusOptions = [
    { value: 'uploaded', label: 'Uploaded' },
    { value: 'in_review', label: 'In Review' },
    { value: 'matched', label: 'Matched' },
    { value: 'approved', label: 'Approved' },
    { value: 'rejected', label: 'Rejected' },
  ]

  const handleLogout = () => {
    localStorage.removeItem('eProcureUser')
    navigate('/login')
  }

  const loadBuyerAccounts = React.useCallback(async () => {
    setBuyerAccountsLoading(true)
    try {
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/buyer-accounts/`)
      if (!response.ok) throw new Error('Unable to load Buyer accounts.')
      setBuyerAccounts(await response.json())
    } catch (error) {
      setBuyerAccountError(error?.message || 'Unable to load Buyer accounts.')
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
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/register/`, {
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
      if (!response.ok) throw new Error(result.message || 'Unable to create Buyer account.')
      setBuyerAccountMessage('Buyer account created successfully.')
      setBuyerAccountForm({ username: '', fullName: '', email: '', unitOffice: '', password: '', confirmPassword: '' })
      loadBuyerAccounts()
    } catch (error) {
      setBuyerAccountError(error?.message || 'Unable to create Buyer account.')
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

  const toggleBuyerAccount = async (account) => {
    setBuyerAccountActionId(account.id)
    setBuyerAccountError('')
    try {
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/buyer-accounts/${account.id}/status/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !account.is_active }),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.message || 'Unable to update Buyer account.')
      setBuyerAccounts((current) => current.map((item) => item.id === account.id ? { ...item, is_active: result.is_active } : item))
    } catch (error) {
      setBuyerAccountError(error?.message || 'Unable to update Buyer account.')
    } finally {
      setBuyerAccountActionId(null)
    }
  }

  const handlePrSaved = React.useCallback((prId) => {
    setWorkflowPrId(prId)
    setCurrentTab('assign-categories')
  }, [])

  const handleContinueMatching = React.useCallback((prId) => {
    setWorkflowPrId(prId)
    setCurrentTab('supplier-matching')
  }, [])

  const loadSupplierRegistrations = React.useCallback(async () => {
    setSupplierLoading(true)
    setSupplierError('')
    try {
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/`)
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
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/admin/dashboard-summary/`)
      if (!res.ok) throw new Error('Failed to load dashboard data')
      setDashboardStats(await res.json())
    } catch (error) {
      console.error(error)
      setDashboardError(error?.message || 'Failed to load dashboard data')
    } finally {
      setDashboardLoading(false)
    }
  }, [apiBaseUrl])

  const loadSupplierDetails = React.useCallback(async (supplierId) => {
    try {
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/${supplierId}/profile/`)
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

  const executeReviewDecision = async (supplierId, nextStatus, actionName) => {
    const trimmedRemarks = reviewRemarks.trim()
    if ((nextStatus === 'Rejected' || nextStatus === 'For Compliance') && !trimmedRemarks) {
      setSupplierError('Remarks are required before rejecting or requesting additional documents.')
      return
    }

    setSupplierActioningId(supplierId)
    setSupplierError('')
    try {
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/${supplierId}/status/`, {
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
      setSelectedSupplierDetails((prev) => prev && prev.id === supplierId ? { ...prev, status: nextStatus, review_remarks: nextReviewRemarks } : prev)
      setReviewRemarks(nextReviewRemarks)
      setSupplierError('')
    } catch (error) {
      console.error(error)
      setSupplierError(error?.message || `Failed to ${actionName} supplier`)
    } finally {
      setSupplierActioningId(null)
    }
  }

  const confirmReviewAction = async (supplierId, nextStatus, actionName, confirmationMessage) => {
    const trimmedRemarks = reviewRemarks.trim()
    if ((nextStatus === 'Rejected' || nextStatus === 'For Compliance') && !trimmedRemarks) {
      setSupplierError('Remarks are required before rejecting or requesting additional documents.')
      return
    }

    const shouldProceed = window.confirm(confirmationMessage)
    if (!shouldProceed) return

    await executeReviewDecision(supplierId, nextStatus, actionName)
  }

  const handleApprove = async (supplierId) => {
    await confirmReviewAction(supplierId, 'Approved', 'approve', 'Are you sure you want to approve this supplier?')
  }

  const handleReject = async (supplierId) => {
    await confirmReviewAction(supplierId, 'Rejected', 'reject', 'Are you sure you want to reject this supplier?')
  }

  const handleRequestCompliance = async (supplierId) => {
    await confirmReviewAction(supplierId, 'For Compliance', 'request additional documents', 'Are you sure you want to request additional documents from this supplier?')
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
    setDocumentStatusDrafts({})
  }

  const loadPrRecords = React.useCallback(async () => {
    setPrLoading(true)
    setPrError('')
    try {
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/list/`)
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
  }, [currentTab, loadBuyerAccounts, loadDashboardStats, loadPrRecords, loadSupplierRegistrations])

  const handlePrStatusChange = async (prId, nextStatus) => {
    setPrSavingId(prId)
    setPrError('')
    try {
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/${prId}/status/`, {
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
    const confirmed = window.confirm(`Delete Purchase Request #${prId}? This cannot be undone.`)
    if (!confirmed) return

    setPrDeletingId(prId)
    setPrError('')
    try {
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/${prId}/`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => null)
        throw new Error(payload?.message || 'Failed to delete PR')
      }
      setPrRecords((prev) => prev.filter((row) => row.id !== prId))
    } catch (error) {
      console.error(error)
      setPrError(error?.message || 'Failed to delete PR')
    } finally {
      setPrDeletingId(null)
    }
  }

  const prStatusMeta = {
    uploaded: { label: 'Uploaded', className: 'status-review' },
    in_review: { label: 'In Review', className: 'status-review' },
    matched: { label: 'Matched', className: 'status-open' },
    approved: { label: 'Approved', className: 'status-open' },
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
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/${pr.id}/details/`)
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
    } catch (error) {
      setPrError(error?.message || 'Failed to load Purchase Request details')
      setEditingPr(null)
    } finally {
      setEditPrLoading(false)
    }
  }

  const closeEditPr = () => {
    if (editPrSaving) return
    setEditingPr(null)
    setEditPrForm(null)
  }

  const handleSavePrEdit = async (finalizeReview = false) => {
    if (!editPrForm || !editingPr) return
    setEditPrSaving(true)
    setPrError('')
    try {
      const res = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/${editingPr.id}/edit/`, {
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
      <nav className="admin-navbar">
        <div className="admin-sidebar-header">
          <div className="admin-brand">
            <span className="admin-brand-mark">eP</span>
            <span className="admin-brand-copy">eProcura</span>
          </div>
          <button
            className="admin-nav-toggle"
            onClick={() => setNavCollapsed((v) => !v)}
            aria-label={navCollapsed ? 'Open navigation' : 'Collapse navigation'}
            title={navCollapsed ? 'Open navigation' : 'Collapse navigation'}
          >
            {navCollapsed ? <Menu size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        <div className="admin-nav-scroll">
          <div className="admin-nav-items">
            <button
              className={`admin-nav-item ${currentTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => setCurrentTab('dashboard')}
              title="Dashboard"
            >
              <LayoutDashboard size={14} />
              <span className="admin-nav-label">Dashboard</span>
            </button>
            <button
              className={`admin-nav-item ${currentTab === 'suppliers' ? 'active' : ''}`}
              onClick={() => setCurrentTab('suppliers')}
              title="Supplier Management"
            >
              <Users size={14} />
              <span className="admin-nav-label">Supplier Management</span>
            </button>
            <button
              className={`admin-nav-item ${currentTab === 'buyer-accounts' ? 'active' : ''}`}
              onClick={() => setCurrentTab('buyer-accounts')}
              title="Buyer Accounts"
            >
              <Users size={14} />
              <span className="admin-nav-label">Buyer Accounts</span>
            </button>
            <button
              className={`admin-nav-item ${currentTab === 'pr-upload' ? 'active' : ''}`}
              onClick={() => setCurrentTab('pr-upload')}
              title="PR Upload"
            >
              <UploadCloud size={14} />
              <span className="admin-nav-label">PR Upload</span>
            </button>
            <button
              className={`admin-nav-item ${currentTab === 'pr-monitoring' ? 'active' : ''}`}
              onClick={() => setCurrentTab('pr-monitoring')}
              title="PR Review & Monitoring"
            >
              <ClipboardList size={14} />
              <span className="admin-nav-label">PR Review & Monitoring</span>
            </button>
          </div>
        </div>

        <div className="admin-navbar-right">
          <div className="admin-user-card" aria-label="Logged in user">
            <div className="admin-user">Administrator</div>
            <div className="admin-user-email">admin@ctu.edu.ph</div>
          </div>
          <button className="admin-nav-logout" onClick={handleLogout} title="Log Out">
            <LogOut size={14} />
            <span className="admin-nav-label">Log Out</span>
          </button>
        </div>
      </nav>

      {/* Admin Content */}
      <div className="admin-content">
        {currentTab === 'dashboard' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>Admin Dashboard</h1>
              <p>System overview and management controls</p>
            </div>
            {dashboardError && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{dashboardError}</div>}
            <div className="admin-cards">
              <div className="admin-card">
                <div className="admin-card-eyebrow">Procurement</div>
                <div className="admin-card-value">{dashboardLoading && !dashboardStats ? '...' : dashboardStats?.total_purchase_requests ?? 0}</div>
                <div className="admin-card-label">Total Purchase Requests</div>
              </div>
              <div className="admin-card">
                <div className="admin-card-eyebrow">Needs attention</div>
                <div className="admin-card-value">{dashboardLoading && !dashboardStats ? '...' : dashboardStats?.pending_purchase_requests ?? 0}</div>
                <div className="admin-card-label">Open Purchase Requests</div>
              </div>
              <div className="admin-card">
                <div className="admin-card-eyebrow">Completed</div>
                <div className="admin-card-value">{dashboardLoading && !dashboardStats ? '...' : dashboardStats?.approved_purchase_requests ?? 0}</div>
                <div className="admin-card-label">Approved Purchase Requests</div>
              </div>
              <div className="admin-card">
                <div className="admin-card-eyebrow">Supplier network</div>
                <div className="admin-card-value">{dashboardLoading && !dashboardStats ? '...' : dashboardStats?.total_suppliers ?? 0}</div>
                <div className="admin-card-label">Registered Suppliers</div>
              </div>
            </div>
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

                      <div className="supplier-detail-panel">
                        <div className="supplier-panel-title">Supplier Categories</div>
                        <div className="supplier-badge-list">
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
                          const statusMeta = getDocumentStatusMeta(document.verification_status)
                          const currentStatus = documentStatusDrafts[document.id] || document.verification_status || 'Pending'
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
                                <select value={currentStatus} onChange={(event) => handleDocumentStatusChange(document.id, event.target.value)}>
                                  <option value="Pending">Pending</option>
                                  <option value="Verified">Verified</option>
                                  <option value="Rejected">Rejected</option>
                                </select>
                                <button className="btn-sm btn-secondary" type="button" onClick={() => openPreview(document)}>Preview</button>
                                <a className="btn-sm btn-secondary" href={document.file_url || '#'} target="_blank" rel="noreferrer">Download</a>
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
                          {selectedSupplierDetails.status !== 'Approved' && (
                            <button className="btn btn-login supplier-action-btn supplier-action-btn-primary" type="button" onClick={() => handleApprove(selectedSupplierDetails.id)} disabled={supplierActioningId === selectedSupplierDetails.id}>
                              <Check size={16} />
                              Approve Registration
                            </button>
                          )}
                          <button className="btn btn-secondary supplier-action-btn supplier-action-btn-outline" type="button" onClick={() => handleRequestCompliance(selectedSupplierDetails.id)} disabled={supplierActioningId === selectedSupplierDetails.id}>
                            <FileText size={16} />
                            Request Additional Documents
                          </button>
                          {selectedSupplierDetails.status !== 'Approved' && (
                            <button className="btn btn-danger supplier-action-btn supplier-action-btn-danger" type="button" onClick={() => handleReject(selectedSupplierDetails.id)} disabled={supplierActioningId === selectedSupplierDetails.id}>
                              <X size={16} />
                              Reject Registration
                            </button>
                          )}
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
              <h1>Buyer Accounts</h1>
              <p>Create and manage Buyer or End User accounts for Purchase Request submission.</p>
            </div>
            <div className="buyer-account-layout">
              <section className="card buyer-account-panel">
                <div className="panel-header">
                  <div>
                    <h2>Create Buyer Account</h2>
                    <p className="supplier-subtext">New accounts are created with access to PR upload.</p>
                  </div>
                </div>
                <form className="buyer-account-form" onSubmit={handleBuyerAccountSubmit}>
                <label className="form-field">
                  <span>Full Name</span>
                  <input required value={buyerAccountForm.fullName} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, fullName: event.target.value }))} placeholder="Buyer or End User name" />
                </label>
                <label className="form-field">
                  <span>Username</span>
                  <input required value={buyerAccountForm.username} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, username: event.target.value }))} placeholder="buyer.username" />
                </label>
                <label className="form-field">
                  <span>Email</span>
                  <input required type="email" value={buyerAccountForm.email} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="buyer@office.edu" />
                </label>
                <label className="form-field">
                  <span>Unit / Office</span>
                  <input required value={buyerAccountForm.unitOffice} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, unitOffice: event.target.value }))} placeholder="Procurement Office" />
                </label>
                <label className="form-field">
                  <span>Password</span>
                  <input required type="password" minLength={8} value={buyerAccountForm.password} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, password: event.target.value }))} placeholder="At least 8 characters" />
                </label>
                <label className="form-field">
                  <span>Confirm Password</span>
                  <input required type="password" minLength={8} value={buyerAccountForm.confirmPassword} onChange={(event) => setBuyerAccountForm((prev) => ({ ...prev, confirmPassword: event.target.value }))} placeholder="Re-enter password" />
                </label>
                {buyerAccountError && <div className="alert alert-error" role="alert">{buyerAccountError}</div>}
                {buyerAccountMessage && <div className="alert alert-success" role="status">{buyerAccountMessage}</div>}
                <div className="form-actions">
                  <button type="submit" className="btn btn-primary" disabled={buyerAccountSaving}>{buyerAccountSaving ? 'Creating Account...' : 'Create Buyer Account'}</button>
                </div>
                </form>
              </section>

              <section className="card buyer-accounts-list-panel">
                <div className="buyer-accounts-list-header">
                  <div>
                    <h2>Managed Accounts</h2>
                    <p className="supplier-subtext">{buyerAccounts.length} Buyer account{buyerAccounts.length === 1 ? '' : 's'} registered</p>
                  </div>
                  <div className="buyer-account-search">
                    <Search size={16} />
                    <input type="search" value={buyerAccountSearch} onChange={(event) => setBuyerAccountSearch(event.target.value)} placeholder="Search accounts" aria-label="Search Buyer accounts" />
                  </div>
                </div>
                {buyerAccountsLoading ? (
                  <div className="buyer-accounts-empty">Loading accounts...</div>
                ) : filteredBuyerAccounts.length === 0 ? (
                  <div className="buyer-accounts-empty">No Buyer accounts found.</div>
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
                          <span className={`status-badge ${account.is_active ? 'status-open' : 'status-merged'}`}>{account.is_active ? 'Active' : 'Inactive'}</span>
                          <button type="button" className="btn-sm btn-secondary" onClick={() => toggleBuyerAccount(account)} disabled={buyerAccountActionId === account.id}>
                            {buyerAccountActionId === account.id ? 'Updating...' : account.is_active ? 'Deactivate' : 'Activate'}
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

        {currentTab === 'pr-upload' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>PR Upload</h1>
              <p>Upload Purchase Requests (PR) for automated extraction and review.</p>
            </div>

            <div className="admin-pr-upload">
              <div className="note">Drag a PDF or image of the PR into the area below. Extracted fields will appear for review and editing.</div>
              <DragDropUpload onSaved={handlePrSaved} />
            </div>
          </div>
        )}

        {currentTab === 'assign-categories' && workflowPrId && (
          <AssignCategories
            prId={workflowPrId}
            apiBase={apiBaseUrl}
            onComplete={(prId) => setCurrentTab('supplier-matching')}
            onBack={() => setCurrentTab('pr-upload')}
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
            </div>

            {prError && (
              <div className="alert alert-error" style={{ marginBottom: '16px' }}>
                <strong>Unable to load PR records.</strong> {prError}
              </div>
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
                        className={`btn-sm pr-review-action-btn ${pr.category?.trim() ? 'pr-review-btn' : 'pr-assign-category-btn'}`}
                        onClick={() => {
                          if (!pr.category?.trim()) {
                            setWorkflowPrId(pr.id)
                            setCurrentTab('assign-categories')
                          } else {
                            handleEditPr(pr)
                          }
                        }}
                      >
                        {pr.category?.trim() ? <Pencil size={14} /> : <ClipboardList size={14} />}
                        {pr.category?.trim() ? 'Review PR' : 'Assign Category'}
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
                  <span>Supplier Matching</span>
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
                            onClick={() => handleContinueMatching(pr.id)}
                          >
                            Continue Matching
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
                          onClick={() => handlePrDelete(pr.id)}
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
                      {editPrSourceUrl && (
                        <div className="pr-review-document-pane">
                          <div className="pr-review-document-header">
                            <h3>Original PR Document</h3>
                            <a className="btn-sm btn-secondary" href={editPrSourceUrl} target="_blank" rel="noreferrer">Open document</a>
                          </div>
                          <iframe src={editPrSourceUrl} title="Original Purchase Request document" />
                        </div>
                      )}
                      <div className="modal-body pr-edit-body">
                        <label className="form-field">
                          <span>PR Number</span>
                          <input value={editPrForm.pr_no} readOnly />
                        </label>
                        {!editPrForm.pr_no && (
                          <div className="pr-review-numbering">
                            <span className="form-field-label">Final PR Number</span>
                            <div className="numbering-options">
                              <label><input type="radio" name="review-pr-numbering" checked={editPrNumberMode === 'automatic'} onChange={() => setEditPrNumberMode('automatic')} /> Automatic</label>
                              <label><input type="radio" name="review-pr-numbering" checked={editPrNumberMode === 'custom'} onChange={() => setEditPrNumberMode('custom')} /> Custom</label>
                            </div>
                            {editPrNumberMode === 'automatic' ? (
                              <small>Next available number will be assigned when you continue to Supplier Matching.</small>
                            ) : (
                              <input value={editPrCustomNumber} onChange={(event) => setEditPrCustomNumber(event.target.value)} placeholder="YYYY-MM-NNN" />
                            )}
                          </div>
                        )}
                        <label className="form-field">
                          <span>Entity Name *</span>
                          <input value={editPrForm.entity_name} onChange={(event) => setEditPrForm((prev) => ({ ...prev, entity_name: event.target.value }))} />
                        </label>
                        <label className="form-field">
                          <span>Category</span>
                          <input value={editPrForm.category} onChange={(event) => setEditPrForm((prev) => ({ ...prev, category: event.target.value }))} />
                        </label>
                        <label className="form-field">
                          <span>Fund Cluster</span>
                          <input value={editPrForm.fund_cluster} onChange={(event) => setEditPrForm((prev) => ({ ...prev, fund_cluster: event.target.value }))} />
                        </label>
                        <label className="form-field">
                          <span>Office / Section</span>
                          <input value={editPrForm.office_section} onChange={(event) => setEditPrForm((prev) => ({ ...prev, office_section: event.target.value }))} />
                        </label>
                        <label className="form-field">
                          <span>Responsibility Center Code</span>
                          <input value={editPrForm.responsibility_center_code} onChange={(event) => setEditPrForm((prev) => ({ ...prev, responsibility_center_code: event.target.value }))} />
                        </label>
                        <label className="form-field">
                          <span>Date</span>
                          <input type="date" value={editPrForm.date} onChange={(event) => setEditPrForm((prev) => ({ ...prev, date: event.target.value }))} />
                        </label>
                        <label className="form-field">
                          <span>Purpose</span>
                          <textarea rows="3" value={editPrForm.purpose} onChange={(event) => setEditPrForm((prev) => ({ ...prev, purpose: event.target.value }))} />
                        </label>
                        <div className="pr-edit-signatories">
                          {[
                            ['requested_by', 'Requested By'],
                            ['funds_available_by', 'Funds Available By'],
                            ['approved_by', 'Approved By'],
                            ['twg_verified_by', 'TWG Verified By'],
                          ].map(([field, label]) => (
                            <label className="form-field" key={field}>
                              <span>{label}</span>
                              <input value={editPrForm[field]} onChange={(event) => setEditPrForm((prev) => ({ ...prev, [field]: event.target.value }))} />
                            </label>
                          ))}
                        </div>
                        <div className="pr-edit-items">
                          <div className="pr-edit-items-header"><h3>Line Items</h3><button type="button" className="btn-sm btn-secondary" onClick={() => setEditPrForm((prev) => ({ ...prev, items: [...prev.items, { stock_property_no: '', unit: '', item_description: '', quantity: 0, unit_cost: 0, category: '' }] }))}>Add Item</button></div>
                          {editPrForm.items.map((item, index) => (
                            <div className="pr-edit-item" key={`${editingPr.id}-item-${index}`}>
                              <input aria-label={`Item ${index + 1} stock number`} placeholder="Stock / Property No." value={item.stock_property_no} onChange={(event) => setEditPrForm((prev) => ({ ...prev, items: prev.items.map((current, itemIndex) => itemIndex === index ? { ...current, stock_property_no: event.target.value } : current) }))} />
                              <input aria-label={`Item ${index + 1} description`} placeholder="Description" value={item.item_description} onChange={(event) => setEditPrForm((prev) => ({ ...prev, items: prev.items.map((current, itemIndex) => itemIndex === index ? { ...current, item_description: event.target.value } : current) }))} />
                              <input aria-label={`Item ${index + 1} unit`} placeholder="Unit" value={item.unit} onChange={(event) => setEditPrForm((prev) => ({ ...prev, items: prev.items.map((current, itemIndex) => itemIndex === index ? { ...current, unit: event.target.value } : current) }))} />
                              <input aria-label={`Item ${index + 1} quantity`} type="number" min="0" step="0.01" placeholder="Qty" value={item.quantity} onChange={(event) => setEditPrForm((prev) => ({ ...prev, items: prev.items.map((current, itemIndex) => itemIndex === index ? { ...current, quantity: event.target.value } : current) }))} />
                              <input aria-label={`Item ${index + 1} unit cost`} type="number" min="0" step="0.01" placeholder="Unit cost" value={item.unit_cost} onChange={(event) => setEditPrForm((prev) => ({ ...prev, items: prev.items.map((current, itemIndex) => itemIndex === index ? { ...current, unit_cost: event.target.value } : current) }))} />
                              <input aria-label={`Item ${index + 1} category`} placeholder="Category" value={item.category} onChange={(event) => setEditPrForm((prev) => ({ ...prev, items: prev.items.map((current, itemIndex) => itemIndex === index ? { ...current, category: event.target.value } : current) }))} />
                              <button type="button" className="icon-action-btn delete" aria-label={`Remove item ${index + 1}`} onClick={() => setEditPrForm((prev) => ({ ...prev, items: prev.items.filter((_, itemIndex) => itemIndex !== index) }))}><Trash2 size={14} /></button>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="modal-actions">
                        <button type="button" className="btn btn-outline" onClick={closeEditPr} disabled={editPrSaving}>Cancel</button>
                        <button type="button" className="btn btn-secondary" onClick={() => handleSavePrEdit(false)} disabled={editPrSaving || !editPrForm.entity_name.trim()}>{editPrSaving ? 'Saving...' : 'Save Corrections'}</button>
                        <button type="button" className="btn btn-primary" onClick={async () => { const saved = await handleSavePrEdit(true); if (saved) { setWorkflowPrId(editingPr.id); setCurrentTab('supplier-matching') } }} disabled={editPrSaving || !editPrForm.entity_name.trim()}>{editPrSaving ? 'Continuing...' : 'Continue to Supplier Matching'}</button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            <div className="admin-checklist">
              <h3>Monitoring Notes</h3>
              <ul>
                <li>Use PR Upload tab to ingest new Purchase Requests.</li>
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
      </div>
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

      const res = await fetch(`${apiBaseUrl}/api/upload/`, {
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
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/suppliers/register`, {
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
    localStorage.removeItem('eProcureUser')
    navigate('/login')
  }

  return (
    <div className={`admin-layout ${navCollapsed ? 'collapsed-nav' : ''}`}>
      {/* Buyer Sidebar Navigation */}
      <nav className="admin-navbar">
        <div className="admin-sidebar-header">
          <div className="admin-brand">
            <span className="admin-brand-mark">eP</span>
            <span className="admin-brand-copy">eProcure Buyer</span>
          </div>
          <button
            className="admin-nav-toggle"
            onClick={() => setNavCollapsed((v) => !v)}
            aria-label={navCollapsed ? 'Open navigation' : 'Collapse navigation'}
            title={navCollapsed ? 'Open navigation' : 'Collapse navigation'}
          >
            {navCollapsed ? <Menu size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        <div className="admin-nav-scroll">
          <div className="admin-nav-items">
            <button
              className={`admin-nav-item ${currentTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => setCurrentTab('dashboard')}
              title="Dashboard"
            >
              <LayoutDashboard size={14} />
              <span className="admin-nav-label">Dashboard</span>
            </button>
            <button
              className={`admin-nav-item ${currentTab === 'live-status' ? 'active' : ''}`}
              onClick={() => setCurrentTab('live-status')}
              title="Live Status"
            >
              <TrendingUp size={14} />
              <span className="admin-nav-label">Live Status</span>
            </button>
          </div>
        </div>

        <div className="admin-navbar-right">
          <div className="admin-user-card" aria-label="Logged in user">
            <div className="admin-user">{user?.name || user?.username || 'Buyer'}</div>
            <div className="admin-user-email">{user?.email || ''}</div>
          </div>
          <button className="admin-nav-logout" onClick={handleLogout} title="Log Out">
            <LogOut size={14} />
            <span className="admin-nav-label">Log Out</span>
          </button>
        </div>
      </nav>

      {/* Buyer Content */}
      <div className="admin-content">
        {currentTab === 'dashboard' && (
          <div className="supplier-section">
            <div className="supplier-header">
              <h1>Buyer Dashboard</h1>
              <p>Welcome back, {user?.name || 'Buyer'}. Submit and track Purchase Requests.</p>
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

            <section className="supplier-section">
              <h2>Next steps</h2>
              <ul>
                <li>Review supplier bids and document compliance reports.</li>
                <li>Compare proposals for university furniture and lab equipment.</li>
                <li>Request additional information from shortlisted suppliers.</li>
              </ul>
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

const BuyerPRStatusViewer = ({ prIds, username }) => {
  const [records, setRecords] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  const statusMeta = {
    uploaded: { label: 'For Review', className: 'status-review', step: 1 },
    in_review: { label: 'Under Review', className: 'status-review', step: 2 },
    matched: { label: 'Ready for Matching', className: 'status-open', step: 3 },
    approved: { label: 'Approved', className: 'status-open', step: 4 },
    rejected: { label: 'Rejected', className: 'status-merged', step: 4 },
  }

  const loadRecords = React.useCallback(async () => {
    if (!prIds.length && !username) return
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, '')}/api/pr/list/?submitted_by=${encodeURIComponent(username)}`)
      if (!response.ok) throw new Error('Unable to load your Purchase Requests')
      const databaseRecords = await response.json()
      const results = Array.isArray(databaseRecords) ? databaseRecords : []
      setRecords(results)
    } catch (loadError) {
      setError(loadError?.message || 'Unable to load Purchase Request status')
    } finally {
      setLoading(false)
    }
  }, [apiBaseUrl, prIds])

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
        <p>Track the PRs you submitted and see when BAC review is complete.</p>
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
        <div className="buyer-status-list">
          {records.map((record) => {
            const meta = statusMeta[record.status] || { label: record.status || 'Unknown', className: 'status-review', step: 1 }
            return (
              <article className="buyer-status-record" key={record.id}>
                <div className="buyer-status-record-head">
                  <div>
                    <strong>{record.pr_no || `Reference #${record.id}`}</strong>
                    <span>{record.entity_name || 'Purchase Request'}</span>
                  </div>
                  <span className={`status-badge ${meta.className}`}>{meta.label}</span>
                </div>
                <div className="buyer-status-meta">
                <span>Office: {record.office_section || 'N/A'}</span>
                <span>Date: {record.date ? new Date(record.date).toLocaleDateString() : 'N/A'}</span>
                <span>Total: {record.grand_total ?? '0.00'}</span>
              </div>
              <div className="buyer-status-progress" aria-label={`Purchase Request status: ${meta.label}`}>
                {['Submitted', 'BAC Review', 'Supplier Matching', 'Completed'].map((label, index) => (
                  <div className={`buyer-status-step ${index + 1 <= meta.step ? 'active' : ''}`} key={label}>
                    <span>{index + 1}</span>
                    <small>{label}</small>
                  </div>
                ))}
              </div>
            </article>
          )
        })}
        </div>
      </section>
    </>
  )
}

const Supplier = () => {
  const navigate = useNavigate()
  const user = React.useMemo(() => getStoredUser(), [])
  const [supplierData, setSupplierData] = React.useState(null)
  const [currentPage, setCurrentPage] = React.useState('dashboard')
  const [navCollapsed, setNavCollapsed] = React.useState(false)
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
  const supplierId = user?.supplier_id || localStorage.getItem('supplier_id')
  const supplierStatus = user?.supplier_status || localStorage.getItem('supplier_status') || 'Pending Review'

  React.useEffect(() => {
    if (!supplierId) return

    const fetchSupplierData = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/profile/`)
        if (response.ok) {
          const data = await response.json()
          setSupplierData(data)
        }
      } catch (error) {
        console.error('Failed to fetch supplier data:', error)
      }
    }

    fetchSupplierData()
  }, [supplierId, apiBaseUrl])

  const handleLogout = () => {
    localStorage.removeItem('eProcureUser')
    localStorage.removeItem('supplier_id')
    localStorage.removeItem('supplier_status')
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

  if (!isApproved && currentPage !== 'dashboard' && currentPage !== 'profile') {
    return (
      <div className="supplier-content-inner supplier-status-page">
        <div className="supplier-status-card">
          <span className={`status-pill ${isRejected ? 'danger' : isCompliance ? 'danger' : isPending ? 'warning' : ''}`}>
            {supplierStatus}
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
  }

  return (
    <div className={`admin-layout ${navCollapsed ? 'collapsed-nav' : ''}`}>
      <SupplierNav 
        currentPage={currentPage} 
        onPageChange={handlePageChange} 
        onLogout={handleLogout}
        navCollapsed={navCollapsed}
        onToggleNav={() => setNavCollapsed((v) => !v)}
      />
      <div className="admin-content">
        {currentPage === 'dashboard' && <SupplierDashboard supplierId={supplierId} apiBaseUrl={apiBaseUrl} supplierStatus={supplierStatus} />}
        {currentPage === 'opportunities' && <ProcurementOpportunities supplierId={supplierId} apiBaseUrl={apiBaseUrl} />}
        {currentPage === 'quotations' && <MyQuotations supplierId={supplierId} apiBaseUrl={apiBaseUrl} />}
        {currentPage === 'rfqs' && <SupplierRFQs supplierId={supplierId} apiBaseUrl={apiBaseUrl} />}
        {currentPage === 'profile' && <CompanyProfile supplierId={supplierId} apiBaseUrl={apiBaseUrl} />}
        {currentPage === 'notifications' && <SupplierNotifications supplierId={supplierId} apiBaseUrl={apiBaseUrl} />}
      </div>
    </div>
  )
}

const SupplierRFQs = ({ supplierId, apiBaseUrl }) => {
  const [rfqs, setRfqs] = React.useState([])
  const [selectedRfq, setSelectedRfq] = React.useState(null)
  const [showQuotationForm, setShowQuotationForm] = React.useState(false)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  const loadRFQs = React.useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/rfqs/`)
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

  if (selectedRfq) {
    return (
      <div className="supplier-content-inner">
        <button type="button" className="back-link" onClick={() => setSelectedRfq(null)}><ChevronLeft size={18} /> Back to RFQs</button>
        <div className="supplier-header">
          <h2>{selectedRfq.rfq_no}</h2>
          <p>{selectedRfq.subject}</p>
        </div>
        <div className="card rfq-review-card">
          <div className="detail-grid">
            <div><strong>PR No.: </strong><span>{selectedRfq.purchase_request.pr_no || `PR-${selectedRfq.purchase_request.id}`}</span></div>
            <div><strong>Requesting Office / Entity: </strong><span>{selectedRfq.purchase_request.office_section || selectedRfq.purchase_request.entity_name}</span></div>
            <div><strong>Category: </strong><span>{selectedRfq.purchase_request.category || 'N/A'}</span></div>
            <div><strong>Status: </strong><span>{selectedRfq.status}</span></div>
          </div>
          <h3>RFQ Message</h3>
          <div className="supplier-readonly-card" style={{ whiteSpace: 'pre-wrap' }}>{selectedRfq.message}</div>
        </div>
        <div className="card rfq-review-card">
          <h3>Requested Items</h3>
          <div className="opportunity-table-wrapper">
            <table className="opportunity-table">
              <thead><tr><th>Unit</th><th>Description</th><th>Quantity</th><th>Category</th></tr></thead>
              <tbody>{selectedRfq.purchase_request.items.map((item) => (
                <tr key={item.id}><td>{item.unit || 'N/A'}</td><td>{item.item_description || 'N/A'}</td><td>{item.quantity}</td><td>{item.category || 'N/A'}</td></tr>
              ))}</tbody>
            </table>
          </div>
          {selectedRfq.purchase_request.source_file_url && <p><strong>Attachment:</strong> <a href={selectedRfq.purchase_request.source_file_url} target="_blank" rel="noreferrer">{selectedRfq.purchase_request.source_filename || 'Original PR'}</a></p>}
        </div>
        <div className="form-actions">
          <button type="button" className="btn-secondary" onClick={() => setSelectedRfq(null)}>Back to RFQs</button>
          {selectedRfq.status === 'sent' ? (
            <button type="button" className="btn-primary" onClick={() => setShowQuotationForm(true)}>Submit Quotation</button>
          ) : (
            <span className="supplier-subtext">A quotation has already been submitted for this RFQ.</span>
          )}
        </div>
        {showQuotationForm && (
          <QuotationForm
            supplierId={supplierId}
            prId={selectedRfq.purchase_request.id}
            rfqId={selectedRfq.id}
            apiBaseUrl={apiBaseUrl}
            onClose={() => setShowQuotationForm(false)}
            onSuccess={() => { setShowQuotationForm(false); setSelectedRfq(null); loadRFQs() }}
          />
        )}
      </div>
    )
  }

  return (
    <div className="supplier-content-inner">
      <div className="supplier-header"><h2>Requests for Quotation</h2><p>Review RFQs sent to your company and submit a quotation.</p></div>
      {error && <div className="alert alert-error">{error}</div>}
      {loading ? <SkeletonRows count={4} /> : rfqs.length === 0 ? <div className="empty-state"><Send size={48} /><h3>No RFQs received</h3><p>New requests for quotation will appear here.</p></div> : (
        <div className="supplier-verification-list-card">
          {rfqs.map((rfq) => (
            <button type="button" className="dashboard-activity-row" key={rfq.id} onClick={() => setSelectedRfq(rfq)}>
              <span className="dashboard-activity-id">{rfq.rfq_no}</span>
              <span className="dashboard-activity-main"><strong>{rfq.subject}</strong><small>PR {rfq.purchase_request.pr_no || rfq.purchase_request.id}</small></span>
              <span className={`status-badge ${rfq.status === 'sent' ? 'status-open' : 'status-review'}`}>{rfq.status}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const SupplierRFQDetail = ({ rfq, supplierId, apiBaseUrl, onBack }) => {
  const [showQuotationForm, setShowQuotationForm] = React.useState(false)

  return (
    <div className="supplier-content-inner">
      <button type="button" className="back-link" onClick={onBack}><ChevronLeft size={18} /> Back</button>
      <div className="supplier-header"><h2>{rfq.rfq_no}</h2><p>{rfq.subject}</p></div>
      <div className="card rfq-review-card">
        <div className="detail-grid">
          <div><strong>PR No.</strong><span>{rfq.purchase_request.pr_no || `PR-${rfq.purchase_request.id}`}</span></div>
          <div><strong>Requesting Office / Entity</strong><span>{rfq.purchase_request.office_section || rfq.purchase_request.entity_name}</span></div>
          <div><strong>Category</strong><span>{rfq.purchase_request.category || 'N/A'}</span></div>
          <div><strong>Status</strong><span>{rfq.status}</span></div>
        </div>
        <h3>RFQ Message</h3>
        <div className="supplier-readonly-card" style={{ whiteSpace: 'pre-wrap' }}>{rfq.message}</div>
      </div>
      <div className="card rfq-review-card">
        <h3>Requested Items</h3>
        <div className="opportunity-table-wrapper"><table className="opportunity-table">
          <thead><tr><th>Unit</th><th>Description</th><th>Quantity</th><th>Category</th></tr></thead>
          <tbody>{rfq.purchase_request.items.map((item) => <tr key={item.id}><td>{item.unit || 'N/A'}</td><td>{item.item_description || 'N/A'}</td><td>{item.quantity}</td><td>{item.category || 'N/A'}</td></tr>)}</tbody>
        </table></div>
        {rfq.purchase_request.source_file_url && <p><strong>Attachment:</strong> <a href={rfq.purchase_request.source_file_url} target="_blank" rel="noreferrer">{rfq.purchase_request.source_filename || 'Original PR'}</a></p>}
      </div>
      <div className="form-actions">
        {rfq.status === 'sent' ? (
          <button type="button" className="btn-primary" onClick={() => setShowQuotationForm(true)}>Submit Quotation</button>
        ) : (
          <span className="supplier-subtext">A quotation has already been submitted for this RFQ.</span>
        )}
      </div>
      {showQuotationForm && <QuotationForm supplierId={supplierId} prId={rfq.purchase_request.id} rfqId={rfq.id} apiBaseUrl={apiBaseUrl} onClose={() => setShowQuotationForm(false)} onSuccess={onBack} />}
    </div>
  )
}

const SupplierNav = ({ currentPage, onPageChange, onLogout, navCollapsed, onToggleNav }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'opportunities', label: 'Opportunities', icon: BriefcaseBusiness },
    { id: 'quotations', label: 'Quotations', icon: FileText },
    { id: 'rfqs', label: 'RFQs', icon: Send },
    { id: 'profile', label: 'Profile', icon: Building2 },
    { id: 'notifications', label: 'Notifications', icon: Bell },
  ]

  return (
    <nav className="admin-navbar">
      <div className="admin-sidebar-header">
        <div className="admin-brand">
          <span className="admin-brand-mark">eP</span>
          <span className="admin-brand-copy">eProcure Supplier</span>
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
        <div className="admin-nav-items">
          {navItems.map((item) => {
            const IconComponent = item.icon
            return (
              <button
                key={item.id}
                className={`admin-nav-item ${currentPage === item.id ? 'active' : ''}`}
                onClick={() => onPageChange(item.id)}
                title={item.label}
              >
                <IconComponent size={14} />
                <span className="admin-nav-label">{item.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="admin-navbar-right">
        <div className="admin-user-card" aria-label="Logged in supplier">
          <div className="admin-user">Supplier Account</div>
          <div className="admin-user-email">Portal</div>
        </div>
        <button className="admin-nav-logout" onClick={onLogout} title="Log Out">
          <LogOut size={14} />
          <span className="admin-nav-label">Log Out</span>
        </button>
      </div>
    </nav>
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
          fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/dashboard/`),
          fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/opportunities/`)
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
          <div className="stat-icon" style={{ background: '#dcfce7' }}>
            <CheckCircle size={24} color="#16a34a" />
          </div>
          <div>
            <div className="stat-value">{summary?.awarded_quotations || 0}</div>
            <div className="stat-label">Awards Won</div>
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
            <div className="stat-value">{summary?.verification_status || 'Pending'}</div>
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
        const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/opportunities/`)
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
    return <OpportunityDetail opportunity={selectedOpp} onBack={() => setSelectedOpp(null)} apiBaseUrl={apiBaseUrl} supplierId={supplierId} />
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
                      {opp.quotation_status ? 'View Quotation' : 'View Details'}
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

const OpportunityDetail = ({ opportunity, onBack, apiBaseUrl, supplierId }) => {
  const [prDetails, setPrDetails] = React.useState(null)
  const [showQuotationForm, setShowQuotationForm] = React.useState(false)
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    const fetchDetails = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/pr/${opportunity.id}/details/`)
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

      {!opportunity.quotation_status && (
        <div className="detail-card">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowQuotationForm(true)}
          >
            <Send size={16} /> Submit Quotation
          </button>
        </div>
      )}

      {showQuotationForm && (
        <QuotationForm
          supplierId={supplierId}
          prId={opportunity.id}
          apiBaseUrl={apiBaseUrl}
          onClose={() => setShowQuotationForm(false)}
          onSuccess={() => {
            setShowQuotationForm(false)
            onBack()
          }}
        />
      )}
    </div>
  )
}

const QuotationForm = ({ supplierId, prId, rfqId, apiBaseUrl, onClose, onSuccess }) => {
  const [formData, setFormData] = React.useState({
    quoted_amount: '',
    estimated_delivery_days: '',
    warranty_months: '',
    remarks: '',
  })
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/quotations/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          purchase_request_id: prId,
          rfq_id: rfqId,
          quoted_amount: parseFloat(formData.quoted_amount),
          estimated_delivery_days: formData.estimated_delivery_days ? parseInt(formData.estimated_delivery_days) : null,
          warranty_months: formData.warranty_months ? parseInt(formData.warranty_months) : null,
        }),
      })

      if (response.ok) {
        alert('Quotation submitted successfully!')
        onSuccess()
      } else {
        const data = await response.json().catch(() => ({}))
        setError(data.error || data.message || `Failed to submit quotation (${response.status})`)
      }
    } catch (err) {
      setError(err?.message || 'Unable to reach the quotation service. Please try again.')
      console.error(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Submit Quotation</h3>
          <button type="button" className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <form className="modal-form" onSubmit={handleSubmit}>
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label htmlFor="quoted_amount">Quoted Amount *</label>
            <input
              type="number"
              id="quoted_amount"
              min="0"
              step="0.01"
              required
              value={formData.quoted_amount}
              onChange={(e) => setFormData({ ...formData, quoted_amount: e.target.value })}
              placeholder="Enter amount in PHP"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="estimated_delivery_days">Est. Delivery (days)</label>
              <input
                type="number"
                id="estimated_delivery_days"
                min="0"
                value={formData.estimated_delivery_days}
                onChange={(e) => setFormData({ ...formData, estimated_delivery_days: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label htmlFor="warranty_months">Warranty (months)</label>
              <input
                type="number"
                id="warranty_months"
                min="0"
                value={formData.warranty_months}
                onChange={(e) => setFormData({ ...formData, warranty_months: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="remarks">Remarks</label>
            <textarea
              id="remarks"
              rows="4"
              value={formData.remarks}
              onChange={(e) => setFormData({ ...formData, remarks: e.target.value })}
              placeholder="Any additional notes for the buyer..."
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit Quotation'}
            </button>
          </div>
        </form>
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
        const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/quotations/`)
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

const CompanyProfile = ({ supplierId, apiBaseUrl }) => {
  const [profile, setProfile] = React.useState(null)
  const [categories, setCategories] = React.useState([])
  const [selectedCategories, setSelectedCategories] = React.useState([])
  const [editMode, setEditMode] = React.useState(false)
  const [formData, setFormData] = React.useState({})
  const [saving, setSaving] = React.useState(false)
  const [message, setMessage] = React.useState(null)

  React.useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/profile/`)
        if (response.ok) {
          const data = await response.json()
          setProfile(data)
          setFormData(data)
          const categoriesResponse = await fetch(`${apiBaseUrl}/api/categories/`)
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
      const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/profile/`, {
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

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setEditMode(true)}
            >
              <Edit2 size={16} /> Edit Profile
            </button>
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
        const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/notifications/`)
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

  return (
    <div className="supplier-content-inner">
      <div className="supplier-header">
        <h2>Notifications</h2>
        <p>Stay updated on your quotations and procurement opportunities.</p>
      </div>

      {notifications.length > 0 ? (
        <div className="notifications-list">
          {notifications.map((notif) => (
            <div key={notif.id} className={`notification-item notification-${notif.type}`}>
              <div className="notification-icon">
                {notif.type === 'opportunity' && <BriefcaseBusiness size={20} />}
                {notif.type === 'quotation_submitted' && <CheckCircle size={20} />}
                {notif.type === 'quotation_review' && <Clock size={20} />}
                {notif.type === 'quotation_awarded' && <CheckCircle size={20} />}
                {notif.type === 'quotation_rejected' && <AlertCircle size={20} />}
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
                      const response = await fetch(`${apiBaseUrl}/api/suppliers/${supplierId}/rfqs/`)
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
    const stored = localStorage.getItem('eProcureUser')
    if (!stored) return null

    const parsed = JSON.parse(stored)
    if (!parsed || typeof parsed !== 'object' || typeof parsed.role !== 'string' || typeof parsed.username !== 'string') {
      localStorage.removeItem('eProcureUser')
      return null
    }

    return parsed
  } catch (error) {
    console.warn('Clearing malformed stored user:', error)
    localStorage.removeItem('eProcureUser')
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
    const handleStorage = () => setUser(getStoredUser())
    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [])

  return (
    <div className="app">
      {showMainNavbar && (
        <nav className="navbar">
          <div className="navbar-left navbar-brand-row">
            <Link to="/" className="navbar-logo-link">
              <img src={logo} alt="eProcure logo" className="navbar-logo" />
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
                  localStorage.removeItem('eProcureUser')
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

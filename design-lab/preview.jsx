// Design preview: renders the real app at a route as a given role, with the
// API answered from preview-data.js. Dev tool only, for screenshots of the
// signed-in portals; it changes nothing on the server and is not part of
// the production bundle (Vite only builds index.html).
//
//   /design-lab/preview.html?as=admin&path=/admin
//   /design-lab/preview.html?as=supplier&path=/supplier
//   /design-lab/preview.html?as=enduser&path=/enduser
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../src/index.css'
import '../src/styles/design-system.css'
import '../src/styles/tokens.css'
import '../src/styles/base.css'
import '../src/styles/components.css'
import '../src/styles/shell.css'
import '../src/styles/screens.css'
import '../src/styles/screens-admin.css'
import '../src/styles/screens-supplier.css'
import '../src/styles/screens-enduser.css'
import '../src/styles/screens-public.css'
import App from '../src/App.jsx'
import { dashboardSummary, manualRfqs, prDetails, prList, rfqGroups, supplierDashboard, supplierMatch, supplierOpportunities, supplierProfile, suppliers } from './preview-data.js'

const params = new URLSearchParams(window.location.search)
const role = params.get('as') || 'admin'
const path = params.get('path') || { admin: '/admin', supplier: '/supplier', enduser: '/enduser' }[role] || '/'

const users = {
  admin: { id: 1, role: 'admin', username: 'admintest', full_name: 'BAC Secretariat', email: '' },
  enduser: { id: 2, role: 'buyer', username: 'enduser1', full_name: 'Maria Lourdes Abellana', name: 'Maria Lourdes Abellana', email: 'mabellana@ctu.edu.ph' },
  supplier: { id: 3, role: 'supplier', username: 'quotes@islandsignage.ph', supplier_id: 327, supplier_status: 'Approved' },
}
const user = users[role]
sessionStorage.setItem('eProcureUser', JSON.stringify(user))
if (user.supplier_id) {
  sessionStorage.setItem('supplier_id', String(user.supplier_id))
  sessionStorage.setItem('supplier_status', user.supplier_status)
}

const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

// [method, pattern, handler(match, url, init)]
const routes = [
  ['GET', /\/api\/admin\/dashboard-summary\/$/, () => dashboardSummary],
  ['GET', /\/api\/pr\/list\/$/, (m, url) => {
    const by = url.searchParams.get('submitted_by')
    return by ? prList.filter((row) => row.submitted_by === by) : prList
  }],
  ['GET', /\/api\/suppliers\/$/, () => suppliers],
  ['GET', /\/api\/pr\/(\d+)\/details\/$/, (m) => prDetails(m[1])],
  ['GET', /\/api\/pr\/(\d+)\/changes\/$/, () => ({ changes: {}, events: [], changed_count: 0, original_available: true, locked: true })],
  ['GET', /\/api\/pr\/(\d+)\/posting\/$/, (m) => {
    const record = prList.find((row) => row.id === Number(m[1]))
    return { is_posted: Boolean(record?.is_posted), posted_at: record?.posted_at, posted_by: record?.posted_by || '', can_post: !record?.is_posted, post_problem: '', min_reason_length: 10, history: [] }
  }],
  ['GET', /\/api\/buyer-accounts\/$/, () => []],
  ['GET', /\/api\/rfqs\/responses\/$/, () => rfqGroups],
  ['GET', /\/api\/suppliers\/\d+\/profile\/$/, () => supplierProfile],
  ['GET', /\/api\/suppliers\/\d+\/dashboard\/$/, () => supplierDashboard],
  ['GET', /\/api\/suppliers\/\d+\/opportunities\/$/, () => supplierOpportunities],
  ['GET', /\/api\/suppliers\/\d+\/rfqs\/$/, () => ({ rfqs: [] })],
  ['GET', /\/api\/pr\/(\d+)\/supplier-match\/$/, () => supplierMatch],
  ['GET', /\/api\/pr\/(\d+)\/rfq\/$/, () => ({ rfqs: [] })],
  ['GET', /\/api\/manual-rfqs\/$/, () => manualRfqs],
  ['GET', /\/api\/pr\/next-number\/$/, () => ({ next_number: '2026-11-015' })],
  ['GET', /\/api\/procurement-modes\/$/, () => ({ modes: ['Small Value Procurement', 'Shopping', 'Negotiated Procurement'] })],
  ['GET', /\/api\/categories\/$/, () => [
    { id: 3, name: 'Advertising Agency Services', count: 2 }, { id: 4, name: 'Information Technology Parts & Peripheral', count: 1 }, { id: 5, name: 'Janitorial Supplies', count: 3 },
  ]],
]

const realFetch = window.fetch.bind(window)
window.fetch = async (input, init = {}) => {
  const raw = typeof input === 'string' ? input : input.url
  const url = new URL(raw, window.location.origin)
  if (!url.pathname.startsWith('/api/')) return realFetch(input, init)
  const method = (init.method || 'GET').toUpperCase()
  for (const [routeMethod, pattern, handler] of routes) {
    const match = url.pathname.match(pattern)
    if (routeMethod === method && match) return json(handler(match, url, init))
  }
  // Anything else: an empty, successful answer.
  return json(method === 'GET' ? {} : { success: true })
}

window.history.replaceState(null, '', path)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

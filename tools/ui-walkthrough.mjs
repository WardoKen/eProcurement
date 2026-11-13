// Real-browser walkthrough of the production build: every screen per role at
// 1280px and 360px, with fixture API responses (no backend needed). Reports
// horizontal page overflow and axe-core WCAG 2.0-2.2 A/AA violations, and
// saves screenshots.
//
// Usage (dependencies are not added to package.json):
//   npm run build
//   npm i --no-save puppeteer-core@24 axe-core@4
//   npx vite preview --port 4173 --strictPort     # in another terminal
//   node tools/ui-walkthrough.mjs . tools/ui-walkthrough-out
// Set CHROME_PATH if Chrome is not at the default Windows location.
import puppeteer from 'puppeteer-core'
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { resolve } from 'node:path'

const require = createRequire(import.meta.url)
const axePath = require.resolve('axe-core/axe.min.js')
const projectRoot = process.argv[2]
const outDir = process.argv[3]
const fx = await import(pathToFileURL(resolve(projectRoot, 'src/test/fixtures.js')).href)
mkdirSync(outDir, { recursive: true })

const APP = 'http://localhost:4173'
const API = 'http://127.0.0.1:8000'

const manyPrs = Array.from({ length: 14 }, (_, i) => ({
  ...fx.numberedPr, id: 100 + i, pr_no: `2026-11-${String(i + 1).padStart(3, '0')}`,
  entity_name: i % 2 ? 'College of Engineering and Architecture' : 'Cebu Technological University', status: i < 3 ? 'matched' : 'in_review',
}))
const rfqRow = { ...fx.supplierRfq, supplier: { id: 7, company_name: 'Acme Supplies, Inc.', email: 'sales@acme.ph' }, sent_at: '2026-11-03T00:00:00Z', has_response: false, status_label: 'Awaiting Response', created_at: '2026-11-02T00:00:00Z' }

const routes = {
  '/api/admin/dashboard-summary/': fx.dashboardSummary,
  '/api/pr/list/': [fx.unnumberedPr, ...manyPrs],
  '/api/suppliers/': [fx.supplierRow, { ...fx.supplierRow, id: 8, company_name: 'Bravo Office Trading', status: 'Approved' }],
  '/api/suppliers/7/profile/': { ...fx.supplierProfile, status: 'Approved', nature_of_business: 'Trading', goods_services: 'Computers' },
  '/api/buyer-accounts/': [{ id: 5, full_name: 'Ana Cruz', username: 'ana.cruz', email: 'ana@ctu.edu.ph', unit_office: 'ICT Office' }],
  '/api/admin/pr-number-format/': { prefix: '', date_granularity: 'year_month', separator: '-', sequence_digits: 3, reset_period: 'monthly', next_sequence: 4 },
  '/api/admin/pr-notification-settings/': { enabled: true, notify_in_review: true, notify_matched: true, notify_approved: true, notify_rejected: true, mute_automatic_transitions: false },
  '/api/rfqs/responses/': { purchase_requests: [{ purchase_request: { id: 43, pr_no: '2026-11-001', category: 'IT Equipment' }, rfq_summary: { status: 'awaiting_responses', sent: 1, responses_received: 0, awaiting_response: 1, category_count: 1 }, rfqs: [rfqRow], categories: [{ category: 'IT Equipment', rfqs: [rfqRow], rfq_count: 1, response_count: 0, item_count: 1 }] }] },
  '/api/manual-rfqs/': { rfqs: [{ id: 31, manual_supplier_name: "Juan's Aircon Services", quotation_no: '2026-022', rfq_no: 'RFQ-2026-002', status: 'sent', status_label: 'Awaiting Response', purchase_request: { id: 43, pr_no: '2026-11-001' }, created_at: '2026-11-03T00:00:00Z', sent_at: '2026-11-03T00:00:00Z' }] },
  '/api/procurement-modes/': { modes: ['Small Value Procurement', 'Shopping', 'Negotiated Procurement', 'Competitive Bidding'] },
  '/api/pr/100/supplier-match/': { ...fx.supplierMatch, pr: { pr_no: '2026-11-002' } },
  '/api/pr/100/details/': { ...fx.prDetails, pr_no: '2026-11-002' },
  '/api/pr/100/rfq/': { rfqs: [] },
  '/api/pr/next-number/': { pr_no: '2026-11-015' },
  '/api/suppliers/7/dashboard/': { company_name: 'Acme Supplies, Inc.', open_opportunities: 2, submitted_quotations: 1, pending_quotations: 1, rejected_quotations: 0, verification_status: 'Approved' },
  '/api/suppliers/7/opportunities/': { opportunities: [{ id: 1, pr_no: '2026-11-001', office_section: 'ICT Office', entity_name: 'CTU', purpose: 'Laptops for the computer laboratory', category: 'IT Equipment', grand_total: 2000, status: 'matched' }] },
  '/api/suppliers/7/rfqs/': { rfqs: [fx.supplierRfq] },
  '/api/suppliers/7/quotations/': { quotations: [{ id: 1, pr_no: '2026-11-001', created_at: '2026-11-02T00:00:00Z', quoted_amount: 1900, status: 'under_review', estimated_delivery_days: 14, warranty_months: 12 }] },
  '/api/suppliers/7/notifications/': { notifications: [{ id: 1, type: 'rfq_received', title: 'New RFQ received', message: 'RFQ-2026-001 for PR 2026-11-001', created_at: new Date().toISOString(), related_rfq_id: 9 }] },
  '/api/categories/': [{ id: 1, name: 'IT Equipment', count: 2 }, { id: 2, name: 'Janitorial Services', count: 0 }],
}

// [role user, path, label, steps] — steps are sidebar/button labels to click in order.
const scenarios = [
  [null, '/', 'public-home'],
  [null, '/login', 'public-login'],
  [null, '/faq', 'public-faq'],
  [null, '/forgot-password', 'public-forgot'],
  [null, '/reset-password?token=abc', 'public-reset'],
  [null, '/supplier/register', 'public-register'],
  [fx.adminUser, '/admin', 'admin-dashboard'],
  [fx.adminUser, '/admin', 'admin-pr-monitoring', ['PR Review & Monitoring']],
  [fx.adminUser, '/admin', 'admin-supplier-matching', ['PR Review & Monitoring', '#Continue Matching']],
  [fx.adminUser, '/admin', 'admin-rfq-prep', ['PR Review & Monitoring', '#Continue Matching', '#Request Quotation']],
  [fx.adminUser, '/admin', 'admin-rfq-management', ['RFQ Management']],
  [fx.adminUser, '/admin', 'admin-manual-rfqs', ['Manual RFQs']],
  [fx.adminUser, '/admin', 'admin-suppliers', ['Supplier Management']],
  [fx.adminUser, '/admin', 'admin-supplier-review', ['Supplier Management', '#View details for Acme Supplies, Inc.']],
  [fx.adminUser, '/admin', 'admin-end-users', ['End User Accounts']],
  [fx.adminUser, '/admin', 'admin-pr-numbering', ['PR Numbering']],
  [fx.adminUser, '/admin', 'admin-pr-notifications', ['PR Notifications']],
  [fx.buyerUser, '/buyer', 'enduser-dashboard'],
  [fx.buyerUser, '/buyer', 'enduser-live-status', ['Live Status']],
  [fx.supplierUser, '/supplier', 'supplier-dashboard'],
  [fx.supplierUser, '/supplier', 'supplier-opportunities', ['Opportunities']],
  [fx.supplierUser, '/supplier', 'supplier-rfqs', ['RFQs']],
  [fx.supplierUser, '/supplier', 'supplier-rfq-detail', ['RFQs', '#View RFQ RFQ-2026-001']],
  [fx.supplierUser, '/supplier', 'supplier-quotations', ['Quotations']],
  [fx.supplierUser, '/supplier', 'supplier-profile', ['Profile']],
  [fx.supplierUser, '/supplier', 'supplier-notifications', ['Notifications']],
  [{ ...fx.supplierUser, supplier_status: 'Pending Review' }, '/supplier', 'supplier-pending-rfqs', ['RFQs']],
]

const browser = await puppeteer.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: true,
  args: ['--no-first-run', '--disable-extensions'],
})

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const results = []

async function clickByName(page, name) {
  // '#Label' = any button whose accessible-ish name (aria-label or text) matches; otherwise a sidebar item.
  const exact = name.startsWith('#') ? name.slice(1) : name
  const clicked = await page.evaluate((label, sidebar) => {
    const candidates = [...document.querySelectorAll(sidebar ? '.admin-nav-item' : 'button')]
    const match = candidates.find((el) => (el.getAttribute('aria-label') || el.textContent).trim() === label)
      || candidates.find((el) => (el.getAttribute('aria-label') || el.textContent).trim().startsWith(label))
    if (!match) return false
    match.click()
    return true
  }, exact, !name.startsWith('#'))
  if (!clicked) throw new Error(`Could not find control "${exact}"`)
  await sleep(450)
}

async function measure(page, label, width) {
  const overflow = await page.evaluate(() => {
    const vw = window.innerWidth
    const docWidth = document.documentElement.scrollWidth
    const offenders = []
    if (docWidth > vw + 1) {
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect()
        if (r.width > 0 && r.right > vw + 1) {
          // Skip descendants of horizontally scrollable containers (intended).
          let p = el.parentElement, scrollable = false
          while (p && p !== document.body) {
            const ox = getComputedStyle(p).overflowX
            if ((ox === 'auto' || ox === 'scroll') && p.scrollWidth > p.clientWidth) { scrollable = true; break }
            p = p.parentElement
          }
          if (!scrollable) offenders.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ').slice(0, 2).join('.')} (${Math.round(r.right)}px)`)
        }
        if (offenders.length >= 4) break
      }
    }
    return { docWidth, vw, offenders }
  })
  await page.addScriptTag({ path: axePath })
  const axe = await page.evaluate(async () => {
    const res = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] }, resultTypes: ['violations'] })
    return res.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0]?.target?.join(' '), summary: v.nodes[0]?.failureSummary?.split('\n')[1]?.trim() }))
  })
  await page.screenshot({ path: `${outDir}/${label}-${width}.png`, fullPage: false })
  return { overflow, axe }
}

for (const [user, path, label, steps = []] of scenarios) {
  const page = await browser.newPage()
  const consoleErrors = []
  page.on('pageerror', (err) => consoleErrors.push(String(err.message || err)))
  await page.setRequestInterception(true)
  page.on('request', (req) => {
    const url = req.url()
    if (url.startsWith(API)) {
      const parsed = new URL(url)
      const body = routes[parsed.pathname]
      if (req.method() === 'OPTIONS') return req.respond({ status: 204, headers: { 'Access-Control-Allow-Origin': APP, 'Access-Control-Allow-Credentials': 'true', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' } })
      return req.respond({
        status: body === undefined ? 404 : 200,
        contentType: 'application/json',
        headers: { 'Access-Control-Allow-Origin': APP, 'Access-Control-Allow-Credentials': 'true' },
        body: JSON.stringify(body ?? { message: 'not mocked' }),
      })
    }
    if (url.includes('fonts.googleapis') || url.includes('fonts.gstatic') || url.includes('recaptcha')) return req.abort()
    return req.continue()
  })
  if (user) {
    await page.evaluateOnNewDocument((u) => {
      sessionStorage.setItem('eProcureUser', JSON.stringify(u))
      if (u.supplier_id) sessionStorage.setItem('supplier_id', String(u.supplier_id))
      if (u.supplier_status) sessionStorage.setItem('supplier_status', u.supplier_status)
    }, user)
  }
  const entry = { label }
  try {
    await page.setViewport({ width: 1280, height: 900 })
    await page.goto(`${APP}${path}`, { waitUntil: 'networkidle0' })
    await sleep(400)
    for (const step of steps) await clickByName(page, step)
    entry.desktop = await measure(page, label, 1280)
    await page.setViewport({ width: 360, height: 780 })
    await sleep(400)
    entry.mobile = await measure(page, label, 360)
  } catch (err) {
    entry.error = String(err.message || err)
  }
  entry.pageErrors = consoleErrors
  results.push(entry)
  await page.close()
}

await browser.close()
writeFileSync(`${outDir}/results.json`, JSON.stringify(results, null, 2))

// Summary
for (const r of results) {
  const flag = (m) => (m ? `${m.overflow.offenders.length ? `OVERFLOW ${m.overflow.docWidth}px: ${m.overflow.offenders.join(', ')}` : 'no overflow'}; axe ${m.axe.length ? m.axe.map((v) => `${v.id}(${v.impact},${v.nodes})`).join(' ') : 'clean'}` : '-')
  console.log(`${r.label}${r.error ? `  ERROR ${r.error}` : ''}${r.pageErrors.length ? `  PAGEERR ${r.pageErrors[0]}` : ''}`)
  console.log(`   1280: ${flag(r.desktop)}`)
  console.log(`    360: ${flag(r.mobile)}`)
}

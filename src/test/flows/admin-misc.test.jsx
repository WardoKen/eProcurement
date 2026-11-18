// Process 11 (reporting dashboard), plus the remaining Admin forms: End User
// accounts, PR numbering and PR notification settings. Also the End User
// Live Status load.
import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, buyerUser, dashboardSummary, numberedPr, supplierRow } from '../fixtures'

const baseRoutes = {
  'GET /api/admin/dashboard-summary/': { json: dashboardSummary },
  'GET /api/pr/list/': { json: [numberedPr] },
  'GET /api/suppliers/': { json: [supplierRow] },
}

describe('admin dashboard', () => {
  it('loads the summary, recent PRs and registrations without writing anything', async () => {
    signIn(adminUser)
    const api = installApi(baseRoutes)
    renderAt('/admin')

    // RFQ response rate 2 of 5 = 40%.
    const kpis = await screen.findByRole('list', { name: 'Key figures' })
    expect(within(kpis).getByText('RFQ response rate').closest('li')).toHaveTextContent('40%')
    expect((await screen.findAllByText('Acme Supplies, Inc.')).length).toBeGreaterThan(0)
    const gets = new Set(api.calls.map((call) => `${call.method} ${call.path}`))
    expect(gets).toEqual(new Set([
      'GET /api/admin/dashboard-summary/',
      'GET /api/pr/list/',
      'GET /api/suppliers/',
    ]))
  })

  it('shows zero/empty states when there is no data', async () => {
    signIn(adminUser)
    installApi({
      'GET /api/admin/dashboard-summary/': { json: {} },
      'GET /api/pr/list/': { json: [] },
      'GET /api/suppliers/': { json: [] },
    })
    renderAt('/admin')

    expect(await screen.findByText(/no suppliers registered yet/i)).toBeInTheDocument()
    expect(screen.getByText(/no purchase requests found/i)).toBeInTheDocument()
  })
})

describe('end user accounts', () => {
  it('creates an End User account', async () => {
    signIn(adminUser)
    const api = installApi({
      ...baseRoutes,
      'GET /api/buyer-accounts/': { json: [] },
      'POST /api/register/': { json: { success: true, welcome_email_sent: true, email: 'ana@ctu.edu.ph' } },
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /end user accounts/i })[0])

    // No password fields: the End User sets their own from the setup email.
    expect(await screen.findByText(/one-time link to set their own password/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()

    await user.type(screen.getByPlaceholderText('End User name'), ' Ana Cruz ')
    await user.type(screen.getByPlaceholderText('enduser.username'), 'ana.cruz')
    await user.type(screen.getByPlaceholderText('enduser@office.edu'), 'ana@ctu.edu.ph')
    await user.type(screen.getByPlaceholderText('Procurement Office'), 'ICT Office')
    await user.click(screen.getByRole('button', { name: /create end user account/i }))

    await waitFor(() => expect(api.find('POST', '/api/register/')).toHaveLength(1))
    expect(api.find('POST', '/api/register/')[0].body).toEqual({
      username: 'ana.cruz',
      fullName: 'Ana Cruz',
      email: 'ana@ctu.edu.ph',
      unitOffice: 'ICT Office',
      role: 'buyer',
    })
    expect(await screen.findByText('End User account created. A setup email was sent to ana@ctu.edu.ph.')).toBeInTheDocument()
  })

  it('tells the admin when the setup email could not be sent', async () => {
    signIn(adminUser)
    installApi({
      ...baseRoutes,
      'GET /api/buyer-accounts/': { json: [] },
      'POST /api/register/': { status: 201, json: { success: true, welcome_email_sent: false, email: 'ana@ctu.edu.ph' } },
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /end user accounts/i })[0])

    await user.type(await screen.findByPlaceholderText('End User name'), 'Ana Cruz')
    await user.type(screen.getByPlaceholderText('enduser.username'), 'ana.cruz')
    await user.type(screen.getByPlaceholderText('enduser@office.edu'), 'ana@ctu.edu.ph')
    await user.type(screen.getByPlaceholderText('Procurement Office'), 'ICT Office')
    await user.click(screen.getByRole('button', { name: /create end user account/i }))

    expect(await screen.findByText(/the setup email to ana@ctu\.edu\.ph could not be sent/i)).toBeInTheDocument()
  })

  it('deletes an account after confirmation', async () => {
    signIn(adminUser)
    const api = installApi({
      ...baseRoutes,
      'GET /api/buyer-accounts/': { json: [{ id: 5, full_name: 'Ana Cruz', username: 'ana.cruz', email: 'ana@ctu.edu.ph', unit_office: 'ICT Office' }] },
      'DELETE /api/buyer-accounts/5/': { json: {} },
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /end user accounts/i })[0])

    await user.click(await screen.findByRole('button', { name: /^delete/i }))
    const dialog = await screen.findByRole('alertdialog', { name: /delete end user account/i })
    await user.click(within(dialog).getByRole('button', { name: /delete account/i }))

    await waitFor(() => expect(api.find('DELETE', '/api/buyer-accounts/5/')).toHaveLength(1))
  })
})

describe('PR settings', () => {
  it('saves the PR numbering format', async () => {
    signIn(adminUser)
    const format = { prefix: '', date_granularity: 'year_month', separator: '-', sequence_digits: 3, reset_period: 'monthly', next_sequence: 4 }
    const api = installApi({
      ...baseRoutes,
      'GET /api/admin/pr-number-format/': { json: format },
      'PATCH /api/admin/pr-number-format/': ({ body }) => ({ json: { ...format, ...body } }),
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /pr numbering/i })[0])

    await user.type(await screen.findByPlaceholderText('e.g. CTU'), 'CTU')
    await user.click(screen.getByRole('button', { name: /save pr numbering settings/i }))

    await waitFor(() => expect(api.find('PATCH', '/api/admin/pr-number-format/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/admin/pr-number-format/')[0].body).toEqual({
      prefix: 'CTU', date_granularity: 'year_month', separator: '-', sequence_digits: 3, reset_period: 'monthly',
    })
  })

  it('saves the PR notification settings', async () => {
    signIn(adminUser)
    const settings = { enabled: true, notify_submitted: true, notify_in_review: true, notify_matched: true, notify_approved: true, notify_rejected: true, mute_automatic_transitions: false }
    const api = installApi({
      ...baseRoutes,
      'GET /api/admin/pr-notification-settings/': { json: settings },
      'PATCH /api/admin/pr-notification-settings/': ({ body }) => ({ json: body }),
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /pr notifications/i })[0])

    await user.click(await screen.findByRole('checkbox', { name: /^matched$/i }))
    await user.click(screen.getByRole('button', { name: /save pr notification settings/i }))

    await waitFor(() => expect(api.find('PATCH', '/api/admin/pr-notification-settings/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/admin/pr-notification-settings/')[0].body).toEqual({ ...settings, notify_matched: false })
  })
})

describe('end user live status', () => {
  it('loads only the signed-in End User\'s Purchase Requests', async () => {
    signIn(buyerUser)
    const api = installApi({
      'GET /api/pr/next-number/': { json: { pr_no: '2026-11-001' } },
      'GET /api/pr/list/': { json: [{ ...numberedPr, display_stage: 'supplier_matching', display_status: 'Supplier Matching' }] },
    })
    const { user } = renderAt('/enduser')

    await user.click(screen.getAllByRole('button', { name: /live status/i })[0])

    expect((await screen.findAllByText('2026-11-001')).length).toBeGreaterThan(0)
    expect(api.find('GET', '/api/pr/list/?submitted_by=enduser1')).toHaveLength(1)
  })
})

describe('end user dashboard', () => {
  const myPrs = [
    { ...numberedPr, display_stage: 'under_review', display_status: 'Under BAC Review' },
    { ...numberedPr, id: 50, pr_no: '2026-10-007', display_stage: 'rfq_sent', display_status: 'RFQ Sent' },
    { ...numberedPr, id: 51, pr_no: '2026-09-003', display_stage: 'completed', display_status: 'Completed' },
  ]

  it('greets the End User by name and sums their PRs by who has them', async () => {
    signIn(buyerUser)
    installApi({ 'GET /api/pr/list/': { json: myPrs } })
    renderAt('/enduser')

    expect(await screen.findByRole('heading', { level: 1, name: 'Welcome back, Ana Cruz' })).toBeInTheDocument()
    const kpis = await screen.findByRole('list', { name: 'Key figures' })
    const tile = (label) => within(kpis).getByText(label).closest('li')
    expect(tile('Submitted')).toHaveTextContent('3PRs')
    expect(tile('With the BAC')).toHaveTextContent('1PR')
    expect(tile('Out for quotation')).toHaveTextContent('1PR')
    expect(tile('Completed')).toHaveTextContent('1PR')
    expect(screen.getByRole('table')).toHaveTextContent('2026-10-007')
  })

  it('offers a way to submit when nothing has been submitted yet', async () => {
    signIn(buyerUser)
    installApi({ 'GET /api/pr/list/': { json: [] }, 'GET /api/pr/next-number/': { json: { pr_no: '2026-11-001' } } })
    const { user } = renderAt('/enduser')

    await user.click(await screen.findByRole('button', { name: /submit your first pr/i }))
    expect(screen.getByRole('heading', { level: 1, name: 'Submit a Purchase Request' })).toBeInTheDocument()
  })

  it('the old /buyer address opens the End User portal', async () => {
    signIn(buyerUser)
    installApi({ 'GET /api/pr/list/': { json: [] } })
    renderAt('/buyer')

    await waitFor(() => expect(window.location.pathname).toBe('/enduser'))
    expect(await screen.findByRole('heading', { level: 1, name: /welcome back/i })).toBeInTheDocument()
  })

  it('groups navigation by task, with help pages one click away', async () => {
    signIn(buyerUser)
    installApi({ 'GET /api/pr/list/': { json: [] } })
    const { user } = renderAt('/enduser')

    const nav = screen.getByRole('navigation', { name: 'End user portal navigation' })
    expect(within(nav).getByRole('group', { name: 'Purchase Requests' })).toHaveTextContent('Submit a PR')
    await user.click(within(nav).getByRole('button', { name: 'Help & FAQ' }))
    await waitFor(() => expect(window.location.pathname).toBe('/faq'))
  })
})

describe('end user live status records', () => {
  it('shows each Purchase Request as a collapsible record, newest open', async () => {
    signIn(buyerUser)
    installApi({
      'GET /api/pr/next-number/': { json: { pr_no: '2026-11-001' } },
      'GET /api/pr/list/': { json: [
        { ...numberedPr, display_stage: 'supplier_matching', display_status: 'Supplier Matching' },
        { ...numberedPr, id: 50, pr_no: '2026-10-007', display_stage: 'under_review', display_status: 'Under BAC Review' },
      ] },
    })
    const { user } = renderAt('/enduser')
    await user.click(screen.getAllByRole('button', { name: /live status/i })[0])

    const newest = await screen.findByRole('button', { name: /2026-11-001/ })
    const older = screen.getByRole('button', { name: /2026-10-007/ })
    expect(newest).toHaveAttribute('aria-expanded', 'true')
    expect(older).toHaveAttribute('aria-expanded', 'false')
    expect(document.getElementById(older.getAttribute('aria-controls'))).not.toBeVisible()

    await user.click(older)
    expect(older).toHaveAttribute('aria-expanded', 'true')
    expect(document.getElementById(older.getAttribute('aria-controls'))).toBeVisible()

    await user.click(newest)
    expect(newest).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('dashboard KPI tiles', () => {
  it('labels each figure with its unit', async () => {
    signIn(adminUser)
    installApi({ ...baseRoutes, 'GET /api/pr/list/': { json: [numberedPr, { ...numberedPr, id: 50, pr_no: '' }] } })
    renderAt('/admin')

    const kpis = await screen.findByRole('list', { name: 'Key figures' })
    const tile = (label) => within(kpis).getByText(label).closest('li')
    expect(tile('Purchase Requests')).toHaveTextContent('4PRs')
    expect(tile('Purchase Requests')).toHaveTextContent('1 awaiting a PR number')
    expect(tile('Registered suppliers')).toHaveTextContent('2 approved')
    expect(tile('RFQs sent')).toHaveTextContent('5RFQs')
    expect(tile('RFQ response rate')).toHaveTextContent('40%')
  })

  it('lists the work waiting on the BAC with a way to act on each item', async () => {
    signIn(adminUser)
    installApi({ ...baseRoutes, 'GET /api/pr/list/': { json: [numberedPr, { ...numberedPr, id: 50, pr_no: '' }] } })
    const { user } = renderAt('/admin')

    const queue = await screen.findByRole('region', { name: 'Waiting on the BAC' })
    expect(within(queue).getByText('1 Purchase Request needs a PR number')).toBeInTheDocument()
    expect(within(queue).getByText('1 supplier registration is waiting for evaluation')).toBeInTheDocument()
    // 5 RFQs sent, 2 with a quotation.
    expect(within(queue).getByText('3 RFQs are still awaiting a quotation')).toBeInTheDocument()

    await user.click(within(queue).getByRole('button', { name: 'Review PRs' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Purchase Requests' })).toBeInTheDocument()
  })

  it('reads as "nothing yet" on an empty system', async () => {
    signIn(adminUser)
    installApi({
      'GET /api/admin/dashboard-summary/': { json: {} },
      'GET /api/pr/list/': { json: [] },
      'GET /api/suppliers/': { json: [] },
    })
    renderAt('/admin')

    const kpis = await screen.findByRole('list', { name: 'Key figures' })
    expect(within(kpis).getByText('No Purchase Requests submitted yet.')).toBeInTheDocument()
    expect(within(kpis).getByText('Available once RFQs are sent.')).toBeInTheDocument()
  })

  it('supplier dashboard shows a retryable error instead of silent zeros', async () => {
    signIn({ role: 'supplier', username: 'acme', supplier_id: 7, supplier_status: 'Approved' })
    const api = installApi({
      'GET /api/suppliers/7/dashboard/': { status: 500, json: {} },
      'GET /api/suppliers/7/opportunities/': { json: { opportunities: [] } },
    })
    const { user } = renderAt('/supplier')

    expect(await screen.findByText(/dashboard figures could not be loaded/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /try again/i }))
    await waitFor(() => expect(api.find('GET', '/api/suppliers/7/dashboard/')).toHaveLength(2))
  })
})

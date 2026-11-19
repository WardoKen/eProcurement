// Processes 1, 8, 11 for suppliers: registration, quotation (completed RFQ)
// submission, and the supplier dashboard.
import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { installApi, pdfFile, renderAt, signIn } from '../harness'
import { prDetails, supplierRfq, supplierUser } from '../fixtures'

const portalRoutes = (overrides = {}) => ({
  'GET /api/suppliers/7/profile/': { json: { id: 7, company_name: 'Acme Supplies, Inc.', email: 'sales@acme.ph', status: 'Approved', documents: [] } },
  'GET /api/suppliers/7/dashboard/': { json: { company_name: 'Acme Supplies, Inc.', open_opportunities: 2, submitted_quotations: 1, pending_quotations: 1, rejected_quotations: 0, verification_status: 'Approved' } },
  'GET /api/suppliers/7/opportunities/': { json: { opportunities: [] } },
  'GET /api/suppliers/7/rfqs/': { json: { rfqs: [supplierRfq] } },
  'POST /api/suppliers/7/rfqs/9/response/': {
    json: { ...supplierRfq, status: 'quotation_received', submitted_pdf_url: '/media/completed.pdf', submitted_filename: 'completed.pdf', submitted_at: '2026-11-05T09:00:00Z', replaced: false },
  },
  ...overrides,
})

describe('supplier portal', () => {
  it('dashboard loads the summary and matching opportunities', async () => {
    signIn(supplierUser)
    const api = installApi(portalRoutes())
    renderAt('/supplier')

    await screen.findByText(/acme supplies/i, { selector: '.portal-head-name' })
    const gets = api.calls.filter((call) => call.method === 'GET').map((call) => call.path)
    expect(gets).toEqual(expect.arrayContaining([
      '/api/suppliers/7/dashboard/',
      '/api/suppliers/7/opportunities/',
      '/api/suppliers/7/profile/',
    ]))
    expect(api.mutations()).toHaveLength(0)
  })

  it('uploads the completed RFQ as the quotation submission', async () => {
    signIn(supplierUser)
    const api = installApi(portalRoutes())
    const { user } = renderAt('/supplier')

    await user.click(screen.getAllByRole('button', { name: /^rfqs$/i })[0])
    await user.click(await screen.findByRole('button', { name: /view rfq/i }))
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, pdfFile('completed.pdf'))
    await user.click(screen.getByRole('button', { name: /upload completed rfq/i }))

    expect((await screen.findAllByText(/completed rfq uploaded successfully/i)).length).toBeGreaterThan(0)
    expect(api.mutations()).toEqual([
      { method: 'POST', path: '/api/suppliers/7/rfqs/9/response/', body: [['file', 'file:completed.pdf']] },
    ])
  })

  it('sorts the RFQ list from the Sort by menu, newest first by default', async () => {
    const rfqs = [
      { ...supplierRfq, id: 1, rfq_no: 'RFQ-2026-11-001:01', status: 'completed', sent_at: '2026-11-01T08:00:00Z', purchase_request: { ...supplierRfq.purchase_request, pr_no: '2026-11-001' } },
      { ...supplierRfq, id: 2, rfq_no: 'RFQ-2026-11-003:01', status: 'quotation_received', sent_at: '2026-11-10T08:00:00Z', purchase_request: { ...supplierRfq.purchase_request, pr_no: '2026-11-003' } },
      { ...supplierRfq, id: 3, rfq_no: 'RFQ-2026-11-002:01', status: 'sent', sent_at: '2026-11-05T08:00:00Z', purchase_request: { ...supplierRfq.purchase_request, pr_no: '2026-11-002' } },
    ]
    signIn(supplierUser)
    installApi(portalRoutes({ 'GET /api/suppliers/7/rfqs/': { json: { rfqs } } }))
    const { user } = renderAt('/supplier')

    await user.click(screen.getAllByRole('button', { name: /^rfqs$/i })[0])
    const order = () => screen.getAllByRole('heading', { level: 3, name: /^RFQ-/ }).map((heading) => heading.textContent)
    await waitFor(() => expect(order()).toEqual(['RFQ-2026-11-003:01', 'RFQ-2026-11-002:01', 'RFQ-2026-11-001:01']))

    const sortMenu = screen.getByLabelText(/sort by/i)
    await user.selectOptions(sortMenu, 'Oldest first')
    expect(order()).toEqual(['RFQ-2026-11-001:01', 'RFQ-2026-11-002:01', 'RFQ-2026-11-003:01'])

    await user.selectOptions(sortMenu, 'Awaiting quotation first')
    expect(order()).toEqual(['RFQ-2026-11-002:01', 'RFQ-2026-11-003:01', 'RFQ-2026-11-001:01'])

    await user.selectOptions(sortMenu, 'RFQ No. (Z–A)')
    expect(order()).toEqual(['RFQ-2026-11-003:01', 'RFQ-2026-11-002:01', 'RFQ-2026-11-001:01'])
  })

  it('rejects a non-PDF completed RFQ before any request', async () => {
    signIn(supplierUser)
    const api = installApi(portalRoutes())
    const { user } = renderAt('/supplier')

    await user.click(screen.getAllByRole('button', { name: /^rfqs$/i })[0])
    await user.click(await screen.findByRole('button', { name: /view rfq/i }))
    const input = document.querySelector('input[type="file"]')
    // Bypasses the input's accept filter, as a drag-and-drop or OS picker can.
    fireEvent.change(input, { target: { files: [new File(['img'], 'photo.png', { type: 'image/png' })] } })

    expect((await screen.findAllByText(/must be uploaded as a pdf/i)).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /upload completed rfq/i })).toBeDisabled()
    expect(api.mutations()).toHaveLength(0)
  })

  it('edits the profile phone and TIN with grouping, keeping a legacy phone', async () => {
    signIn(supplierUser)
    // Not yet approved: the TIN is still editable (it locks on approval).
    const api = installApi(portalRoutes({
      'GET /api/suppliers/7/profile/': { json: { id: 7, company_name: 'Acme Supplies, Inc.', email: 'sales@acme.ph', status: 'Pending Review', documents: [], contact_phone: '0917-123-4567', tin: '123456789' } },
      'GET /api/categories/': { json: [] },
      'PATCH /api/suppliers/7/profile/': { json: { success: true, supplier: { id: 7, company_name: 'Acme Supplies, Inc.' } } },
    }))
    const { user } = renderAt('/supplier')

    await user.click(screen.getAllByRole('button', { name: /^profile$/i })[0])
    await user.click(await screen.findByRole('button', { name: /edit profile/i }))

    const phone = screen.getByLabelText(/^phone$/i)
    const tin = screen.getByLabelText(/tin number/i)
    expect(phone).toHaveValue('917 123 4567')
    expect(screen.getByLabelText(/country calling code/i)).toHaveValue('PH')
    expect(tin).toHaveValue('123-456-789')

    await user.type(tin, '0')
    await user.click(screen.getByRole('button', { name: /save changes/i }))
    expect(await screen.findByText(/enter a 9-digit tin/i)).toBeInTheDocument()
    expect(tin).toHaveAttribute('aria-invalid', 'true')
    expect(api.mutations()).toHaveLength(0)

    await user.type(tin, '00')
    expect(tin).toHaveValue('123-456-789-000')
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => expect(api.find('PATCH', '/api/suppliers/7/profile/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/suppliers/7/profile/')[0].body).toMatchObject({ contact_phone: '+63 917 123 4567', tin: '123-456-789-000' })
  })

  const approvedProfile = {
    id: 7, company_name: 'Acme Supplies, Inc.', business_type: 'Corporation', tin: '123-456-789-000',
    email: 'sales@acme.ph', contact_phone: '+63 917 123 4567', contact_person: 'Rep',
    status: 'Approved', documents: [], category_ids: [1], categories: ['Office Supplies'],
  }
  const profileCategories = [{ id: 1, name: 'Office Supplies' }, { id: 2, name: 'Janitorial Supplies' }]

  it('an approved supplier sees company name, TIN and business type as read-only', async () => {
    signIn(supplierUser)
    const api = installApi(portalRoutes({
      'GET /api/suppliers/7/profile/': { json: approvedProfile },
      'GET /api/categories/': { json: profileCategories },
      'PATCH /api/suppliers/7/profile/': { json: { success: true, supplier: { ...approvedProfile, contact_person: 'New Rep' } } },
    }))
    const { user } = renderAt('/supplier')

    await user.click(screen.getAllByRole('button', { name: /^profile$/i })[0])
    await user.click(await screen.findByRole('button', { name: /edit profile/i }))

    expect(screen.getByText(/contact the bac/i)).toBeInTheDocument()
    for (const label of [/company name/i, /tin number/i, /business type/i]) {
      expect(screen.getByLabelText(label)).toHaveAttribute('readonly')
    }
    const contact = screen.getByLabelText(/contact person/i)
    await user.clear(contact)
    await user.type(contact, 'New Rep')
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => expect(api.find('PATCH', '/api/suppliers/7/profile/')).toHaveLength(1))
    const body = api.find('PATCH', '/api/suppliers/7/profile/')[0].body
    expect(body).toMatchObject({ contact_person: 'New Rep' })
    expect(body).not.toHaveProperty('company_name')
    expect(body).not.toHaveProperty('tin')
    expect(body).not.toHaveProperty('business_type')
  })

  it('an approved supplier changing categories confirms, then goes back to BAC review', async () => {
    signIn(supplierUser)
    const api = installApi(portalRoutes({
      'GET /api/suppliers/7/profile/': { json: approvedProfile },
      'GET /api/categories/': { json: profileCategories },
      'PATCH /api/suppliers/7/profile/': { json: { success: true, supplier: { ...approvedProfile, status: 'Pending Review', category_ids: [1, 2] } } },
    }))
    const { user } = renderAt('/supplier')

    await user.click(screen.getAllByRole('button', { name: /^profile$/i })[0])
    await user.click(await screen.findByRole('button', { name: /edit profile/i }))
    await user.click(screen.getByRole('checkbox', { name: /janitorial supplies/i }))
    await user.click(screen.getByRole('button', { name: /save changes/i }))

    // Nothing is sent until the supplier confirms the review consequence.
    const dialog = await screen.findByRole('alertdialog', { name: /send category changes for bac review/i })
    expect(api.mutations()).toHaveLength(0)
    await user.click(within(dialog).getByRole('button', { name: /save and send for review/i }))

    await waitFor(() => expect(api.find('PATCH', '/api/suppliers/7/profile/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/suppliers/7/profile/')[0].body).toMatchObject({ category_ids: [1, 2] })
    expect(await screen.findByText(/sent to the bac for review/i)).toBeInTheDocument()

    // The portal reflects the new status right away: RFQs are closed again.
    await user.click(screen.getAllByRole('button', { name: /^rfqs/i })[0])
    expect(api.find('GET', '/api/suppliers/7/rfqs/')).toHaveLength(0)
  })

  it('opportunity details show the ABC but no per-item costs', async () => {
    const opportunity = { id: 43, pr_no: '2026-11-001', office_section: 'ICT Office', purpose: 'Laptops', category: 'IT Equipment', grand_total: 2000, status: 'matched', posted_at: '2026-11-02T08:00:00Z' }
    signIn(supplierUser)
    // Even if item costs ever came back from the API, the page must not show them.
    installApi(portalRoutes({
      'GET /api/suppliers/7/opportunities/': { json: { opportunities: [opportunity] } },
      'GET /api/pr/43/details/': { json: { ...prDetails, id: 43, pr_no: '2026-11-001' } },
    }))
    const { user } = renderAt('/supplier')

    await user.click(screen.getAllByRole('button', { name: /^opportunities$/i })[0])
    await user.click(await screen.findByRole('button', { name: /view details for 2026-11-001/i }))

    expect(await screen.findByText(/approved budget for the contract \(abc\)/i)).toBeInTheDocument()
    expect(screen.getByText('₱2,000.00')).toBeInTheDocument()
    expect(screen.getByText('Laptop, 16GB RAM')).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: /unit cost/i })).not.toBeInTheDocument()
    expect(screen.queryByText('₱1,000.00')).not.toBeInTheDocument()
  })

  it('a supplier still under review sees the access status instead of RFQs', async () => {
    signIn({ ...supplierUser, supplier_status: 'Pending Review' })
    const api = installApi(portalRoutes())
    const { user } = renderAt('/supplier')

    await user.click(screen.getAllByRole('button', { name: /^rfqs/i })[0])

    expect(await screen.findByText(/still under review/i)).toBeInTheDocument()
    expect(api.find('GET', '/api/suppliers/7/rfqs/')).toHaveLength(0)
  })
})

describe('supplier registration wizard', () => {
  it('submits the full registration as multipart form data', async () => {
    const api = installApi({
      'GET /api/categories/': { json: [{ id: 1, name: 'IT Equipment' }, { id: 2, name: 'Janitorial Services' }] },
      'POST /api/suppliers/register': { status: 201, json: { message: 'Registration submitted.' } },
    })
    const { user } = renderAt('/supplier/register')

    await user.type(screen.getByLabelText(/company \/ supplier name/i), 'Acme Supplies, Inc.')
    await user.type(screen.getByLabelText(/business address/i), 'Cebu City')
    await user.type(screen.getByLabelText(/tin number/i), '123456789000')
    expect(screen.getByLabelText(/tin number/i)).toHaveValue('123-456-789-000')
    await user.type(screen.getByLabelText(/contact person/i), 'Jo Reyes')
    await user.type(screen.getByLabelText(/email address/i), 'sales@acme.ph')
    const phone = screen.getByLabelText(/phone number/i)
    await user.type(phone, '09171234567')
    expect(phone).toHaveValue('917 123 4567')
    expect(screen.getByLabelText(/country calling code/i)).toHaveValue('PH')
    await user.type(screen.getByLabelText(/^username/i), 'acme')
    await user.type(screen.getByLabelText(/^password/i), 'secret123')
    await user.type(screen.getByLabelText(/^confirm password/i), 'secret123')
    await user.click(screen.getByRole('button', { name: /^continue$/i }))

    await user.type(await screen.findByLabelText(/^products \/ services/i), 'Computers and peripherals')
    await user.click(await screen.findByRole('checkbox', { name: 'IT Equipment' }))
    await user.click(screen.getByRole('button', { name: /^continue$/i }))

    const inputs = await waitFor(() => {
      const found = document.querySelectorAll('input[type="file"]')
      if (found.length < 6) throw new Error('document inputs not rendered')
      return [...found]
    })
    const names = ['mayor.pdf', 'permit.pdf', 'philgeps.pdf', 'bir.pdf', 'tax.pdf', 'dti.pdf']
    for (const [index, name] of names.entries()) {
      await user.upload(inputs[index], pdfFile(name))
    }
    await user.upload(screen.getByLabelText('Other Eligibility Requirements'), [pdfFile('audited-fs.pdf'), pdfFile('omnibus.pdf')])
    await user.click(screen.getByRole('button', { name: /^continue$/i }))
    await user.click(await screen.findByRole('button', { name: /submit registration/i }))

    await waitFor(() => expect(api.find('POST', '/api/suppliers/register')).toHaveLength(1))
    expect(api.find('POST', '/api/suppliers/register')[0].body).toMatchSnapshot()
  })

  it('tracks attached documents and shows a rejected file on its card', async () => {
    installApi({ 'GET /api/categories/': { json: [{ id: 1, name: 'IT Equipment' }] } })
    const { user } = renderAt('/supplier/register')

    await user.type(screen.getByLabelText(/company \/ supplier name/i), 'Acme Supplies, Inc.')
    await user.type(screen.getByLabelText(/business address/i), 'Cebu City')
    await user.type(screen.getByLabelText(/tin number/i), '123456789000')
    await user.type(screen.getByLabelText(/contact person/i), 'Jo Reyes')
    await user.type(screen.getByLabelText(/email address/i), 'sales@acme.ph')
    await user.type(screen.getByLabelText(/phone number/i), '9171234567')
    await user.type(screen.getByLabelText(/^username/i), 'acme')
    await user.type(screen.getByLabelText(/^password/i), 'secret123')
    await user.type(screen.getByLabelText(/^confirm password/i), 'secret123')
    await user.click(screen.getByRole('button', { name: /^continue$/i }))
    await user.type(await screen.findByLabelText(/^products \/ services/i), 'Computers')
    await user.click(await screen.findByRole('checkbox', { name: 'IT Equipment' }))
    await user.click(screen.getByRole('button', { name: /^continue$/i }))

    expect(await screen.findByText('0 of 6 required documents attached')).toBeInTheDocument()
    const mayor = screen.getByLabelText("Mayor's Permit")
    await user.upload(mayor, pdfFile('mayor.pdf'))
    expect(screen.getByText('1 of 6 required documents attached')).toBeInTheDocument()
    expect(screen.getByText('mayor.pdf')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: "Remove Mayor's Permit file" }))
    expect(screen.getByText('0 of 6 required documents attached')).toBeInTheDocument()

    const permit = screen.getByLabelText('Business Permit')
    fireEvent.change(permit, { target: { files: [new File(['x'], 'notes.txt', { type: 'text/plain' })] } })
    expect(permit).toHaveAttribute('aria-invalid', 'true')
    expect(document.getElementById(permit.getAttribute('aria-describedby').split(' ').pop())).toHaveTextContent(/notes\.txt/)

    // Other Eligibility Requirements takes several files, skipping duplicates.
    const other = screen.getByLabelText('Other Eligibility Requirements')
    const audited = pdfFile('audited-fs.pdf')
    await user.upload(other, [audited, pdfFile('omnibus.pdf')])
    await user.upload(other, [audited, pdfFile('net-worth.pdf')])
    const otherList = screen.getByRole('list', { name: 'Other Eligibility Requirements files' })
    expect(within(otherList).getAllByRole('listitem').map((item) => item.querySelector('strong').textContent))
      .toEqual(['audited-fs.pdf', 'omnibus.pdf', 'net-worth.pdf'])
    expect(screen.getByText('3 attached')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove omnibus.pdf' }))
    expect(within(otherList).getAllByRole('listitem')).toHaveLength(2)
  })

  it('switches country and regroups the phone number', async () => {
    installApi({ 'GET /api/categories/': { json: [] } })
    const { user } = renderAt('/supplier/register')

    const phone = screen.getByLabelText(/phone number/i)
    await user.selectOptions(screen.getByLabelText(/country calling code/i), 'US')
    await user.type(phone, '4155550123')
    expect(phone).toHaveValue('415 555 0123')

    await user.clear(phone)
    await user.click(phone)
    await user.paste('+63 917 123 4567')
    expect(phone).toHaveValue('917 123 4567')
    expect(screen.getByLabelText(/country calling code/i)).toHaveValue('PH')
  })

  it('explains an incomplete phone number', async () => {
    installApi({ 'GET /api/categories/': { json: [] } })
    const { user } = renderAt('/supplier/register')

    await user.type(screen.getByLabelText(/phone number/i), '917123')
    await user.click(screen.getByRole('button', { name: /^continue$/i }))

    expect((await screen.findAllByText(/enter a complete philippines number, e\.g\. \+63 917 123 4567/i)).length).toBeGreaterThan(0)
    expect(screen.getByLabelText(/phone number/i)).toHaveAttribute('aria-invalid', 'true')
  })

  it('blocks Continue when required fields are missing', async () => {
    const api = installApi({ 'GET /api/categories/': { json: [] } })
    const { user } = renderAt('/supplier/register')

    await user.click(screen.getByRole('button', { name: /^continue$/i }))

    expect((await screen.findAllByText(/company name is required/i)).length).toBeGreaterThan(0)
    expect(api.mutations()).toHaveLength(0)
  })
})

// Processes 1, 8, 11 for suppliers: registration, quotation (completed RFQ)
// submission, and the supplier dashboard.
import { describe, expect, it } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { installApi, pdfFile, renderAt, signIn } from '../harness'
import { supplierRfq, supplierUser } from '../fixtures'

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

    await screen.findByText(/welcome back, acme supplies/i)
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
    const api = installApi(portalRoutes({
      'GET /api/suppliers/7/profile/': { json: { id: 7, company_name: 'Acme Supplies, Inc.', email: 'sales@acme.ph', status: 'Approved', documents: [], contact_phone: '0917-123-4567', tin: '123456789' } },
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
    await user.click(screen.getByRole('button', { name: /^continue$/i }))
    await user.click(await screen.findByRole('button', { name: /submit registration/i }))

    await waitFor(() => expect(api.find('POST', '/api/suppliers/register')).toHaveLength(1))
    expect(api.find('POST', '/api/suppliers/register')[0].body).toMatchSnapshot()
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

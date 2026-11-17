// Processes 6–7: category-based supplier matching, RFQ generation and email
// distribution, manual RFQ for unregistered suppliers.
import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { acceptConfirmation, installApi, renderAt, signIn } from '../harness'
import { adminUser, numberedPr, prDetails, supplierMatch } from '../fixtures'

const savedRfq = (body, status = 'draft') => ({
  id: 9,
  rfq_no: 'RFQ-2026-001',
  quotation_no: '2026-021',
  status,
  category: body.category,
  subject: body.subject,
  message: body.message,
  abc: '₱2,000.00',
  quotation_basis: body.quotation_basis,
  mode_of_procurement: body.mode_of_procurement,
  additional_notes: body.additional_notes,
  pdf_url: '/media/rfq-9.pdf',
  supplier: { id: 7 },
  selection_type: body.selection_type,
})

const routes = {
  'GET /api/admin/dashboard-summary/': { json: {} },
  'GET /api/suppliers/': { json: [] },
  'GET /api/pr/list/': { json: [numberedPr] },
  'GET /api/procurement-modes/': { json: { modes: ['Small Value Procurement', 'Shopping', 'Negotiated Procurement', 'Competitive Bidding'] } },
  'GET /api/pr/43/supplier-match/': { json: supplierMatch },
  'GET /api/pr/43/details/': { json: { ...prDetails, pr_no: '2026-11-001' } },
  'GET /api/pr/43/rfq/': { json: { rfqs: [] } },
  'POST /api/pr/43/rfq/': ({ body }) => ({ json: savedRfq(body) }),
  'PATCH /api/pr/43/rfq/': ({ body }) => ({ json: savedRfq(body, body.send ? 'sent' : 'draft') }),
  'POST /api/pr/43/manual-rfq/': ({ body }) => ({ json: { id: 31, manual_supplier_name: body.manual_supplier_name, quotation_no: '2026-022' } }),
}

async function openMatching(user) {
  await user.click(screen.getAllByRole('button', { name: /^purchase requests/i })[0])
  await user.click(await screen.findByRole('button', { name: /continue matching/i }))
  await screen.findByText(/category-matched suppliers/i)
}

describe('supplier matching and RFQ distribution', () => {
  it('saves, then sends, an RFQ to a category-matched supplier', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    await openMatching(user)

    await user.click(screen.getByRole('button', { name: /request quotation/i }))
    const mode = await waitFor(() => {
      const input = document.querySelector('input[list="procurement-mode-options"]')
      if (!input) throw new Error('mode input not rendered')
      return input
    })
    // The email is written automatically: no subject/message to fill in.
    expect(await screen.findByRole('heading', { name: /email to supplier/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/rfq message/i)).not.toBeInTheDocument()
    await user.type(mode, 'Small Value Procurement')
    await user.click(screen.getByRole('button', { name: /^save rfq/i }))

    await waitFor(() => expect(api.find('POST', '/api/pr/43/rfq/')).toHaveLength(1))
    expect(api.find('POST', '/api/pr/43/rfq/')[0].body).toMatchSnapshot('save body')
    expect(api.find('PATCH', '/api/pr/43/rfq/')).toHaveLength(0)

    await user.click(await screen.findByRole('button', { name: /send rfq to supplier/i }))
    await acceptConfirmation(user)

    await waitFor(() => expect(api.find('PATCH', '/api/pr/43/rfq/')).toHaveLength(1))
    const sendBody = api.find('PATCH', '/api/pr/43/rfq/')[0].body
    expect(sendBody).toMatchObject({ send: true, preview: false, rfq_id: 9, supplier_id: 7 })
    expect(sendBody).toMatchSnapshot('send body')
  })

  it('cancelling the send confirmation sends nothing', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    await openMatching(user)
    await user.click(screen.getByRole('button', { name: /request quotation/i }))
    await screen.findByRole('heading', { name: /email to supplier/i })
    await user.type(document.querySelector('input[list="procurement-mode-options"]'), 'Shopping')
    await user.click(screen.getByRole('button', { name: /^save rfq/i }))
    await waitFor(() => expect(api.find('POST', '/api/pr/43/rfq/')).toHaveLength(1))

    window.confirm.mockImplementation(() => false)
    await user.click(await screen.findByRole('button', { name: /send rfq to supplier/i }))
    const dialog = screen.queryByRole('alertdialog')
    if (dialog) await user.click(within(dialog).getByRole('button', { name: /cancel/i }))

    expect(api.find('PATCH', '/api/pr/43/rfq/')).toHaveLength(0)
  })

  it('issues a manual RFQ to an unregistered supplier', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    await openMatching(user)

    await user.click(screen.getByRole('button', { name: /add unregistered supplier/i }))
    const dialog = await screen.findByRole('dialog', { name: /add unregistered supplier/i })
    await user.type(within(dialog).getByLabelText(/company \/ supplier name/i), "Juan's Aircon Services")
    await user.type(within(dialog).getByLabelText(/mode of procurement/i), 'Shopping')
    await user.selectOptions(within(dialog).getByLabelText(/quotation basis/i), 'LINE')
    await user.click(within(dialog).getByRole('button', { name: /create rfq/i }))
    await acceptConfirmation(user)

    await waitFor(() => expect(api.find('POST', '/api/pr/43/manual-rfq/')).toHaveLength(1))
    expect(api.find('POST', '/api/pr/43/manual-rfq/')[0].body).toEqual({
      manual_supplier_name: "Juan's Aircon Services",
      category: 'IT Equipment',
      mode_of_procurement: 'Shopping',
      quotation_basis: 'LINE',
    })
  })
})

describe('assign categories', () => {
  it('assigns a category per item with the labelled combobox and saves the assignments', async () => {
    signIn(adminUser)
    const api = installApi({
      ...routes,
      'GET /api/pr/list/': { json: [{ ...numberedPr, category: '' }] },
      'GET /api/categories/': { json: [{ id: 3, name: 'IT Equipment' }, { id: 4, name: 'Janitorial Services' }] },
      'GET /api/pr/43/items/': { json: [
        { id: 100, item_description: 'Laptop', quantity: 2, unit_cost: 1000, category: '' },
        { id: 101, item_description: 'Mop', quantity: 5, unit_cost: 50, category: 'Janitorial Services' },
      ] },
      'POST /api/pr/43/items/categories/': { json: { ok: true } },
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /^purchase requests/i })[0])
    await user.click(await screen.findByRole('button', { name: /select categories/i }))

    const first = await screen.findByRole('combobox', { name: 'Category for item 1' })
    await user.click(first)
    await user.type(first, 'IT')
    const listbox = screen.getByRole('listbox', { name: 'Category for item 1' })
    expect(first).toHaveAttribute('aria-controls', listbox.id)
    await user.keyboard('{Enter}')
    await user.click(screen.getByRole('button', { name: /save categories and continue/i }))

    await waitFor(() => expect(api.find('POST', '/api/pr/43/items/categories/')).toHaveLength(1))
    expect(api.find('POST', '/api/pr/43/items/categories/')[0].body).toEqual({
      assignments: [
        { item_id: 100, category: 'IT Equipment' },
        { item_id: 101, category: 'Janitorial Services' },
      ],
    })
  })

  it('does not save while an item has no category', async () => {
    signIn(adminUser)
    const api = installApi({
      ...routes,
      'GET /api/pr/list/': { json: [{ ...numberedPr, category: '' }] },
      'GET /api/categories/': { json: [{ id: 3, name: 'IT Equipment' }] },
      'GET /api/pr/43/items/': { json: [{ id: 100, item_description: 'Laptop', quantity: 2, unit_cost: 1000, category: '' }] },
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /^purchase requests/i })[0])
    await user.click(await screen.findByRole('button', { name: /select categories/i }))
    await user.click(await screen.findByRole('button', { name: /save categories and continue/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/1 item still need a category/i)
    expect(screen.getByRole('combobox', { name: 'Category for item 1' })).toHaveAttribute('aria-invalid', 'true')
    expect(api.mutations()).toHaveLength(0)
  })
})

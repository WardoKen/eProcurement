// Process 2: document eligibility verification and supplier approval.
import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, supplierProfile, supplierRow } from '../fixtures'

const routes = {
  'GET /api/admin/dashboard-summary/': { json: {} },
  'GET /api/pr/list/': { json: [] },
  'GET /api/suppliers/': { json: [supplierRow] },
  'GET /api/suppliers/7/profile/': { json: supplierProfile },
  'PATCH /api/suppliers/7/status/': ({ body }) => ({
    json: {
      remarks: body.remarks,
      documents: Object.entries(body.document_statuses).map(([id, status]) => ({ id: Number(id), verification_status: status })),
    },
  }),
  'DELETE /api/suppliers/7/': { json: {} },
}

async function openSupplierReview(user) {
  await user.click(screen.getAllByRole('button', { name: /supplier management/i })[0])
  await user.click(await screen.findByRole('button', { name: /^view details$/i }))
  return screen.findByRole('dialog', { name: /acme supplies/i })
}

// The decision dialog's confirming button ("Confirm", "Confirm Rejection", ...).
async function confirmDecision(user) {
  const buttons = await screen.findAllByRole('button', { name: /^confirm/i })
  await user.click(buttons[buttons.length - 1])
}

describe('supplier verification', () => {
  it('approve sends status, remarks and per-document decisions', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    const review = await openSupplierReview(user)

    const verifyButtons = within(review).getAllByRole('button', { name: /^verify/i })
    await user.click(verifyButtons[0])
    await user.click(verifyButtons[1])
    await user.click(within(review).getByRole('button', { name: /approve registration/i }))
    await confirmDecision(user)

    await waitFor(() => expect(api.find('PATCH', '/api/suppliers/7/status/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/suppliers/7/status/')[0].body).toEqual({
      status: 'Approved',
      remarks: '',
      document_statuses: { 1: 'Verified', 2: 'Verified' },
    })
  })

  it('reject is blocked without remarks, then sends them', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    const review = await openSupplierReview(user)

    await user.click(within(review).getAllByRole('button', { name: /^reject$/i })[0])
    await user.click(within(review).getByRole('button', { name: /reject registration/i }))
    await confirmDecision(user)
    expect(api.find('PATCH', '/api/suppliers/7/status/')).toHaveLength(0)
    expect((await screen.findAllByText(/remarks are required/i)).length).toBeGreaterThan(0)

    await user.type(screen.getByLabelText(/review remarks/i, { selector: '#review-action-remarks' }), 'Business permit is expired.')
    await confirmDecision(user)

    await waitFor(() => expect(api.find('PATCH', '/api/suppliers/7/status/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/suppliers/7/status/')[0].body).toEqual({
      status: 'Rejected',
      remarks: 'Business permit is expired.',
      document_statuses: { 1: 'Rejected' },
    })
  })

  it('request additional documents sends For Compliance', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    const review = await openSupplierReview(user)

    await user.click(within(review).getByRole('button', { name: /request additional documents/i }))
    await user.type(screen.getByLabelText(/review remarks/i, { selector: '#review-action-remarks' }), 'Upload a current BIR 2303.')
    await confirmDecision(user)

    await waitFor(() => expect(api.find('PATCH', '/api/suppliers/7/status/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/suppliers/7/status/')[0].body).toEqual({
      status: 'For Compliance',
      remarks: 'Upload a current BIR 2303.',
      document_statuses: {},
    })
  })

  it('apply document changes keeps the current status', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    const review = await openSupplierReview(user)

    await user.click(within(review).getAllByRole('button', { name: /^verify/i })[1])
    await user.click(within(review).getByRole('button', { name: /apply document changes/i }))

    await waitFor(() => expect(api.find('PATCH', '/api/suppliers/7/status/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/suppliers/7/status/')[0].body).toEqual({
      status: 'Pending Review',
      remarks: '',
      document_statuses: { 2: 'Verified' },
    })
  })

  it('delete account requires confirmation', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /supplier management/i })[0])

    await user.click(await screen.findByRole('button', { name: /^delete account$/i }))
    expect(api.find('DELETE', '/api/suppliers/7/')).toHaveLength(0)
    const dialog = await screen.findByRole('alertdialog', { name: /delete supplier account/i })
    await user.click(within(dialog).getByRole('button', { name: /delete account/i }))

    await waitFor(() => expect(api.find('DELETE', '/api/suppliers/7/')).toHaveLength(1))
  })
})

// Irreversible actions ask first and say what will happen. Cancelling sends
// nothing. (The payloads themselves are pinned by the per-flow tests.)
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, numberedPr, prDetails, supplierMatch, supplierProfile, supplierRow, unnumberedPr } from '../fixtures'

const adminRoutes = {
  'GET /api/admin/dashboard-summary/': { json: {} },
  'GET /api/suppliers/': { json: [supplierRow] },
  'GET /api/suppliers/7/profile/': { json: supplierProfile },
  'GET /api/pr/list/': { json: [unnumberedPr, numberedPr] },
  'GET /api/pr/42/details/': { json: prDetails },
  'PATCH /api/pr/42/edit/': { json: { pr_no: '2026-11-002', status: 'in_review', grand_total: '2000.00' } },
  'GET /api/procurement-modes/': { json: { modes: ['Shopping'] } },
  'GET /api/pr/43/supplier-match/': { json: supplierMatch },
  'GET /api/pr/43/details/': { json: { ...prDetails, pr_no: '2026-11-001' } },
  'GET /api/pr/43/rfq/': { json: { rfqs: [] } },
  'POST /api/pr/43/rfq/': ({ body }) => ({ json: { id: 9, rfq_no: 'RFQ-2026-001', status: 'draft', ...body, supplier: { id: 7 } } }),
  'PATCH /api/pr/43/rfq/': { json: {} },
}

const openPrMonitoring = async (user) => {
  await user.click(screen.getAllByRole('button', { name: /^purchase requests/i })[0])
  await screen.findByText(/awaiting pr number/i)
}

describe('confirmation steps', () => {
  it('Assign PR Number states that the number is permanent; cancel sends nothing', async () => {
    signIn(adminUser)
    const api = installApi(adminRoutes)
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    await user.click(await screen.findByRole('button', { name: /review pr/i }))
    await screen.findByDisplayValue('RC-100')

    await user.click(screen.getByRole('button', { name: /assign pr number/i }))
    const dialog = await screen.findByRole('alertdialog', { name: /assign the official pr number/i })
    expect(dialog).toHaveAccessibleDescription(/permanent/i)
    expect(within(dialog).getByRole('button', { name: /cancel/i })).toHaveFocus()

    await user.click(within(dialog).getByRole('button', { name: /cancel/i }))
    expect(api.find('PATCH', '/api/pr/42/edit/')).toHaveLength(0)
    // The review modal is still open with the user's work intact.
    expect(screen.getByDisplayValue('RC-100')).toBeInTheDocument()
  })

  it('Send RFQ states the recipient and that the RFQ locks', async () => {
    signIn(adminUser)
    installApi(adminRoutes)
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    await user.click(await screen.findByRole('button', { name: /continue matching/i }))
    await user.click(await screen.findByRole('button', { name: /request quotation/i }))
    await screen.findByRole('heading', { name: /email to supplier/i })
    await user.type(document.querySelector('input[list="procurement-mode-options"]'), 'Shopping')
    await user.click(screen.getByRole('button', { name: /^save rfq/i }))
    await user.click(await screen.findByRole('button', { name: /send rfq to supplier/i }))

    const dialog = await screen.findByRole('alertdialog', { name: /send rfq to acme supplies/i })
    expect(dialog).toHaveTextContent('sales@acme.ph')
    expect(dialog).toHaveAccessibleDescription(/can no longer be edited/i)
  })

  it('Reject Supplier states the consequence for the supplier', async () => {
    signIn(adminUser)
    installApi(adminRoutes)
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /^suppliers/i })[0])
    await user.click(await screen.findByRole('button', { name: /^view details for acme supplies/i }))
    const review = await screen.findByRole('dialog', { name: /acme supplies/i })
    await user.click(within(review).getByRole('button', { name: /reject registration/i }))

    const dialog = await screen.findByRole('alertdialog', { name: /reject supplier/i })
    expect(dialog).toHaveAccessibleDescription(/loses access to opportunities/i)
    expect(within(dialog).getByRole('button', { name: /confirm rejection/i })).toBeInTheDocument()
    expect(within(dialog).getByLabelText(/review remarks/i)).toBeRequired()
  })

  it('Escape closes a confirmation without acting', async () => {
    signIn(adminUser)
    const api = installApi({ ...adminRoutes, 'DELETE /api/pr/42/': { json: {} } })
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    const deleteButtons = screen.getAllByRole('button', { name: /^delete/i })
    await user.click(deleteButtons[0])
    await screen.findByRole('alertdialog', { name: /delete purchase request/i })

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(api.find('DELETE', '/api/pr/42/')).toHaveLength(0)
  })
})

describe('modal focus management on real screens', () => {
  it('PR review modal traps focus, closes on Escape and returns focus to its trigger', async () => {
    signIn(adminUser)
    installApi(adminRoutes)
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    const trigger = await screen.findByRole('button', { name: /review pr/i })
    await user.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: /review purchase request/i })
    await screen.findByDisplayValue('RC-100')

    for (let index = 0; index < 40; index += 1) {
      await user.tab()
      expect(dialog.contains(document.activeElement)).toBe(true)
    }

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: /review purchase request/i })).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('View on a PR opens a summary dialog instead of a browser alert', async () => {
    signIn(adminUser)
    installApi(adminRoutes)
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)

    await user.click(screen.getByRole('button', { name: 'View 2026-11-001' }))

    const dialog = await screen.findByRole('dialog', { name: /purchase request 2026-11-001/i })
    expect(dialog).toHaveTextContent('In Review')
    expect(window.alert).not.toHaveBeenCalled()
  })
})

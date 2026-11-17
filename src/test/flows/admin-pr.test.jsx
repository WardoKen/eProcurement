// Processes 3–5 on the BAC side: review extracted PRs, assign the PR number,
// change workflow status, delete.
import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { acceptConfirmation, installApi, renderAt, signIn } from '../harness'
import { adminUser, numberedPr, prDetails, unnumberedPr } from '../fixtures'

const routes = (overrides = {}) => ({
  'GET /api/admin/dashboard-summary/': { json: {} },
  'GET /api/suppliers/': { json: [] },
  'GET /api/pr/list/': { json: [unnumberedPr, numberedPr] },
  'GET /api/pr/42/details/': { json: prDetails },
  'PATCH /api/pr/42/edit/': ({ body }) => ({ json: { grand_total: '2000.00', pr_no: body.finalize_review ? '2026-11-002' : '', status: body.finalize_review ? 'in_review' : 'uploaded' } }),
  'PATCH /api/pr/43/status/': { json: { status: 'matched' } },
  'DELETE /api/pr/42/': { json: {} },
  ...overrides,
})

async function openPrMonitoring(user) {
  await user.click(screen.getAllByRole('button', { name: /^purchase requests/i })[0])
  await screen.findByText(/awaiting pr number/i)
}

async function openReview(user) {
  await user.click(await screen.findByRole('button', { name: /review pr/i }))
  await screen.findByDisplayValue('RC-100')
}

describe('BAC PR review and numbering', () => {
  it('Save Corrections sends the edited record without finalizing', async () => {
    signIn(adminUser)
    const api = installApi(routes())
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    await openReview(user)

    const entity = screen.getByDisplayValue('Cebu Technological University')
    await user.clear(entity)
    await user.type(entity, 'CTU Main Campus')
    await user.click(screen.getByRole('button', { name: /save corrections/i }))

    await waitFor(() => expect(api.find('PATCH', '/api/pr/42/edit/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/pr/42/edit/')[0].body).toMatchSnapshot()
  })

  it('Assign PR Number finalizes the review with automatic numbering', async () => {
    signIn(adminUser)
    const api = installApi(routes())
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    await openReview(user)

    await user.click(screen.getByRole('button', { name: /assign pr number/i }))
    await acceptConfirmation(user)

    await waitFor(() => expect(api.find('PATCH', '/api/pr/42/edit/')).toHaveLength(1))
    const body = api.find('PATCH', '/api/pr/42/edit/')[0].body
    expect(body.finalize_review).toBe(true)
    expect(body.pr_number_mode).toBe('automatic')
    expect(body).toMatchSnapshot()
  })

  it('Assign PR Number with a custom number sends it', async () => {
    signIn(adminUser)
    const api = installApi(routes())
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    await openReview(user)

    await user.click(screen.getByRole('radio', { name: /custom/i }))
    await user.type(screen.getByLabelText(/custom pr number/i), '2026-11-077')
    await user.click(screen.getByRole('button', { name: /assign pr number/i }))
    await acceptConfirmation(user)

    await waitFor(() => expect(api.find('PATCH', '/api/pr/42/edit/')).toHaveLength(1))
    const body = api.find('PATCH', '/api/pr/42/edit/')[0].body
    expect(body).toMatchObject({ finalize_review: true, pr_number_mode: 'custom', custom_pr_number: '2026-11-077' })
  })

  it('status change sends only the new status', async () => {
    signIn(adminUser)
    const api = installApi(routes())
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)

    await user.click(await screen.findByRole('button', { name: /^edit status/i }))
    await user.selectOptions(document.querySelector('select.pr-status-select'), 'matched')
    await user.click(screen.getByRole('button', { name: /^save( status)?/i }))
    await acceptConfirmation(user)

    await waitFor(() => expect(api.find('PATCH', '/api/pr/43/status/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/pr/43/status/')[0].body).toEqual({ status: 'matched' })
  })

  it('delete requires confirmation, then sends DELETE', async () => {
    signIn(adminUser)
    const api = installApi(routes())
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)

    const queue = screen.getByText(/awaiting pr number/i).closest('section, div.admin-checklist')
    await user.click(within(queue).getByRole('button', { name: /^delete/i }))
    expect(api.find('DELETE', '/api/pr/42/')).toHaveLength(0)

    const dialog = await screen.findByRole('alertdialog', { name: /delete purchase request/i })
    await user.click(within(dialog).getByRole('button', { name: /confirm delete|^delete/i }))

    await waitFor(() => expect(api.find('DELETE', '/api/pr/42/')).toHaveLength(1))
  })
})

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
  'GET /api/pr/42/changes/': { json: { changes: {}, events: [], changed_count: 0, original_available: true, locked: false } },
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

// The recheck result for a PR whose Funds Available box could not be read
// and whose Approved By box reads blank.
const sigRow = (key, label, state, reason = 'test') => ({ key, label, state, reason, required: key !== 'twg', name: '' })
const failedSignatureCheck = {
  summary: {
    can_save: false, needs_confirmation: false, needs_bac_verification: false,
    required_detected: 1, required_total: 3, status: 'incomplete',
    message: 'One or more required signatures are missing.',
    missing_signatures: ['Approved By'], missing_keys: ['approved_by'],
    uncertain_signatures: [], uncertain_keys: [],
    unverifiable_signatures: ['Funds Available'], unverifiable_keys: ['funds_available'],
  },
  signatories: {
    requested_by: sigRow('requested_by', 'Requested By', 'present'),
    funds_available: sigRow('funds_available', 'Funds Available', 'unverifiable', 'analysis_error'),
    approved_by: sigRow('approved_by', 'Approved By', 'absent'),
    twg: sigRow('twg', 'TWG Verified By', 'present'),
  },
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
    // An edit cannot be saved without a reason.
    expect(screen.getByRole('button', { name: /save corrections/i })).toBeDisabled()
    await user.type(screen.getByLabelText(/reason for edits/i), 'Entity name misread')
    await user.click(screen.getByRole('button', { name: /save corrections/i }))

    await waitFor(() => expect(api.find('PATCH', '/api/pr/42/edit/')).toHaveLength(1))
    const body = api.find('PATCH', '/api/pr/42/edit/')[0].body
    expect(body.reason).toBe('Entity name misread')
    expect(body.items[0].id).toBe(100)
    expect(body).toMatchSnapshot()
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

describe('PR change history', () => {
  const numberedDetails = {
    ...prDetails,
    pr_no: '2026-11-001',
    purpose: 'Laptops for the faculty room',
    items: [{ ...prDetails.items[0], quantity: 3 }],
  }
  const changes = {
    locked: true,
    original_available: true,
    changed_count: 3,
    changes: {
      'pr:purpose': {
        field: 'purpose', label: 'Purpose', item_id: null,
        original: 'Laptops for the computer laboratory', current: 'Laptops for the faculty room',
        history: [
          { old: 'Laptops for the computer laboratory', new: 'Laptops for the lab', by: 'Maria Santos', by_username: 'bac-maria', by_role: 'BAC Secretariat', at: '2026-11-02T01:00:00Z', reason: 'First correction' },
          { old: 'Laptops for the lab', new: 'Laptops for the faculty room', by: 'Maria Santos', by_username: 'bac-maria', by_role: 'BAC Secretariat', at: '2026-11-02T02:00:00Z', reason: 'Per end user memo' },
        ],
      },
      '100:quantity': {
        field: 'quantity', label: 'Item 1 · Quantity', item_id: 100, item_label: 'Laptop, 16GB RAM',
        original: '2.00', current: '3.00',
        history: [{ old: '2.00', new: '3.00', by: 'Maria Santos', by_username: 'bac-maria', by_role: 'BAC Secretariat', at: '2026-11-02T02:00:00Z', reason: 'Quantity misread' }],
      },
    },
    editors: [{ name: 'Maria Santos', username: 'bac-maria', role: 'BAC Secretariat', edit_count: 4 }],
    events: [
      { type: 'item_removed', item_id: 99, item_label: 'Mouse', value: { item_description: 'Mouse', quantity: '1.00', unit: 'pc', unit_cost: '300.00' }, by: 'Maria Santos', by_username: 'bac-maria', by_role: 'BAC Secretariat', at: '2026-11-02T02:00:00Z', reason: 'Duplicate line' },
    ],
  }

  const lockedRoutes = () => routes({
    'GET /api/pr/43/details/': { json: numberedDetails },
    'GET /api/pr/43/changes/': { json: changes },
  })

  async function openLocked(user) {
    await openPrMonitoring(user)
    await user.click(await screen.findByRole('button', { name: /open details for 2026-11-001/i }))
    await screen.findByDisplayValue('RC-100')
  }

  it('a numbered PR opens read-only with edited fields highlighted', async () => {
    signIn(adminUser)
    installApi(lockedRoutes())
    const { user } = renderAt('/admin')
    await openLocked(user)

    expect(await screen.findByText(/is locked and shown read-only/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /save corrections/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /add item/i })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/reason for edits/i)).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('Laptops for the faculty room')).toHaveAttribute('readonly')

    // Purpose and item quantity are flagged; the tooltip carries the original.
    const badges = await screen.findAllByText('Edited', { selector: '.field-value-badge, .field-value-badge *' })
    expect(badges).toHaveLength(2)
    expect(screen.getAllByRole('tooltip', { hidden: true }).map((node) => node.textContent)).toEqual(
      expect.arrayContaining([expect.stringContaining('Laptops for the computer laboratory'), expect.stringContaining('2.00')]),
    )
  })

  it('View changes lists each change, item events and expands multi-step edits', async () => {
    signIn(adminUser)
    installApi(lockedRoutes())
    const { user } = renderAt('/admin')
    await openLocked(user)

    await user.click(await screen.findByRole('button', { name: /view changes \(3\)/i }))
    const dialog = await screen.findByRole('dialog', { name: /change history/i })
    const table = within(dialog).getByRole('table')
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(
      ['Field', 'Original (from upload)', 'Current', 'Edited by (account)', 'Date', 'Reason'],
    )
    expect(within(table).getByText('Item removed')).toBeInTheDocument()
    expect(within(table).getByText('Duplicate line')).toBeInTheDocument()
    expect(within(table).getByText('Quantity misread')).toBeInTheDocument()
    expect(within(table).queryByText('First correction')).not.toBeInTheDocument()

    await user.click(within(table).getByRole('button', { name: /purpose/i }))
    expect(within(table).getByText('First correction')).toBeInTheDocument()
    expect(within(table).getByText('Edit 2')).toBeInTheDocument()
  })

  it('shows the account that made each change', async () => {
    signIn(adminUser)
    installApi(lockedRoutes())
    const { user } = renderAt('/admin')
    await openLocked(user)

    // Header summary and the field tooltip name the editing account.
    expect(await screen.findByText(/edited by/i, { selector: '.pr-edited-by-label' })).toBeInTheDocument()
    expect(screen.getAllByRole('tooltip', { hidden: true })[0]).toHaveTextContent(/changed by\s*maria santos \(@bac-maria\) · bac secretariat/i)

    await user.click(screen.getByRole('button', { name: /view changes \(3\)/i }))
    const table = within(await screen.findByRole('dialog', { name: /change history/i })).getByRole('table')
    expect(within(table).getByRole('columnheader', { name: /edited by \(account\)/i })).toBeInTheDocument()
    // One row per change (purpose, item quantity, item removed), each naming the account.
    expect(within(table).getAllByText('@bac-maria')).toHaveLength(3)
  })

  it('hides the View changes button when nothing changed', async () => {
    signIn(adminUser)
    installApi(routes())
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    await openReview(user)

    expect(screen.queryByRole('button', { name: /view changes/i })).not.toBeInTheDocument()
    expect(screen.queryByText('Edited', { selector: '.field-value-badge, .field-value-badge *' })).not.toBeInTheDocument()
  })

  it('signatures the detector did not find must be verified before numbering; a blank one needs a note', async () => {
    signIn(adminUser)
    const api = installApi(routes({
      'GET /api/pr/list/': { json: [{ ...unnumberedPr, signatures_to_verify: ['Funds Available'] }, numberedPr] },
      'GET /api/pr/42/details/': { json: { ...prDetails, source_filename: 'pr-42.pdf', source_file_url: '/uploads/pr-42.pdf' } },
      'POST /api/pr/recheck-signatures/': { json: { success: true, signature_validation: failedSignatureCheck } },
    }))
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    expect(screen.getByText('Verify signatures: Funds Available')).toBeInTheDocument()
    await openReview(user)

    const assign = await screen.findByRole('button', { name: /assign pr number/i })
    await screen.findByRole('checkbox', { name: /funds available is signed/i })
    expect(assign).toBeDisabled()

    await user.click(screen.getByRole('checkbox', { name: /i checked the original document: funds available is signed/i }))
    expect(assign).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: /override: .*approved by is signed/i }))
    const note = screen.getByLabelText(/why the detector was wrong/i)
    await user.type(note, 'pencil')
    expect(assign).toBeDisabled()
    await user.type(note, ' signature, checked the paper original')
    expect(assign).toBeEnabled()

    await user.click(assign)
    await acceptConfirmation(user)
    await waitFor(() => expect(api.find('PATCH', '/api/pr/42/edit/')).toHaveLength(1))
    expect(api.find('PATCH', '/api/pr/42/edit/')[0].body.signature_verifications).toEqual([
      { key: 'funds_available', note: '' },
      { key: 'approved_by', note: 'pencil signature, checked the paper original' },
    ])
  })

  it('without a document, numbering asks the BAC to verify the signatures the server could not check', async () => {
    signIn(adminUser)
    const blank = {
      ...failedSignatureCheck,
      signatories: Object.fromEntries(Object.entries(failedSignatureCheck.signatories).map(
        ([key, row]) => [key, { ...row, state: 'unverifiable', reason: 'document_missing' }],
      )),
    }
    installApi(routes({
      'PATCH /api/pr/42/edit/': {
        status: 422,
        json: {
          success: false,
          signature_verification_required: true,
          message: 'Verify these signatures against the original document before assigning the PR number: Requested By, Funds Available, Approved By.',
          signature_validation: blank,
        },
      },
    }))
    const { user } = renderAt('/admin')
    await openPrMonitoring(user)
    await openReview(user)
    expect(screen.getByText(/no document is on file for this pr/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /assign pr number/i }))
    await acceptConfirmation(user)

    expect(await screen.findByText(/verify these signatures against the original document before assigning/i)).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox', { name: /i checked the original document/i })).toHaveLength(3)
    expect(screen.getByRole('button', { name: /assign pr number/i })).toBeDisabled()
  })
})

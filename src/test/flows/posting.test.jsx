// Explicit posting of Purchase Requests as procurement opportunities: the BAC
// posts / takes down a PR from its details; the public Opportunities page
// shows only posted PRs, from the public feed.
import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, numberedPr, prDetails } from '../fixtures'

const notPosted = {
  is_posted: false, posted_at: null, posted_by: '', can_post: true, post_problem: '', min_reason_length: 10, history: [],
}
const posted = {
  ...notPosted, is_posted: true, posted_at: '2026-11-19T01:00:00Z', posted_by: 'bac', post_problem: '', can_post: false,
  history: [{ id: 1, action: 'posted', reason: '', automatic: false, changed_by: 'bac', changed_at: '2026-11-19T01:00:00Z' }],
}

describe('BAC posting', () => {
  it('posts a PR, then takes it down with a reason', async () => {
    const matchedPr = { ...numberedPr, status: 'matched' }
    signIn(adminUser)
    const api = installApi({
      'GET /api/admin/dashboard-summary/': { json: {} },
      'GET /api/suppliers/': { json: [] },
      'GET /api/pr/list/': { json: [matchedPr] },
      'GET /api/pr/43/details/': { json: { ...prDetails, id: 43, pr_no: '2026-11-001', status: 'matched' } },
      'GET /api/pr/43/changes/': { json: { changes: {}, events: [], changed_count: 0, original_available: true, locked: true } },
      'GET /api/pr/43/posting/': { json: notPosted },
      'POST /api/pr/43/posting/': ({ body }) => ({
        json: body.action === 'post'
          ? posted
          : { ...notPosted, history: [{ id: 2, action: 'unposted', reason: body.reason, automatic: false, changed_by: 'bac', changed_at: '2026-11-19T02:00:00Z' }, ...posted.history] },
      }),
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /^purchase requests/i })[0])
    await user.click(await screen.findByRole('button', { name: 'View 2026-11-001' }))
    const summary = await screen.findByRole('dialog', { name: /purchase request 2026-11-001/i })
    await user.click(within(summary).getByRole('button', { name: /open details/i }))

    const posting = await screen.findByRole('region', { name: /public posting/i })
    expect(posting).toHaveTextContent('Not posted')
    await user.click(within(posting).getByRole('button', { name: /post as opportunity/i }))
    // Confirm first: nothing is posted until then.
    const confirmDialog = await screen.findByRole('alertdialog', { name: /post as procurement opportunity/i })
    expect(api.find('POST', '/api/pr/43/posting/')).toHaveLength(0)
    await user.click(within(confirmDialog).getByRole('button', { name: /^post$/i }))

    // Posted: the action flips to "Take down".
    expect(await within(posting).findByRole('button', { name: /take down/i })).toBeInTheDocument()
    expect(posting.querySelector('.status-badge')).toHaveTextContent('Posted')
    expect(api.find('POST', '/api/pr/43/posting/')[0].body).toEqual({ action: 'post' })
    expect(posting).toHaveTextContent('by bac')

    // Take down: a reason is required.
    await user.click(within(posting).getByRole('button', { name: /take down/i }))
    const unpostDialog = await screen.findByRole('alertdialog', { name: /take down posting/i })
    const reason = within(unpostDialog).getByLabelText(/reason/i)
    await user.type(reason, 'short')
    await user.click(within(unpostDialog).getByRole('button', { name: /take down posting/i }))
    expect(within(unpostDialog).getByText('Enter at least 10 characters (5 so far).')).toBeInTheDocument()
    expect(api.find('POST', '/api/pr/43/posting/')).toHaveLength(1)

    await user.clear(reason)
    await user.type(reason, 'End user withdrew the request.')
    await user.click(within(unpostDialog).getByRole('button', { name: /take down posting/i }))

    await waitFor(() => expect(api.find('POST', '/api/pr/43/posting/')).toHaveLength(2))
    expect(api.find('POST', '/api/pr/43/posting/')[1].body).toEqual({ action: 'unpost', reason: 'End user withdrew the request.' })
    await waitFor(() => expect(posting).toHaveTextContent('Not posted'))
    expect(posting).toHaveTextContent('End user withdrew the request.')
  })
})

describe('public Opportunities page', () => {
  it('lists only posted PRs from the public feed, without signing in', async () => {
    const api = installApi({
      // Alphabetical, with ids that are not 1, 2: rows must still number 1, 2.
      'GET /api/categories/': { json: [{ id: 7, name: 'IT Equipment', count: 0 }, { id: 3, name: 'Office Supplies', count: 1 }] },
      'GET /api/public/opportunities/': {
        json: { opportunities: [{
          id: 43, pr_no: '2026-11-001', entity_name: 'CTU', office_section: 'ICT Office', purpose: 'Bond paper for exams',
          categories: ['Office Supplies'], abc: 2500, posted_at: '2026-11-19T01:00:00Z',
          items: [{ description: 'Bond paper', quantity: 10, unit: 'ream' }],
        }] },
      },
    })
    const { user } = renderAt('/opportunities')

    expect(await screen.findByText(/1 open opportunities/i)).toBeInTheDocument()
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows.map((row) => row.cells[0].textContent)).toEqual(['1', '2'])
    await user.click(screen.getByRole('button', { name: 'Office Supplies' }))

    expect(await screen.findByText('2026-11-001')).toBeInTheDocument()
    expect(screen.getByText('Bond paper (10 ream)')).toBeInTheDocument()
    expect(screen.getByText('₱2,500.00')).toBeInTheDocument()
    const feedCalls = api.calls.filter((call) => call.path.startsWith('/api/public/opportunities/'))
    expect(feedCalls).toHaveLength(1)
    expect(new URLSearchParams(feedCalls[0].path.split('?')[1]).get('category')).toBe('Office Supplies')
    // The signed-in-only PR list is never used by the public page.
    expect(api.calls.some((call) => call.path.startsWith('/api/pr/list/'))).toBe(false)
  })
})

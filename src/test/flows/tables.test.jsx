// List controls added to screens: search, filters, sorting, pagination.
// They only reorder or slice what the API already returned.
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, numberedPr } from '../fixtures'

const manyPrs = Array.from({ length: 12 }, (_, index) => ({
  ...numberedPr,
  id: 100 + index,
  pr_no: `2026-11-${String(index + 1).padStart(3, '0')}`,
  entity_name: index % 2 ? 'College of Engineering' : 'ICT Office',
  status: index < 3 ? 'matched' : 'in_review',
  grand_total: String(1000 * (index + 1)),
}))

const routes = {
  'GET /api/admin/dashboard-summary/': { json: {} },
  'GET /api/suppliers/': { json: [] },
  'GET /api/pr/list/': { json: manyPrs },
}

const dataRows = (table) => within(table).getAllByRole('row').slice(1)

async function openMonitor(user) {
  await user.click(screen.getAllByRole('button', { name: /pr review & monitoring/i })[0])
  return screen.findByRole('table', { name: /numbered purchase requests/i })
}

describe('PR monitoring table', () => {
  it('paginates, searches, filters and sorts client-side without new requests', async () => {
    signIn(adminUser)
    const api = installApi(routes)
    const { user } = renderAt('/admin')
    const table = await openMonitor(user)
    const listCallsBefore = api.find('GET', '/api/pr/list/').length

    expect(dataRows(table)).toHaveLength(10)
    expect(screen.getByText('Showing 1–10 of 12')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(dataRows(table)).toHaveLength(2)

    await user.type(screen.getByLabelText(/search numbered prs/i), 'engineering')
    expect(dataRows(table)).toHaveLength(6)
    expect(screen.getByText('6 Purchase Requests of 12')).toBeInTheDocument()

    await user.clear(screen.getByLabelText(/search numbered prs/i))
    await user.selectOptions(screen.getByLabelText(/^status$/i), 'matched')
    expect(dataRows(table)).toHaveLength(3)

    await user.selectOptions(screen.getByLabelText(/^status$/i), 'all')
    const totalHeader = within(table).getByRole('columnheader', { name: /grand total/i })
    await user.click(within(totalHeader).getByRole('button'))
    await user.click(within(totalHeader).getByRole('button'))
    expect(totalHeader).toHaveAttribute('aria-sort', 'descending')
    expect(dataRows(table)[0]).toHaveTextContent('2026-11-012')

    expect(api.find('GET', '/api/pr/list/')).toHaveLength(listCallsBefore)
    expect(api.mutations()).toHaveLength(0)
  })

  it('explains an empty filter result and offers to clear it', async () => {
    signIn(adminUser)
    installApi(routes)
    const { user } = renderAt('/admin')
    const table = await openMonitor(user)

    await user.type(screen.getByLabelText(/search numbered prs/i), 'no such office')
    expect(within(table).getByText(/no purchase requests match/i)).toBeInTheDocument()
    await user.click(within(table).getByRole('button', { name: /clear filters/i }))
    expect(dataRows(table)).toHaveLength(10)
  })
})

describe('supplier management list', () => {
  const suppliers = [
    { id: 1, company_name: 'Bravo Trading', status: 'Approved', email: 'b@x.ph' },
    { id: 2, company_name: 'Alpha Supplies', status: 'Pending Review', email: 'a@x.ph' },
    { id: 3, company_name: 'Charlie Corp', status: 'Rejected', email: 'c@x.ph' },
  ]
  const supplierRoutes = { ...routes, 'GET /api/suppliers/': { json: suppliers } }
  const names = () => screen.getAllByRole('listitem').map((item) => item.querySelector('.supplier-name')?.textContent).filter(Boolean)

  it('filters by status and sorts by name in both directions', async () => {
    signIn(adminUser)
    const api = installApi(supplierRoutes)
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /supplier management/i })[0])
    await screen.findByText('Bravo Trading')

    expect(names()).toEqual(['Bravo Trading', 'Alpha Supplies', 'Charlie Corp'])
    await user.selectOptions(screen.getByLabelText(/^sort by$/i), 'name:descending')
    expect(names()).toEqual(['Charlie Corp', 'Bravo Trading', 'Alpha Supplies'])
    await user.selectOptions(screen.getByLabelText(/^sort by$/i), 'name:ascending')
    expect(names()).toEqual(['Alpha Supplies', 'Bravo Trading', 'Charlie Corp'])
    await user.selectOptions(screen.getByLabelText(/^sort by$/i), 'default')
    expect(names()).toEqual(['Bravo Trading', 'Alpha Supplies', 'Charlie Corp'])

    await user.selectOptions(screen.getByLabelText(/^status$/i), 'Pending Review')
    expect(names()).toEqual(['Alpha Supplies'])
    expect(api.mutations()).toHaveLength(0)
  })
})

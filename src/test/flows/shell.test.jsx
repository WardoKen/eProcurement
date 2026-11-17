// App shell: landmarks, current-page state, breadcrumbs, locked items.
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, supplierUser } from '../fixtures'

describe('app shell', () => {
  it('offers a skip link to the main landmark', () => {
    installApi({})
    renderAt('/')
    expect(screen.getByRole('link', { name: /skip to main content/i })).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
  })

  it('opens the process guide from the home page', async () => {
    installApi({})
    const { user } = renderAt('/')

    await user.click(screen.getByRole('link', { name: /view the process/i }))
    expect(screen.getByRole('heading', { level: 1, name: /how a request becomes a quotation/i })).toBeInTheDocument()
    const index = screen.getByRole('navigation', { name: 'Process stages' })
    expect(within(index).getByRole('link', { name: /bac review and pr numbering/i })).toHaveAttribute('href', '#stage-review')
    expect(within(index).getAllByRole('link')).toHaveLength(5)
    expect(screen.queryByText(/evaluation|purchase order|not yet/i)).not.toBeInTheDocument()
  })

  it('marks the active Admin tab and shows breadcrumbs off the dashboard', async () => {
    signIn(adminUser)
    installApi({
      'GET /api/admin/dashboard-summary/': { json: {} },
      'GET /api/pr/list/': { json: [] },
      'GET /api/suppliers/': { json: [] },
      'GET /api/buyer-accounts/': { json: [] },
    })
    const { user } = renderAt('/admin')

    expect(screen.getByRole('button', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'End user accounts' }))
    expect(screen.getByRole('button', { name: 'End user accounts' })).toHaveAttribute('aria-current', 'page')
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(crumbs).toHaveTextContent('Admin portal')
    expect(crumbs).toHaveTextContent('End user accounts')
  })

  it('keeps procurement items visible but marked for unapproved suppliers', () => {
    signIn({ ...supplierUser, supplier_status: 'Pending Review' })
    installApi({ 'GET /api/suppliers/7/dashboard/': { json: {} }, 'GET /api/suppliers/7/opportunities/': { json: { opportunities: [] } } })
    renderAt('/supplier')

    expect(screen.getByRole('button', { name: /^rfqs\s*\(available after bac approval\)$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^profile$/i })).toBeInTheDocument()
  })

  it('approved suppliers see no lock markers', () => {
    signIn(supplierUser)
    installApi({ 'GET /api/suppliers/7/dashboard/': { json: {} }, 'GET /api/suppliers/7/opportunities/': { json: { opportunities: [] } } })
    renderAt('/supplier')

    expect(screen.getByRole('button', { name: /^rfqs$/i })).toBeInTheDocument()
  })
})

// App shell: landmarks, current-page state, breadcrumbs, locked items.
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, supplierUser } from '../fixtures'

describe('app shell', () => {
  it('offers a skip link to the main landmark', () => {
    installApi({})
    renderAt('/')
    expect(screen.getByRole('link', { name: /skip to main content/i })).toHaveAttribute('href', '#main-content')
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content')
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

    await user.click(screen.getByRole('button', { name: 'End User Accounts' }))
    expect(screen.getByRole('button', { name: 'End User Accounts' })).toHaveAttribute('aria-current', 'page')
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(crumbs).toHaveTextContent('Admin Portal')
    expect(crumbs).toHaveTextContent('End User Accounts')
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

import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { installApi, renderAt } from '../harness'

const loginRoutes = (user) => ({
  'POST /api/login/': { json: { user } },
  // Landing pages load data right after the redirect; give them empty data.
  'GET /api/admin/dashboard-summary/': { json: {} },
  'GET /api/pr/list/': { json: [] },
  'GET /api/suppliers/': { json: [] },
  'GET /api/pr/next-number/': { json: { pr_no: '2026-11-001' } },
  [`GET /api/suppliers/${user.supplier_id}/profile/`]: { json: { company_name: 'Acme' } },
  [`GET /api/suppliers/${user.supplier_id}/dashboard/`]: { json: {} },
  [`GET /api/suppliers/${user.supplier_id}/opportunities/`]: { json: { opportunities: [] } },
})

async function logIn(user, { role, username, password }) {
  await user.selectOptions(document.querySelector('select[name="role"]'), role)
  await user.type(document.querySelector('input[name="username"]'), username)
  await user.type(document.querySelector('input[name="password"]'), password)
  await user.click(screen.getByRole('button', { name: /^log in$/i }))
}

describe('login per role', () => {
  it.each([
    ['admin', { role: 'admin', username: 'bac' }, '/admin'],
    ['buyer', { role: 'buyer', username: 'enduser1', name: 'Ana' }, '/buyer'],
    ['supplier', { role: 'supplier', username: 'acme', supplier_id: 7, supplier_status: 'Approved' }, '/supplier'],
  ])('%s signs in and lands on its portal', async (role, accountUser, landing) => {
    const api = installApi(loginRoutes(accountUser))
    const { user } = renderAt('/login')

    await logIn(user, { role, username: accountUser.username, password: 'secret123' })

    await waitFor(() => expect(window.location.pathname).toBe(landing))
    expect(api.find('POST', '/api/login/')).toHaveLength(1)
    expect(api.find('POST', '/api/login/')[0].body).toEqual({
      username: accountUser.username,
      password: 'secret123',
      role,
    })
    expect(JSON.parse(window.sessionStorage.getItem('eProcureUser')).role).toBe(role)
    if (role === 'supplier') {
      expect(window.sessionStorage.getItem('supplier_id')).toBe('7')
      expect(window.sessionStorage.getItem('supplier_status')).toBe('Approved')
    }
  })

  it('rejected credentials keep the user on the login page', async () => {
    const api = installApi({ 'POST /api/login/': { status: 401, json: { message: 'Invalid username or password.' } } })
    const { user } = renderAt('/login')

    await logIn(user, { role: 'buyer', username: 'nobody', password: 'wrongpass' })

    await waitFor(() => expect(api.find('POST', '/api/login/')).toHaveLength(1))
    expect(window.location.pathname).toBe('/login')
    expect(window.sessionStorage.getItem('eProcureUser')).toBeNull()
  })

  it('empty credentials never reach the server', async () => {
    const api = installApi({})
    const { user } = renderAt('/login')

    await user.click(screen.getByRole('button', { name: /^log in$/i }))

    expect(api.find('POST', '/api/login/')).toHaveLength(0)
  })
})

describe('password reset', () => {
  it('forgot password posts the identifier', async () => {
    const api = installApi({ 'POST /api/forgot-password/': { json: { message: 'ok' } } })
    const { user } = renderAt('/forgot-password')

    await user.type(screen.getByPlaceholderText(/username or email/i), ' ana@ctu.edu.ph ')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    await waitFor(() => expect(api.mutations()).toHaveLength(1))
    expect(api.mutations()[0]).toEqual({
      method: 'POST',
      path: '/api/forgot-password/',
      body: { username_or_email: 'ana@ctu.edu.ph' },
    })
  })

  it('reset password posts token and new password, then returns to login', async () => {
    const api = installApi({ 'POST /api/reset-password/': { json: { message: 'ok' } } })
    const { user } = renderAt('/reset-password?token=abc123')

    await user.type(screen.getByPlaceholderText(/^new password/i), 'newsecret1')
    await user.type(screen.getByPlaceholderText(/confirm new password/i), 'newsecret1')
    await user.click(screen.getByRole('button', { name: /reset password/i }))

    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(api.mutations()).toEqual([
      { method: 'POST', path: '/api/reset-password/', body: { token: 'abc123', new_password: 'newsecret1' } },
    ])
  })

  it('mismatched passwords never reach the server', async () => {
    const api = installApi({})
    const { user } = renderAt('/reset-password?token=abc123')

    await user.type(screen.getByPlaceholderText(/^new password/i), 'newsecret1')
    await user.type(screen.getByPlaceholderText(/confirm new password/i), 'different1')
    await user.click(screen.getByRole('button', { name: /reset password/i }))

    expect(api.mutations()).toHaveLength(0)
  })
})

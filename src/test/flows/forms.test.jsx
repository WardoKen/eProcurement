// Field-level validation: errors sit on the field, are announced, and the
// rules/messages are the same as before.
import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser } from '../fixtures'

describe('supplier registration wizard validation', () => {
  it('marks each invalid field, focuses the summary and links to the field', async () => {
    installApi({ 'GET /api/categories/': { json: [{ id: 1, name: 'IT Equipment' }] } })
    const { user } = renderAt('/supplier/register')

    await user.type(screen.getByLabelText(/company \/ supplier name/i), 'Acme')
    await user.type(screen.getByLabelText(/email address/i), 'not-an-email')
    await user.click(screen.getByRole('button', { name: /^continue$/i }))

    const summary = await screen.findByRole('alert')
    await waitFor(() => expect(summary).toHaveFocus())
    expect(screen.getByLabelText(/company \/ supplier name/i)).not.toHaveAttribute('aria-invalid')
    const email = screen.getByLabelText(/email address/i)
    expect(email).toHaveAttribute('aria-invalid', 'true')
    expect(email).toHaveAccessibleDescription('Email address must be valid')
    expect(screen.getByLabelText(/business address/i)).toHaveAccessibleDescription('Business Address is required')

    await user.click(screen.getByRole('button', { name: 'Email address must be valid' }))
    expect(email).toHaveFocus()

    await user.clear(email)
    await user.type(email, 'sales@acme.ph')
    expect(email).not.toHaveAttribute('aria-invalid')
  })

  it('announces the current step', async () => {
    installApi({ 'GET /api/categories/': { json: [] } })
    renderAt('/supplier/register')

    const steps = screen.getByRole('list', { name: /registration progress/i })
    const current = [...steps.querySelectorAll('[role="listitem"]')].find((item) => item.getAttribute('aria-current') === 'step')
    expect(current).toHaveTextContent(/company & account setup.*current step, 1 of 4/i)
  })
})

describe('End User account form validation', () => {
  it('puts the mismatch on Confirm Password and the length rule on Password', async () => {
    signIn(adminUser)
    const api = installApi({
      'GET /api/admin/dashboard-summary/': { json: {} },
      'GET /api/pr/list/': { json: [] },
      'GET /api/suppliers/': { json: [] },
      'GET /api/buyer-accounts/': { json: [] },
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /end user accounts/i })[0])

    await user.type(await screen.findByPlaceholderText('End User name'), 'Ana Cruz')
    await user.type(screen.getByPlaceholderText('enduser.username'), 'ana')
    await user.type(screen.getByPlaceholderText('enduser@office.edu'), 'ana@ctu.edu.ph')
    await user.type(screen.getByPlaceholderText('Procurement Office'), 'ICT')
    await user.type(screen.getByLabelText(/^password/i), 'short')
    await user.type(screen.getByLabelText(/^confirm password/i), 'other')
    await user.click(screen.getByRole('button', { name: /create end user account/i }))

    const confirm = screen.getByLabelText(/^confirm password/i)
    expect(confirm).toHaveAccessibleDescription('Passwords do not match.')
    expect(confirm).toHaveFocus()

    await user.clear(confirm)
    await user.type(confirm, 'short')
    await user.click(screen.getByRole('button', { name: /create end user account/i }))
    expect(screen.getByLabelText(/^password/i)).toHaveAccessibleDescription('Password must be at least 8 characters long.')
    expect(api.find('POST', '/api/register/')).toHaveLength(0)
  })
})

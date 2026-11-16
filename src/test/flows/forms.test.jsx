// Field-level validation: errors sit on the field, are announced, and the
// rules/messages are the same as before.
import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { installApi, renderAt } from '../harness'

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

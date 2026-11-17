// Process 3: PR scanning and extraction (End User).
// The extracted data must never be saved until the user confirms it.
import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { installApi, pdfFile, renderAt, signIn } from '../harness'
import { buyerUser } from '../fixtures'

const extraction = {
  filename: 'pr-2026.pdf',
  rawText: 'PURCHASE REQUEST ...',
  fields: {
    entityName: 'Cebu Technological University',
    officeSection: 'ICT Office',
    fundCluster: '01',
    responsibilityCenterCode: 'RC-100',
    purpose: 'Laptops for the computer laboratory',
    date: '2026-11-01',
    requested_by_name: 'Ana Cruz',
    requested_items: [
      { stock_no: 'SP-1', unit: 'pc', description: 'Laptop, 16GB RAM', quantity: '2', unit_cost: '1,000.00', total_cost: '2,000.00' },
    ],
  },
  signature_validation: {
    summary: { can_save: true, required_detected: 3, required_total: 3, status: 'complete', message: 'All required signatures detected.' },
    signatories: {},
  },
}

const routes = {
  'GET /api/pr/next-number/': { json: { pr_no: '2026-11-001' } },
  'POST /api/upload/': { json: extraction },
  'POST /api/pr/': { json: { id: 42, pr_no: '', status: 'uploaded', created_at: '2026-11-01T08:00:00Z' } },
  'GET /api/pr/list/': { json: [] },
}

async function uploadPr(user) {
  const input = document.querySelector('input[type="file"]')
  await user.upload(input, pdfFile('pr-2026.pdf'))
  await user.click(screen.getByRole('button', { name: /confirm upload/i }))
  await screen.findByText(/uploaded and its details were extracted/i)
  await user.click(screen.getByRole('button', { name: /continue reviewing/i }))
}

describe('End User PR upload and review', () => {
  it('extraction alone never creates a Purchase Request', async () => {
    signIn(buyerUser)
    const api = installApi(routes)
    const { user } = renderAt('/buyer')

    await uploadPr(user)

    expect(api.find('POST', '/api/upload/')).toEqual([
      { method: 'POST', path: '/api/upload/', body: [['file', 'file:pr-2026.pdf']] },
    ])
    expect(api.find('POST', '/api/pr/')).toHaveLength(0)
    // Saving stays blocked until the declaration is acknowledged.
    expect(screen.getByRole('button', { name: /save purchase request/i })).toBeDisabled()
  })

  it('saves the reviewed record only after the declaration is acknowledged', async () => {
    signIn(buyerUser)
    const api = installApi(routes)
    const { user } = renderAt('/buyer')

    await uploadPr(user)
    await user.click(screen.getByRole('checkbox', { name: /read and understood this declaration/i }))
    await user.click(screen.getByRole('button', { name: /save purchase request/i }))

    await screen.findByText(/purchase request submitted successfully/i)
    const saves = api.find('POST', '/api/pr/')
    expect(saves).toHaveLength(1)
    expect(saves[0].body).toMatchSnapshot()
  })

  it('a save rejected for missing signatures keeps the form and the user input', async () => {
    signIn(buyerUser)
    const api = installApi({
      ...routes,
      'POST /api/pr/': { status: 400, json: { error: 'Missing signatures', missing_signatures: ['Approved By'] } },
    })
    const { user } = renderAt('/buyer')

    await uploadPr(user)
    await user.click(screen.getByRole('checkbox', { name: /read and understood this declaration/i }))
    await user.click(screen.getByRole('button', { name: /save purchase request/i }))

    await waitFor(() => expect(api.find('POST', '/api/pr/')).toHaveLength(1))
    expect(await screen.findByText(/missing signatures: approved by/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('Cebu Technological University')).toBeInTheDocument()
  })

  it('a signature marked "Please confirm" blocks the save until the reviewer confirms it', async () => {
    signIn(buyerUser)
    const row = (key, label, state, extra = {}) => ({ key, label, state, required: key !== 'twg', name: '', ...extra })
    const api = installApi({
      ...routes,
      'POST /api/upload/': {
        json: {
          ...extraction,
          signature_validation: {
            summary: {
              can_save: false,
              needs_confirmation: true,
              required_detected: 2,
              required_total: 3,
              status: 'needs_confirmation',
              message: 'Please confirm the signatures marked for review against the original document.',
              missing_signatures: [],
              uncertain_signatures: ['Funds Available'],
              uncertain_keys: ['funds_available'],
              unverifiable_signatures: [],
            },
            signatories: {
              requested_by: row('requested_by', 'Requested By', 'present'),
              funds_available: row('funds_available', 'Funds Available', 'uncertain', { reason: 'weak_mark' }),
              approved_by: row('approved_by', 'Approved By', 'present'),
              twg: row('twg', 'TWG Verified By', 'present'),
            },
          },
        },
      },
    })
    const { user } = renderAt('/buyer')

    await uploadPr(user)
    expect(screen.getAllByText('Please Confirm').length).toBeGreaterThan(0)
    expect(screen.getByText(/too faint or small to be sure/i)).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: /read and understood this declaration/i }))
    // Declaration alone is not enough: the uncertain signature is unconfirmed.
    expect(screen.getByRole('button', { name: /save purchase request/i })).toBeDisabled()
    expect(screen.getByText(/confirm 1 marked "please confirm"/i)).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: /i checked the document: funds available is signed/i }))
    const save = screen.getByRole('button', { name: /save purchase request/i })
    expect(save).toBeEnabled()
    await user.click(save)

    await screen.findByText(/purchase request submitted successfully/i)
    const saves = api.find('POST', '/api/pr/')
    expect(saves).toHaveLength(1)
    expect(saves[0].body.fields.signature_confirmations).toEqual(['funds_available'])
  })
})

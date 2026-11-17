// Every RFQ record shows where it is in RFQ Prepared → RFQ Sent → Quotation Received.
import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, numberedPr, prDetails, supplierMatch, supplierRfq, supplierUser } from '../fixtures'

const currentStep = (list) => within(list).getAllByRole('listitem').find((item) => item.getAttribute('aria-current') === 'step')

describe('RFQ workflow indicator', () => {
  it('supplier RFQ detail is worded for the supplier, with filling in the RFQ as their next step', async () => {
    signIn(supplierUser)
    installApi({
      'GET /api/suppliers/7/profile/': { json: { company_name: 'Acme' } },
      'GET /api/suppliers/7/dashboard/': { json: {} },
      'GET /api/suppliers/7/opportunities/': { json: { opportunities: [] } },
      'GET /api/suppliers/7/rfqs/': { json: { rfqs: [supplierRfq] } },
    })
    const { user } = renderAt('/supplier')
    await user.click(screen.getAllByRole('button', { name: /^rfqs$/i })[0])
    await user.click(await screen.findByRole('button', { name: /view rfq rfq-2026-001/i }))

    const stepper = screen.getByRole('list', { name: /your progress on rfq-2026-001/i })
    const steps = within(stepper).getAllByRole('listitem')
    expect(steps.map((step) => step.querySelector('.procurement-step-label').textContent))
      .toEqual(['RFQ Received', 'Fill In & Sign', 'Upload Quotation'])
    expect(currentStep(stepper)).toHaveTextContent(/fill in & sign.*your action needed/i)
    expect(steps[2]).toHaveTextContent(/not uploaded yet/i)
    expect(screen.getByText(/current status:/i)).toHaveTextContent('Awaiting Your Quotation')
    expect(screen.queryByText(/awaiting supplier/i)).not.toBeInTheDocument()
  })

  it('RFQ Preparation moves from "not saved" to a prepared draft after Save', async () => {
    signIn(adminUser)
    installApi({
      'GET /api/admin/dashboard-summary/': { json: {} },
      'GET /api/suppliers/': { json: [] },
      'GET /api/pr/list/': { json: [numberedPr] },
      'GET /api/procurement-modes/': { json: { modes: ['Shopping'] } },
      'GET /api/pr/43/supplier-match/': { json: supplierMatch },
      'GET /api/pr/43/details/': { json: { ...prDetails, pr_no: '2026-11-001' } },
      'GET /api/pr/43/rfq/': { json: { rfqs: [] } },
      'POST /api/pr/43/rfq/': ({ body }) => ({ json: { ...body, id: 9, rfq_no: 'RFQ-2026-001', status: 'draft', supplier: { id: 7 } } }),
    })
    const { user } = renderAt('/admin')
    await user.click(screen.getAllByRole('button', { name: /^purchase requests/i })[0])
    await user.click(await screen.findByRole('button', { name: /continue matching/i }))
    await user.click(await screen.findByRole('button', { name: /request quotation/i }))

    expect(screen.getByText(/current status:/i)).toHaveTextContent('Not saved yet')
    await screen.findByRole('heading', { name: /email to supplier/i })
    await user.type(document.querySelector('input[list="procurement-mode-options"]'), 'Shopping')
    await user.click(screen.getByRole('button', { name: /^save rfq/i }))

    await waitFor(() => expect(screen.getByText(/current status:/i)).toHaveTextContent('Draft (not sent)'))
    const stepper = screen.getByRole('list', { name: /rfq progress for acme/i })
    expect(currentStep(stepper)).toHaveTextContent(/rfq prepared/i)
  })
})

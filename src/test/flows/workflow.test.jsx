// Every RFQ record shows where it is in RFQ → Quotation → Evaluation → PO.
import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import { installApi, renderAt, signIn } from '../harness'
import { adminUser, numberedPr, prDetails, supplierMatch, supplierRfq, supplierUser } from '../fixtures'

const currentStep = (list) => within(list).getAllByRole('listitem').find((item) => item.getAttribute('aria-current') === 'step')

describe('RFQ workflow indicator', () => {
  it('supplier RFQ detail shows the quotation as the step in progress', async () => {
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

    const stepper = screen.getByRole('list', { name: /progress of rfq-2026-001/i })
    expect(currentStep(stepper)).toHaveTextContent(/quotation received.*awaiting supplier/i)
    expect(within(stepper).getByText('PO Issuance').closest('li')).toHaveTextContent(/not yet available/i)
    expect(screen.getByText(/current status:/i)).toHaveTextContent('Awaiting Supplier Response')
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
    await user.click(screen.getAllByRole('button', { name: /pr review & monitoring/i })[0])
    await user.click(await screen.findByRole('button', { name: /continue matching/i }))
    await user.click(await screen.findByRole('button', { name: /request quotation/i }))

    expect(screen.getByText(/current status:/i)).toHaveTextContent('Not saved yet')
    await waitFor(() => expect(screen.getByDisplayValue('Request for Quotation - PR 2026-11-001')).toBeInTheDocument())
    await user.type(document.querySelector('input[list="procurement-mode-options"]'), 'Shopping')
    await user.click(screen.getByRole('button', { name: /^save rfq/i }))

    await waitFor(() => expect(screen.getByText(/current status:/i)).toHaveTextContent('Draft (not sent)'))
    const stepper = screen.getByRole('list', { name: /rfq progress for acme/i })
    expect(currentStep(stepper)).toHaveTextContent(/rfq prepared/i)
  })
})

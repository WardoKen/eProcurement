import { describe, expect, it } from 'vitest'
import { PIPELINE_STAGES, STAGE_COUNT, prPipelinePosition } from './pipeline'

describe('the procurement line', () => {
  it('ends at Quotation: evaluation, award and the purchase order are out of scope', () => {
    expect(PIPELINE_STAGES.map((stage) => stage.label)).toEqual(['Purchase request', 'Posting', 'RFQ', 'Quotation'])
  })

  it.each([
    [{ status: 'uploaded' }, 0, 'Submitted'],
    [{ status: 'in_review' }, 0, 'In BAC review'],
    [{ status: 'matched' }, 1, 'Matched, not posted'],
    [{ status: 'matched', is_posted: true }, 2, 'Posted, RFQs not sent yet'],
    [{ status: 'matched', is_posted: true, rfq_sent_count: 3, rfq_response_count: 1 }, 3, '1 of 3 quotations in'],
    [{ status: 'matched', is_posted: true, rfq_sent_count: 3, rfq_response_count: 3 }, STAGE_COUNT, 'All quotations received'],
    [{ status: 'approved' }, STAGE_COUNT, 'Completed'],
  ])('places %o at station %i', (pr, index, label) => {
    expect(prPipelinePosition(pr)).toEqual({ index, stopped: false, label })
  })

  it('stops a rejected PR at the request', () => {
    expect(prPipelinePosition({ status: 'rejected' })).toEqual({ index: 0, stopped: true, label: 'Rejected at review' })
  })
})

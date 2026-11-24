// The procurement stations eProcure covers and where a PR sits on them
// (DESIGN.md, "The line"). Used by src/components/ui/PipelineLine.jsx.
//
// The line ends at Quotation: evaluation, award and the purchase order are
// out of eProcure's scope and happen outside the system.

export const PIPELINE_STAGES = [
  { key: 'request', label: 'Purchase request' },
  { key: 'posting', label: 'Posting' },
  { key: 'rfq', label: 'RFQ' },
  { key: 'quotation', label: 'Quotation' },
]

export const STAGE_COUNT = PIPELINE_STAGES.length

// Where a PR is on the line, from fields the PR list already returns:
// status, is_posted, rfq_sent_count and rfq_response_count.
// Returns { index, stopped, label } where index is the current station
// (STAGE_COUNT once every station is passed).
export function prPipelinePosition(pr) {
  if (!pr) return { index: -1, stopped: false, label: '' }
  const status = pr.status
  const sent = Number(pr.rfq_sent_count || 0)
  const responded = Number(pr.rfq_response_count || 0)
  if (status === 'rejected') return { index: 0, stopped: true, label: 'Rejected at review' }
  if (status === 'approved') return { index: STAGE_COUNT, stopped: false, label: 'Completed' }
  if (status === 'uploaded' || status === 'in_review' || !status) {
    return { index: 0, stopped: false, label: status === 'in_review' ? 'In BAC review' : 'Submitted' }
  }
  if (sent > 0 && responded >= sent) return { index: STAGE_COUNT, stopped: false, label: 'All quotations received' }
  if (sent > 0) return { index: 3, stopped: false, label: `${responded} of ${sent} quotations in` }
  if (pr.is_posted) return { index: 2, stopped: false, label: 'Posted, RFQs not sent yet' }
  return { index: 1, stopped: false, label: 'Matched, not posted' }
}

export const pipelineStateFor = (index, current, stopped) => {
  if (stopped && index === current) return 'stopped'
  if (index < current) return 'done'
  if (index === current) return 'now'
  return 'later'
}

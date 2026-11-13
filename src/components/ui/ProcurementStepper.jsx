import { Check } from 'lucide-react'

// Visible position of one RFQ record in the RFQ → Quotation → Evaluation → PO
// workflow. Display only: it reads the RFQ's stored status and never changes
// it. Evaluation and PO Issuance are shown as not yet available because
// eProcure has no backend for them yet (see docs/ui-audit.md §3).
const STEPS = [
  { key: 'prepared', label: 'RFQ Prepared' },
  { key: 'sent', label: 'RFQ Sent' },
  { key: 'quotation', label: 'Quotation Received' },
  { key: 'evaluation', label: 'Evaluation', unavailable: true },
  { key: 'po', label: 'PO Issuance', unavailable: true },
]

// Index of the step in progress for each stored RFQ status. A sent RFQ has
// finished "RFQ Sent" and is waiting on the quotation.
const CURRENT_INDEX = {
  draft: 0,
  sent: 2,
  quotation_received: 3,
  completed: 3,
}

const CURRENT_TEXT = { 0: 'Being prepared', 2: 'Awaiting supplier' }

export default function ProcurementStepper({ status, label = 'RFQ workflow progress' }) {
  const current = status in CURRENT_INDEX ? CURRENT_INDEX[status] : -1
  return (
    <ol className="procurement-stepper" aria-label={label}>
      {STEPS.map((step, index) => {
        let state = 'upcoming'
        if (step.unavailable) state = 'unavailable'
        else if (index < current || (index === current && status === 'completed')) state = 'done'
        else if (index === current) state = 'current'
        const stateText = {
          done: 'Completed',
          current: CURRENT_TEXT[index] || 'In progress',
          upcoming: 'Not started',
          unavailable: 'Not yet available in eProcure',
        }[state]
        return (
          <li
            key={step.key}
            className={`procurement-step is-${state}`}
            aria-current={state === 'current' ? 'step' : undefined}
          >
            <span className="procurement-step-marker" aria-hidden="true">
              {state === 'done' ? <Check size={12} /> : index + 1}
            </span>
            <span className="procurement-step-text">
              <span className="procurement-step-label">{step.label}</span>
              <span className="procurement-step-state">{stateText}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

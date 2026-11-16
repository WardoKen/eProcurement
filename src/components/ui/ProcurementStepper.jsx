import { Check } from 'lucide-react'

// Visible position of one RFQ record in the RFQ → Quotation workflow, the part
// of procurement eProcure handles. Display only: it reads the RFQ's stored
// status and never changes it.
//
// The same RFQ is described from two sides. The BAC sees its own progress
// (prepare, send, receive); a supplier sees what it has received and what it
// still has to do.
const WORKFLOWS = {
  bac: {
    steps: [
      { key: 'prepared', label: 'RFQ Prepared' },
      { key: 'sent', label: 'RFQ Sent' },
      { key: 'quotation', label: 'Quotation Received' },
    ],
    // Index of the step in progress for each stored RFQ status. A sent RFQ has
    // finished "RFQ Sent" and is waiting on the quotation; once a quotation is
    // in (or the RFQ is completed) every step is done.
    currentIndex: { draft: 0, sent: 2, quotation_received: 3, completed: 3 },
    currentText: { 0: 'Being prepared', 2: 'Awaiting supplier' },
    doneText: {},
    upcomingText: {},
  },
  supplier: {
    steps: [
      { key: 'received', label: 'RFQ Received' },
      { key: 'complete', label: 'Fill In & Sign' },
      { key: 'upload', label: 'Upload Quotation' },
    ],
    // A supplier only ever sees an RFQ once it is sent, so "RFQ Received" is
    // already done and filling in the form is the next action.
    currentIndex: { sent: 1, quotation_received: 3, completed: 3 },
    currentText: { 1: 'Your action needed' },
    doneText: { 0: 'From the BAC', 1: 'Done', 2: 'Submitted to the BAC' },
    upcomingText: { 2: 'Not uploaded yet' },
  },
}

export default function ProcurementStepper({ status, audience = 'bac', label = 'RFQ workflow progress' }) {
  const workflow = WORKFLOWS[audience] || WORKFLOWS.bac
  const current = status in workflow.currentIndex ? workflow.currentIndex[status] : -1
  return (
    <ol className="procurement-stepper" aria-label={label}>
      {workflow.steps.map((step, index) => {
        let state = 'upcoming'
        if (index < current) state = 'done'
        else if (index === current) state = 'current'
        const stateText = {
          done: workflow.doneText[index] || 'Completed',
          current: workflow.currentText[index] || 'In progress',
          upcoming: workflow.upcomingText[index] || 'Not started',
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

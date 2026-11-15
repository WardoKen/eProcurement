import { Link } from 'react-router-dom'
import { ArrowRight, ChevronRight, FileText } from 'lucide-react'

// Public walkthrough of the procurement workflow, opened from the home page's
// "View the process" link. Static content only: the stages and status names
// mirror PurchaseRequest.STATUS_CHOICES and RFQ.STATUS_CHOICES in the backend,
// and Evaluation / PO Issuance are marked as not yet handled in eProcure (the
// same rule ProcurementStepper follows).
const ROLES = {
  enduser: 'End User',
  bac: 'BAC Secretariat',
  supplier: 'Supplier',
}

const STAGES = [
  {
    id: 'upload',
    title: 'Upload the signed Purchase Request',
    role: 'enduser',
    summary: 'The End User submits the original, signed PR. eProcure keeps the source file and reads its details into a structured record.',
    steps: [
      'Upload the signed PR as a PDF or clear image.',
      'OCR extracts the entity, fund cluster, office, line items and totals.',
      'Acknowledge the submission declaration before sending.',
    ],
    input: 'Signed Purchase Request',
    output: 'Extracted PR record',
    statuses: [{ label: 'Uploaded', scope: 'PR' }],
  },
  {
    id: 'review',
    title: 'BAC review and PR numbering',
    role: 'bac',
    summary: 'The BAC Secretariat checks the extracted record against the original document before anything goes to suppliers.',
    steps: [
      'Compare extracted fields side by side with the source file.',
      'Confirm the signatories: requested by, funds available, approved by, and TWG verification.',
      'Assign the official PR number, or reject the request with a reason.',
    ],
    input: 'Extracted PR record',
    output: 'Numbered, validated PR',
    statuses: [{ label: 'In Review', scope: 'PR' }, { label: 'Approved', scope: 'PR' }, { label: 'Rejected', scope: 'PR' }],
  },
  {
    id: 'matching',
    title: 'Group items and match suppliers',
    role: 'bac',
    summary: 'Line items are grouped by procurement category, so one PR can lead to several RFQs without losing the link back to the request.',
    steps: [
      'Sort line items into category groups.',
      'Match each group with approved suppliers registered in that category.',
      'Add other suppliers to a group by hand when needed.',
    ],
    input: 'Validated PR',
    output: 'Category groups with matched suppliers',
    statuses: [{ label: 'Matched', scope: 'PR' }],
  },
  {
    id: 'rfq',
    title: 'Prepare and send the RFQ',
    role: 'bac',
    summary: 'A Request for Quotation is generated for each category group and sent to the matched suppliers.',
    steps: [
      'Review the RFQ draft and set the quotation basis (by lot or by line).',
      'Send it. Each supplier is notified and can download the RFQ PDF.',
    ],
    input: 'Category group',
    output: 'RFQ document',
    statuses: [{ label: 'Draft', scope: 'RFQ' }, { label: 'Sent', scope: 'RFQ' }],
  },
  {
    id: 'quotation',
    title: 'Supplier quotation',
    role: 'supplier',
    summary: 'The supplier fills in the RFQ on paper, signs it, and uploads the completed document to the same RFQ.',
    steps: [
      'Download and print the RFQ PDF.',
      'Fill in brand and model, unit prices, totals and contact details, then sign.',
      'Scan the whole RFQ as one PDF and upload it. While the RFQ is open, you can replace the upload; the earlier file is kept for the BAC.',
    ],
    input: 'RFQ document',
    output: 'Signed quotation on record',
    statuses: [{ label: 'Quotation Received', scope: 'RFQ' }, { label: 'Completed', scope: 'RFQ' }],
  },
  {
    id: 'evaluation',
    title: 'Evaluation and Purchase Order',
    role: 'bac',
    summary: 'The BAC compares quotations and issues the Purchase Order. These steps happen outside eProcure for now.',
    steps: [
      'Quotations are evaluated under the BAC\'s usual procedure.',
      'The Purchase Order is issued through existing office channels.',
    ],
    input: 'Received quotations',
    output: 'Award and Purchase Order',
    statuses: [],
    unavailable: true,
  },
]

const REQUIREMENTS = [
  'DTI / SEC Registration',
  'Business Permit',
  'BIR Form 2303',
  'Tax Clearance',
  'PhilGEPS Certificate',
  'CDA Certificate (if applicable)',
]

const stageNumber = (index) => String(index + 1).padStart(2, '0')

export default function ProcessGuide() {
  return (
    <div className="page-content institutional-home process-guide">
      <section className="procurement-hero process-hero">
        <div className="procurement-hero-copy">
          <p className="hero-kicker">eProcure / The procurement process</p>
          <h1>How a request becomes a quotation.</h1>
          <p className="hero-lede">
            Every Purchase Request follows the same path through eProcure, from the End User's signed document
            to a supplier's quotation. Each stage keeps its own record, so anyone involved can see where a request is and who acts next.
          </p>
          <div className="hero-actions">
            <Link to="/login" className="btn-primary">Access eProcure</Link>
            <Link to="/faq" className="hero-text-link">Read the FAQ <ChevronRight size={16} aria-hidden="true" /></Link>
          </div>
        </div>

        <nav className="procurement-activity-panel process-index" aria-label="Process stages">
          <div className="activity-panel-head">
            <span className="document-tab">Stage index</span>
            <span className="activity-panel-state">{STAGES.length} stages</span>
          </div>
          <ol className="activity-timeline">
            {STAGES.map((stage, index) => (
              <li key={stage.id} className={stage.unavailable ? 'is-unavailable' : undefined}>
                <span>{stageNumber(index)}</span>
                <div>
                  <a href={`#stage-${stage.id}`}>{stage.title}</a>
                  <small>{stage.unavailable ? 'Not yet handled in eProcure' : ROLES[stage.role]}</small>
                </div>
              </li>
            ))}
          </ol>
        </nav>
      </section>

      <section className="home-role-strip" aria-label="Who acts at each stage">
        {Object.entries(ROLES).map(([key, label], index) => {
          const owned = STAGES
            .map((stage, stageIndex) => ({ stage, stageIndex }))
            .filter(({ stage }) => stage.role === key && !stage.unavailable)
          return (
            <article key={key}>
              <span className="role-index">{stageNumber(index)}</span>
              <div>
                <h2>{label}</h2>
                <p>Acts in stage{owned.length === 1 ? '' : 's'} {owned.map(({ stageIndex }) => stageNumber(stageIndex)).join(', ')}.</p>
              </div>
            </article>
          )
        })}
      </section>

      <section className="process-stages" aria-labelledby="process-stages-title">
        <div className="process-section-head">
          <p className="section-kicker">Stage by stage</p>
          <h2 id="process-stages-title">One request, one record at every step.</h2>
        </div>

        <ol className="process-stage-list">
          {STAGES.map((stage, index) => (
            <li
              key={stage.id}
              id={`stage-${stage.id}`}
              className={`process-stage${stage.unavailable ? ' is-unavailable' : ''}`}
              aria-labelledby={`stage-${stage.id}-title`}
            >
              <div className="process-stage-marker" aria-hidden="true">{stageNumber(index)}</div>

              <div className="process-stage-body">
                <p className="process-stage-role">
                  {stage.unavailable ? 'Outside eProcure' : ROLES[stage.role]}
                </p>
                <h3 id={`stage-${stage.id}-title`}>{stage.title}</h3>
                <p className="process-stage-summary">{stage.summary}</p>
                <ul className="process-stage-steps">
                  {stage.steps.map((step) => <li key={step}>{step}</li>)}
                </ul>
              </div>

              <aside className="process-stage-record" aria-label={`Stage ${stageNumber(index)} record`}>
                <div className="process-record-row">
                  <span className="activity-label">Receives</span>
                  <strong>{stage.input}</strong>
                </div>
                <ArrowRight size={16} className="process-record-arrow" aria-hidden="true" />
                <div className="process-record-row">
                  <span className="activity-label">Produces</span>
                  <strong>{stage.output}</strong>
                </div>
                {stage.statuses.length > 0 ? (
                  <div className="process-record-statuses">
                    <span className="activity-label">Status shown</span>
                    <ul>
                      {stage.statuses.map((status) => (
                        <li key={`${status.scope}-${status.label}`}>
                          <span className="process-status-scope">{status.scope}</span> {status.label}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="process-record-note">Not yet tracked in eProcure</p>
                )}
              </aside>
            </li>
          ))}
        </ol>
      </section>

      <div className="home-editorial-grid">
        <section className="official-bulletin" aria-labelledby="process-supplier-title">
          <div className="bulletin-head">
            <div>
              <p className="section-kicker">Before stage 05</p>
              <h2 id="process-supplier-title">Supplier registration</h2>
            </div>
            <span>COMPLIANCE</span>
          </div>
          <p className="process-bulletin-intro">
            Suppliers are matched to RFQs only after the BAC approves their registration. Verification usually takes
            3 to 5 business days. Keep these documents current:
          </p>
          <ul>
            {REQUIREMENTS.map((item) => (
              <li key={item} className="process-requirement"><FileText size={15} aria-hidden="true" /> <p>{item}</p></li>
            ))}
          </ul>
          <Link to="/supplier/register" className="hero-text-link">Register as a supplier <ChevronRight size={16} aria-hidden="true" /></Link>
        </section>

        <section className="process-cta" aria-labelledby="process-cta-title">
          <p className="hero-kicker">Ready to begin</p>
          <h2 id="process-cta-title">Start from the right workspace.</h2>
          <p>
            End Users upload Purchase Requests, the BAC Secretariat reviews them and issues RFQs, and suppliers respond
            with quotations, all from the same sign-in page.
          </p>
          <div className="hero-actions">
            <Link to="/login" className="btn-primary">Access eProcure</Link>
            <Link to="/faq" className="hero-text-link process-cta-link">Questions? Read the FAQ <ChevronRight size={16} aria-hidden="true" /></Link>
          </div>
        </section>
      </div>
    </div>
  )
}

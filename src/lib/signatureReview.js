// Who may release a required PR signature the detector did not find - the
// frontend mirror of backend/api/signature_review.py. The backend re-checks
// everything; these only drive what the review screens show and enable.

export const REQUIRED_SIGNATORY_KEYS = ['requested_by', 'funds_available', 'approved_by']

// Same bar as backend/api/signature_review.py MIN_ABSENT_NOTE_LENGTH.
export const MIN_ABSENT_NOTE_LENGTH = 10

// Older confirmation records carry no role; they are all submitter ones.
export const isSubmitterConfirmation = (entry) => (entry?.confirmed_role || 'submitter') === 'submitter'

// Required signatures the BAC must verify by hand before assigning the PR
// number: anything the detector did not find, except an "uncertain" box the
// submitter already confirmed. Mirrors signature_review.pending_for_bac.
export const bacPendingSignatureKeys = (validation, confirmations = []) => {
  if (!validation?.signatories) return []
  const submitterConfirmed = new Set(
    confirmations.filter(isSubmitterConfirmation).map((entry) => entry.key),
  )
  return REQUIRED_SIGNATORY_KEYS.filter((key) => {
    const state = validation.signatories[key]?.state || 'unverifiable'
    if (state === 'present') return false
    return !(state === 'uncertain' && submitterConfirmed.has(key))
  })
}

// Whether every pending box has the BAC's tick (and a note, for a blank box).
export const bacVerificationsComplete = (validation, confirmations, verifications) => (
  bacPendingSignatureKeys(validation, confirmations).every((key) => {
    if (!(key in verifications)) return false
    if (validation.signatories[key]?.state !== 'absent') return true
    return (verifications[key] || '').trim().length >= MIN_ABSENT_NOTE_LENGTH
  })
)

export const describeConfirmation = (item) => {
  const by = item.confirmed_by ? ` by ${item.confirmed_by}` : ''
  const override = item.detected_state === 'absent' ? ', overriding a blank box' : ''
  const note = item.note ? `: "${item.note}"` : ''
  return `${item.label}${by}${override}${note}`
}

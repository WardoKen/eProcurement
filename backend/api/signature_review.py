"""Who may let a Purchase Request past a required signature the detector did
not find, and how.

The detector (``ocr.signature_detection``) only reports what it saw in each
box: ``present``, ``absent``, ``uncertain`` or ``unverifiable``. This module
turns that into the two gates a PR passes through. Neither ever passes a box
silently.

Submission - the End User (``create_pr`` with ``review_only``)
    present       passes.
    uncertain     the submitter must confirm it against the document.
    unverifiable  passes, flagged: the detector failed, not the document, so
                  the BAC verifies the box at review.
    absent        blocked. A submitter can never override a blank box.
    no document   blocked (handled by the caller: there is nothing to check).

Numbering - the BAC / admin (``pr_update`` with ``finalize_review``)
    The document is checked again. Each required box that is not ``present``
    must be cleared before the PR number is assigned, either by
      * the submitter's confirmation, while the box is still ``uncertain``, or
      * the admin's verification sent with the numbering request. Overriding
        an ``absent`` box needs a written note.
    With no document on disk, every required box needs the admin's
    verification (against the paper original).

Every release is recorded in ``PurchaseRequest.signature_confirmations``.
"""
from django.utils import timezone

try:
    from ocr import signature_detection as sd
except ImportError:  # pragma: no cover
    from backend.ocr import signature_detection as sd

ROLE_SUBMITTER = 'submitter'
ROLE_BAC = 'bac'

# Same bar as an unposting reason (pr_posting.MIN_REASON_LENGTH).
MIN_ABSENT_NOTE_LENGTH = 10


def _states(result):
    signatories = (result or {}).get('signatories') or {}
    return {
        key: (signatories.get(key) or {}).get('state', sd.STATE_UNVERIFIABLE)
        for key in sd.REQUIRED_SIGNATORIES
    }


def _reason(result, key):
    return str((((result or {}).get('signatories') or {}).get(key) or {}).get('reason') or '')


def record(result, key, user, role, note='', at=None):
    """One audit entry for a signature released by hand."""
    return {
        'key': key,
        'label': sd.DISPLAY_NAMES.get(key, key),
        'detected_state': _states(result).get(key, sd.STATE_UNVERIFIABLE),
        'detected_reason': _reason(result, key),
        'confirmed_by': getattr(user, 'username', '') or '',
        'confirmed_role': role,
        'confirmed_at': (at or timezone.now()).isoformat(),
        'note': note,
    }


def submission_snapshot(result, at=None):
    """What the detector saw when the End User submitted, kept on the PR.

    ``bac_verification_keys`` are the boxes the BAC still has to check by hand
    (the detector could not read them), shown as a flag in the BAC's PR list.
    """
    summary = (result or {}).get('summary') or {}
    return {
        'checked_at': (at or timezone.now()).isoformat(),
        'states': _states(result),
        'bac_verification_keys': list(summary.get('unverifiable_keys') or []),
    }


def check_submission(result, confirmed_keys):
    """Gate 1. Returns ``(error_payload, confirmed_uncertain_keys)``.

    ``error_payload`` is ``None`` when the End User may submit.
    """
    summary = (result or {}).get('summary') or {}
    if summary.get('can_save'):
        return None, []
    missing = list(summary.get('missing_signatures') or [])
    uncertain_keys = list(summary.get('uncertain_keys') or [])
    unconfirmed = [key for key in uncertain_keys if key not in set(confirmed_keys or ())]
    if not missing and not unconfirmed:
        # Anything left is unverifiable: allowed through, flagged for the BAC.
        return None, uncertain_keys
    if missing:
        error = (
            'Purchase Request cannot be saved because one or more required signatures are missing. '
            'Have the document signed and upload it again. If it is signed, contact the BAC '
            'Secretariat: only the BAC can override a signature that appears blank.'
        )
    else:
        error = (
            'Please confirm the signatures marked "Please confirm" against the original document '
            'before submitting.'
        )
    return {
        'success': False,
        'error': error,
        'missing_signatures': missing,
        'uncertain_signatures': list(summary.get('uncertain_signatures') or []),
        'unverifiable_signatures': list(summary.get('unverifiable_signatures') or []),
        'signature_validation': result,
    }, []


def parse_verifications(raw):
    """``[{"key", "note"}]`` or ``["key", ...]`` from the request -> {key: note}."""
    verifications = {}
    if not isinstance(raw, (list, tuple)):
        return verifications
    for entry in raw:
        if isinstance(entry, dict):
            key, note = str(entry.get('key') or ''), str(entry.get('note') or '').strip()
        else:
            key, note = str(entry or ''), ''
        if key in sd.REQUIRED_SIGNATORIES:
            verifications[key] = note
    return verifications


def _submitter_confirmed(existing_records):
    return {
        str(entry.get('key'))
        for entry in existing_records or []
        if isinstance(entry, dict) and entry.get('confirmed_role', ROLE_SUBMITTER) == ROLE_SUBMITTER
    }


def pending_for_bac(result, existing_records):
    """Required boxes the admin must verify before numbering, in form order."""
    confirmed = _submitter_confirmed(existing_records)
    pending = []
    for key, state in _states(result).items():
        if state == sd.STATE_PRESENT:
            continue
        if state == sd.STATE_UNCERTAIN and key in confirmed:
            continue
        pending.append(key)
    return pending


def check_finalize(result, existing_records, verifications):
    """Gate 2. Returns ``(error_payload, keys_released_by_the_admin)``.

    ``error_payload`` is ``None`` when the PR may be numbered.
    """
    states = _states(result)
    pending = pending_for_bac(result, existing_records)
    unverified = [key for key in pending if key not in verifications]
    notes_needed = [
        key for key in pending
        if key in verifications and states[key] == sd.STATE_ABSENT
        and len(verifications[key]) < MIN_ABSENT_NOTE_LENGTH
    ]
    if not unverified and not notes_needed:
        return None, pending
    if unverified:
        labels = ', '.join(sd.DISPLAY_NAMES[key] for key in unverified)
        message = (
            f'Verify these signatures against the original document before assigning the PR number: {labels}.'
        )
    else:
        labels = ', '.join(sd.DISPLAY_NAMES[key] for key in notes_needed)
        message = (
            f'Add a note (at least {MIN_ABSENT_NOTE_LENGTH} characters) explaining why you are overriding '
            f'the blank signature box: {labels}.'
        )
    return {
        'success': False,
        'signature_verification_required': True,
        'message': message,
        'signatures_to_verify': [
            {'key': key, 'label': sd.DISPLAY_NAMES[key], 'state': states[key]} for key in pending
        ],
        'unverified_signatures': unverified,
        'notes_required': notes_needed,
        'signature_validation': result,
    }, []

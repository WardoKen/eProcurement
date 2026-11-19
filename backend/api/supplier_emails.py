"""Emails about a supplier's profile changes and their BAC review.

* ``send_changes_submitted`` - to the supplier, when their own change (a
  category change or a document resubmission) sent the account to Pending
  Review: what was submitted, and that opportunities pause until approval.
* ``notify_bac_of_changes`` - to every active BAC admin account with an email
  address, so the review is not missed.
* ``send_changes_approved`` - to the supplier, when the BAC approves an
  account that had been approved before and went back to review because of
  the supplier's changes (a first-time approval keeps the registration email).

Each returns whether a message was handed to the mail server. A failure is
logged and never blocks the save or decision that triggered it. Callers send
after their database transaction commits.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage

from .models import SupplierChangeLog, User
from .supplier_changes import describe
from .supplier_registration import REQUIRED_DOCUMENTS

logger = logging.getLogger(__name__)

FOOTER = 'This is an automated notification from eProcure. Please do not reply to this email.'


def _document_label(key):
    return REQUIRED_DOCUMENTS.get(key) or key.replace('_', ' ').title()


def _change_lines(rows):
    lines = [f'  - {describe(row, _document_label)}' for row in rows if row.event_type != SupplierChangeLog.EVENT_STATUS]
    return lines or ['  - (no details recorded)']


def _send(subject, lines, recipients, log_context):
    recipients = [address for address in recipients if address and '@' in address]
    if not recipients:
        return False
    email = EmailMessage(
        subject=subject, body='\n'.join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL, to=recipients,
    )
    try:
        return email.send(fail_silently=False) > 0
    except Exception:
        logger.exception('Failed to send %s email', log_context)
        return False


def _greeting(supplier):
    return f'Good day, {supplier.contact_person or supplier.company_name}.'


def send_changes_submitted(supplier, rows):
    return _send(
        'Your eProcure profile changes were submitted for BAC review',
        [
            _greeting(supplier),
            '',
            f'We received the following changes to the supplier profile of {supplier.company_name}:',
            *_change_lines(rows),
            '',
            'The BAC Secretariat will review them. Until it does, your account is Pending Review: you will not '
            'see new procurement opportunities. RFQs you have already received are not affected.',
            '',
            "You will receive another email once the BAC Secretariat has reviewed your changes.",
            '',
            f'Company Profile: {settings.FRONTEND_ORIGIN}/supplier',
            '',
            FOOTER,
        ],
        [(supplier.email or '').strip()],
        f'changes-submitted (supplier {supplier.id})',
    )


def bac_recipients():
    return list(
        User.objects.filter(role__name='admin', is_active=True)
        .exclude(email='').values_list('email', flat=True)
    )


def notify_bac_of_changes(supplier, rows):
    return _send(
        f'Supplier review needed: {supplier.company_name} changed their profile',
        [
            'Good day, BAC Secretariat.',
            '',
            f'{supplier.company_name} changed their supplier profile, which sent the account back to Pending Review:',
            *_change_lines(rows),
            '',
            'Review the changes in Supplier Management. The Change Log in the supplier review lists every change.',
            '',
            f'Supplier Management: {settings.FRONTEND_ORIGIN}/admin',
            '',
            FOOTER,
        ],
        bac_recipients(),
        f'BAC change alert (supplier {supplier.id})',
    )


def send_changes_approved(supplier, rows):
    return _send(
        'Your eProcure profile changes have been approved',
        [
            _greeting(supplier),
            '',
            f'The BAC Secretariat has reviewed and approved the following changes to the supplier profile of '
            f'{supplier.company_name}:',
            *_change_lines(rows),
            '',
            'Your account is Approved again. You will now receive procurement opportunities and RFQs matched to '
            'your current categories.',
            '',
            f'Sign in here: {settings.FRONTEND_ORIGIN}/login',
            '',
            FOOTER,
        ],
        [(supplier.email or '').strip()],
        f'changes-approved (supplier {supplier.id})',
    )

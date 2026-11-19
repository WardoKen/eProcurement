"""Emails about supplier profile changes and their BAC review.

* A supplier change that sends the account to Pending Review (category
  change, document resubmission) emails the supplier a confirmation listing
  the changes, and alerts every active BAC admin with an email address.
* Saves that do not trigger a review send nothing.
* When the BAC approves a previously approved supplier whose changes sent it
  back to review, the supplier gets a "changes approved" email listing them -
  not the first-time registration email.
* A failing mail server never blocks the save or the decision.
"""

import json
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from api.models import Category, Role, User
from api.tests.test_authorization import _login_as
from api.tests.test_category_grouped_matching import make_eligible_supplier

_PDF_BYTES = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SupplierChangeEmailTests(TestCase):
    def setUp(self):
        self.office = Category.objects.get_or_create(name='Office Supplies')[0]
        self.janitorial = Category.objects.get_or_create(name='Janitorial Supplies')[0]
        self.supplier = make_eligible_supplier('Acme Supplies', self.office)
        admin_role = Role.objects.get_or_create(name='admin')[0]
        self.admin = User.objects.create(username='bac', password_hash='x', role=admin_role, email='bac@ctu.edu.ph', is_active=True)
        # Not alerted: inactive, or no email address.
        User.objects.create(username='old-bac', password_hash='x', role=admin_role, email='old@ctu.edu.ph', is_active=False)
        User.objects.create(username='bac2', password_hash='x', role=admin_role, email='', is_active=True)

    def _as_supplier(self):
        _login_as(self.client, 'supplier', supplier=self.supplier)

    def _change_categories(self):
        self._as_supplier()
        return self.client.patch(
            f'/api/suppliers/{self.supplier.id}/profile/',
            data=json.dumps({'contact_person': 'New Rep', 'category_ids': [self.office.id, self.janitorial.id]}),
            content_type='application/json',
        )

    def _decide(self, status, remarks=''):
        _login_as(self.client, 'admin', user=self.admin)
        return self.client.patch(
            f'/api/suppliers/{self.supplier.id}/status/',
            data=json.dumps({'status': status, 'remarks': remarks}), content_type='application/json',
        )

    def _mail_to(self, address):
        return [message for message in mail.outbox if address in message.to]

    def test_change_sent_for_review_emails_supplier_and_bac(self):
        response = self._change_categories()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['review_email_sent'])
        [to_supplier] = self._mail_to('acme@example.com')
        self.assertIn('submitted for BAC review', to_supplier.subject)
        self.assertIn('Contact Person: Rep -> New Rep', to_supplier.body)
        self.assertIn('Categories: Added: Janitorial Supplies', to_supplier.body)
        self.assertIn('Pending Review', to_supplier.body)

        [to_bac] = self._mail_to('bac@ctu.edu.ph')
        self.assertEqual(to_bac.to, ['bac@ctu.edu.ph'])  # inactive / no-email admins left out
        self.assertIn('Acme Supplies', to_bac.subject)
        self.assertIn('Categories: Added: Janitorial Supplies', to_bac.body)

    def test_save_that_does_not_trigger_review_sends_nothing(self):
        self._as_supplier()
        response = self.client.patch(
            f'/api/suppliers/{self.supplier.id}/profile/',
            data=json.dumps({'contact_person': 'New Rep'}), content_type='application/json',
        )
        self.assertIsNone(response.json()['review_email_sent'])
        self.assertEqual(mail.outbox, [])

    def test_document_resubmission_emails_supplier_and_bac(self):
        self._decide('For Compliance', 'Upload a current permit.')
        mail.outbox.clear()
        self._as_supplier()
        response = self.client.post(
            f'/api/suppliers/{self.supplier.id}/documents/resubmit/',
            data={'doc_type': 'mayor_permit', 'file': SimpleUploadedFile('permit-2026.pdf', _PDF_BYTES, content_type='application/pdf')},
        )

        self.assertTrue(response.json()['review_email_sent'])
        [to_supplier] = self._mail_to('acme@example.com')
        self.assertIn("Document resubmitted: Mayor's Permit (permit-2026.pdf)", to_supplier.body)
        self.assertEqual(len(self._mail_to('bac@ctu.edu.ph')), 1)

    def test_bac_approving_the_changes_sends_changes_approved_email(self):
        self._change_categories()
        mail.outbox.clear()

        response = self._decide('Approved')

        self.assertTrue(response.json()['approval_email_sent'])
        [message] = mail.outbox
        self.assertEqual(message.to, ['acme@example.com'])
        self.assertIn('profile changes have been approved', message.subject)
        self.assertIn('Contact Person: Rep -> New Rep', message.body)
        self.assertIn('Categories: Added: Janitorial Supplies', message.body)
        self.assertNotIn('registration has been approved', message.subject)

    def test_reapproval_after_compliance_round_still_lists_changes(self):
        # Approved -> own changes -> BAC asks for compliance -> resubmits -> approved.
        self._change_categories()
        self._decide('For Compliance', 'Upload a current permit.')
        self._as_supplier()
        self.client.post(
            f'/api/suppliers/{self.supplier.id}/documents/resubmit/',
            data={'doc_type': 'mayor_permit', 'file': SimpleUploadedFile('permit-2026.pdf', _PDF_BYTES, content_type='application/pdf')},
        )
        mail.outbox.clear()

        self._decide('Approved')

        [message] = mail.outbox
        self.assertIn('profile changes have been approved', message.subject)
        self.assertIn("Mayor's Permit", message.body)

    def test_first_time_approval_keeps_the_registration_email(self):
        self.supplier.status = 'Pending Review'
        self.supplier.save(update_fields=['status'])

        self._decide('Approved')

        [message] = mail.outbox
        self.assertIn('registration has been approved', message.subject)

    def test_mail_failure_never_blocks_the_save_or_the_decision(self):
        with patch('django.core.mail.EmailMessage.send', side_effect=OSError('SMTP down')):
            response = self._change_categories()
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()['review_email_sent'])
            self.assertEqual(response.json()['supplier']['status'], 'Pending Review')

            decision = self._decide('Approved')
            self.assertEqual(decision.status_code, 200)
            self.assertFalse(decision.json()['approval_email_sent'])
            self.assertEqual(decision.json()['status'], 'Approved')

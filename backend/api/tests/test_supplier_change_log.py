"""Supplier change log for BAC review.

Every supplier profile edit, category change and document resubmission is
logged (old -> new, by whom, when), along with each status change - the
automatic return to Pending Review and the BAC's own decisions. Only the BAC
receives the log, and the log is append-only.
"""

import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from api.models import Category, Role, Supplier, SupplierChangeLog, User
from api.tests.test_authorization import _login_as
from api.tests.test_category_grouped_matching import make_eligible_supplier

_PDF_BYTES = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


class SupplierChangeLogTests(TestCase):
    def setUp(self):
        self.office = Category.objects.get_or_create(name='Office Supplies')[0]
        self.janitorial = Category.objects.get_or_create(name='Janitorial Supplies')[0]
        self.supplier = make_eligible_supplier('Acme Supplies', self.office)
        supplier_role = Role.objects.get_or_create(name='supplier')[0]
        self.supplier_user = User.objects.create(username='acme', password_hash='x', role=supplier_role)
        admin_role = Role.objects.get_or_create(name='admin')[0]
        self.admin_user = User.objects.create(username='bac', password_hash='x', role=admin_role)

    def _as_supplier(self):
        _login_as(self.client, 'supplier', user=self.supplier_user, supplier=self.supplier)

    def _as_admin(self):
        _login_as(self.client, 'admin', user=self.admin_user)

    def _patch(self, **data):
        return self.client.patch(
            f'/api/suppliers/{self.supplier.id}/profile/',
            data=json.dumps(data), content_type='application/json',
        )

    def _log(self):
        self._as_admin()
        return self.client.get(f'/api/suppliers/{self.supplier.id}/profile/').json()['change_log']

    def test_profile_edit_logs_each_changed_field_only(self):
        self._as_supplier()
        # contact_person and email change; the unchanged address is not logged.
        self._patch(contact_person='New Rep', email='new@acme.ph', business_address=self.supplier.business_address)

        log = self._log()
        self.assertEqual({(row['field_name'], row['old_value'], row['new_value']) for row in log}, {
            ('contact_person', 'Rep', 'New Rep'),
            ('email', 'acme@example.com', 'new@acme.ph'),
        })
        row = log[0]
        self.assertEqual(row['changed_by'], 'acme')
        self.assertEqual(row['changed_by_role'], 'supplier')
        self.assertEqual({r['changed_at'] for r in log}, {row['changed_at']})  # one change set

    def test_category_change_logs_categories_and_the_return_to_review(self):
        self._as_supplier()
        self._patch(category_ids=[self.janitorial.id])

        log = {row['event_type']: row for row in self._log()}
        categories = log[SupplierChangeLog.EVENT_CATEGORIES]
        self.assertEqual(categories['field_label'], 'Categories')
        self.assertEqual(categories['old_value'], 'Office Supplies')
        self.assertEqual(categories['new_value'], 'Janitorial Supplies')
        self.assertEqual(categories['note'], 'Added: Janitorial Supplies; Removed: Office Supplies')
        status = log[SupplierChangeLog.EVENT_STATUS]
        self.assertEqual((status['old_value'], status['new_value']), ('Approved', 'Pending Review'))
        self.assertIn('Category change', status['note'])

    def test_document_resubmission_is_logged(self):
        self.supplier.status = 'For Compliance'
        self.supplier.save(update_fields=['status'])
        self._as_supplier()
        response = self.client.post(
            f'/api/suppliers/{self.supplier.id}/documents/resubmit/',
            data={'doc_type': 'mayor_permit', 'file': SimpleUploadedFile('new-permit.pdf', _PDF_BYTES, content_type='application/pdf')},
        )
        self.assertEqual(response.status_code, 200)

        log = {row['event_type']: row for row in self._log()}
        document = log[SupplierChangeLog.EVENT_DOCUMENT]
        self.assertEqual(document['field_name'], 'mayor_permit')
        self.assertEqual(document['old_value'], 'mayor_permit.pdf')
        self.assertEqual(document['new_value'], 'new-permit.pdf')
        self.assertEqual(
            (log[SupplierChangeLog.EVENT_STATUS]['old_value'], log[SupplierChangeLog.EVENT_STATUS]['new_value']),
            ('For Compliance', 'Pending Review'),
        )

    def test_bac_decision_is_logged_with_remarks(self):
        self._as_admin()
        self.client.patch(
            f'/api/suppliers/{self.supplier.id}/status/',
            data=json.dumps({'status': 'For Compliance', 'remarks': 'Upload a current permit.'}),
            content_type='application/json',
        )
        row = self._log()[0]
        self.assertEqual(row['event_type'], SupplierChangeLog.EVENT_STATUS)
        self.assertEqual((row['old_value'], row['new_value']), ('Approved', 'For Compliance'))
        self.assertEqual(row['note'], 'Upload a current permit.')
        self.assertEqual((row['changed_by'], row['changed_by_role']), ('bac', 'admin'))

    def test_saving_without_changes_logs_nothing(self):
        self._as_supplier()
        self._patch(contact_person='Rep', category_ids=[self.office.id])
        self.assertEqual(self._log(), [])

    def test_rejected_locked_field_change_logs_nothing(self):
        self._as_supplier()
        self.assertEqual(self._patch(company_name='Other Inc.', contact_person='New Rep').status_code, 400)
        self.assertEqual(self._log(), [])

    def test_supplier_does_not_receive_the_log(self):
        self._as_supplier()
        self._patch(contact_person='New Rep')
        profile = self.client.get(f'/api/suppliers/{self.supplier.id}/profile/').json()
        self.assertNotIn('change_log', profile)

    def test_log_is_append_only_but_goes_with_a_deleted_supplier(self):
        self._as_supplier()
        self._patch(contact_person='New Rep')
        row = SupplierChangeLog.objects.get()
        row.note = 'tampered'
        with self.assertRaises(PermissionError):
            row.save()
        with self.assertRaises(PermissionError):
            row.delete()
        with self.assertRaises(PermissionError):
            SupplierChangeLog.objects.all().delete()

        Supplier.objects.filter(id=self.supplier.id).delete()
        self.assertFalse(SupplierChangeLog.objects.exists())

"""Supplier profile edits after BAC approval.

* Company name, TIN and business type are locked once the supplier is
  Approved; resending the unchanged values (the form posts the whole profile)
  is still allowed.
* A category change by an Approved supplier sends the account back to the
  BAC: status becomes Pending Review, as a document resubmission does.
"""

import json

from django.test import TestCase

from api.models import Category, SupplierCategory
from api.tests.test_authorization import _login_as
from api.tests.test_category_grouped_matching import make_eligible_supplier


class SupplierProfileLockTests(TestCase):
    def setUp(self):
        self.office = Category.objects.get_or_create(name='Office Supplies')[0]
        self.janitorial = Category.objects.get_or_create(name='Janitorial Supplies')[0]
        self.supplier = make_eligible_supplier('Acme Supplies', self.office)
        self.supplier.tin = '123-456-789-000'
        self.supplier.save(update_fields=['tin'])
        _login_as(self.client, 'supplier', supplier=self.supplier)

    def _patch(self, **data):
        return self.client.patch(
            f'/api/suppliers/{self.supplier.id}/profile/',
            data=json.dumps(data), content_type='application/json',
        )

    def _set_status(self, status):
        self.supplier.status = status
        self.supplier.save(update_fields=['status'])

    def test_approved_supplier_cannot_change_locked_fields(self):
        for field, value in (('company_name', 'Other Name Inc.'), ('tin', '999-999-999-000'), ('business_type', 'Corporation')):
            with self.subTest(field=field):
                response = self._patch(**{field: value})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['locked_fields'], [field])
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.company_name, 'Acme Supplies')
        self.assertEqual(self.supplier.tin, '123-456-789-000')
        self.assertEqual(self.supplier.business_type, 'Others')

    def test_a_rejected_lock_saves_nothing_else(self):
        response = self._patch(company_name='Other Name Inc.', contact_person='New Rep')
        self.assertEqual(response.status_code, 400)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.contact_person, 'Rep')

    def test_approved_supplier_may_resend_unchanged_locked_values(self):
        # TIN punctuation and surrounding whitespace are not a change.
        response = self._patch(
            company_name=' Acme Supplies ', tin='123456789000', business_type='Others',
            contact_person='New Rep',
        )
        self.assertEqual(response.status_code, 200)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.contact_person, 'New Rep')
        self.assertEqual(self.supplier.status, 'Approved')

    def test_supplier_not_yet_approved_can_still_fix_identity_fields(self):
        self._set_status('Pending Review')
        response = self._patch(company_name='Acme Supplies, Inc.', tin='111-222-333-000')
        self.assertEqual(response.status_code, 200)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.company_name, 'Acme Supplies, Inc.')

    def test_approved_category_change_goes_back_to_pending_review(self):
        response = self._patch(category_ids=[self.office.id, self.janitorial.id])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['supplier']['status'], 'Pending Review')
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.status, 'Pending Review')
        self.assertEqual(
            set(SupplierCategory.objects.filter(supplier=self.supplier).values_list('category_id', flat=True)),
            {self.office.id, self.janitorial.id},
        )
        # Pending Review suppliers get no opportunities until the BAC approves.
        opportunities = self.client.get(f'/api/suppliers/{self.supplier.id}/opportunities/').json()
        self.assertEqual(opportunities['opportunities'], [])

    def test_resending_the_same_categories_keeps_approval(self):
        response = self._patch(category_ids=[self.office.id], contact_person='New Rep')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['supplier']['status'], 'Approved')

    def test_category_change_before_approval_does_not_change_status(self):
        self._set_status('For Compliance')
        response = self._patch(category_ids=[self.janitorial.id])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['supplier']['status'], 'For Compliance')


class SupplierEndpointsAcceptBrowserRequestsTests(TestCase):
    """The frontend sends no CSRF token (every mutating endpoint is
    csrf_exempt). Django's test client skips CSRF checks by default, which hid
    that these three were missing the exemption: in a browser they returned
    an HTML 403 and the profile showed "Failed to update profile"."""

    def setUp(self):
        from django.test import Client
        self.supplier = make_eligible_supplier('Acme Supplies', Category.objects.get_or_create(name='Office Supplies')[0])
        self.browser = Client(enforce_csrf_checks=True)
        _login_as(self.browser, 'supplier', supplier=self.supplier)

    def test_profile_save(self):
        response = self.browser.patch(
            f'/api/suppliers/{self.supplier.id}/profile/',
            data=json.dumps({'contact_person': 'New Rep'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_document_resubmission_reaches_the_view(self):
        # No file: the view's own 400, not Django's CSRF 403.
        response = self.browser.post(f'/api/suppliers/{self.supplier.id}/documents/resubmit/', data={'doc_type': 'mayor_permit'})
        self.assertEqual(response.status_code, 400)

    def test_mark_notification_read_reaches_the_view(self):
        # Unknown notification: the view's own 404, not Django's CSRF 403.
        response = self.browser.post('/api/notifications/999999/read/')
        self.assertEqual(response.status_code, 404)

"""Coverage for the session-based auth added in backend/api/auth.py.

These tests exercise the ``require_auth`` decorator itself (via a handful of
representative endpoints) rather than re-testing every endpoint's business
logic - that's covered in test_supplier_registration.py. The four cases the
decorator is responsible for are: no session -> 401, wrong role -> 403,
wrong supplier (ownership) -> 403, correct role/owner -> success.
"""
import json

from django.test import TestCase

from api.models import Category, PurchaseRequest, PurchaseRequestItem, Quotation, Role, Supplier, User


def _login_as(client, role_name, *, user=None, supplier=None):
    """Authenticate ``client``'s session as a user with the given role.

    Mirrors what ``login_view`` stores in the session (user_id/role/username,
    plus supplier_id for supplier accounts) without a real password round
    trip in every test.
    """
    if user is None:
        role = Role.objects.get_or_create(name=role_name)[0]
        user = User.objects.create(
            username=f'test-{role_name}-{User.objects.count()}',
            password_hash='x',
            role=role,
            is_active=True,
        )
    session = client.session
    session['user_id'] = user.id
    session['role'] = role_name
    session['username'] = user.username
    if supplier is not None:
        session['supplier_id'] = supplier.id
    session.save()
    return user


class AdminEndpointAuthTests(TestCase):
    """admin_dashboard_summary as a representative admin-only endpoint."""

    def test_unauthenticated_request_is_rejected_with_401(self):
        response = self.client.get('/api/admin/dashboard-summary/')
        self.assertEqual(response.status_code, 401)

    def test_wrong_role_is_rejected_with_403(self):
        _login_as(self.client, 'buyer')
        response = self.client.get('/api/admin/dashboard-summary/')
        self.assertEqual(response.status_code, 403)

    def test_supplier_role_is_also_rejected_with_403(self):
        _login_as(self.client, 'supplier')
        response = self.client.get('/api/admin/dashboard-summary/')
        self.assertEqual(response.status_code, 403)

    def test_admin_request_succeeds(self):
        _login_as(self.client, 'admin')
        response = self.client.get('/api/admin/dashboard-summary/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('total_suppliers', payload)
        for key in (
            'supplier_status_breakdown', 'supplier_category_breakdown',
            'document_status_breakdown', 'pr_status_breakdown',
            'pr_monthly_volume', 'rfq_stats',
        ):
            self.assertIn(key, payload)
        self.assertEqual(len(payload['pr_monthly_volume']), 6)
        self.assertIn('total_sent', payload['rfq_stats'])

    def test_session_for_a_deleted_or_deactivated_user_is_rejected(self):
        role = Role.objects.get_or_create(name='admin')[0]
        user = User.objects.create(username='ghost-admin', password_hash='x', role=role, is_active=True)
        _login_as(self.client, 'admin', user=user)
        user.is_active = False
        user.save(update_fields=['is_active'])

        response = self.client.get('/api/admin/dashboard-summary/')
        self.assertEqual(response.status_code, 401)


class AdminExportEndpointAuthTests(TestCase):
    """admin_export_suppliers / admin_export_purchase_requests: admin-only CSV streams."""

    def setUp(self):
        self.category = Category.objects.create(name='Office Supplies')
        self.supplier = Supplier.objects.create(
            company_name='Acme Corp', email='acme@example.com', status='Approved',
        )
        from api.models import SupplierCategory
        SupplierCategory.objects.create(supplier=self.supplier, category=self.category)
        self.pr = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-09-010', status='matched')

    def test_unauthenticated_export_requests_are_rejected(self):
        self.assertEqual(self.client.get('/api/admin/export/suppliers/').status_code, 401)
        self.assertEqual(self.client.get('/api/admin/export/purchase-requests/').status_code, 401)

    def test_non_admin_export_requests_are_rejected_with_403(self):
        _login_as(self.client, 'buyer')
        self.assertEqual(self.client.get('/api/admin/export/suppliers/').status_code, 403)
        self.assertEqual(self.client.get('/api/admin/export/purchase-requests/').status_code, 403)

    def test_admin_can_export_suppliers_csv(self):
        _login_as(self.client, 'admin')
        response = self.client.get('/api/admin/export/suppliers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = b''.join(response.streaming_content).decode()
        self.assertIn('Acme Corp', body)
        self.assertIn('Office Supplies', body)

    def test_admin_can_filter_suppliers_export_by_status(self):
        Supplier.objects.create(company_name='Pending Co', email='pending@example.com', status='Pending Review')
        _login_as(self.client, 'admin')
        response = self.client.get('/api/admin/export/suppliers/?status=Approved')
        body = b''.join(response.streaming_content).decode()
        self.assertIn('Acme Corp', body)
        self.assertNotIn('Pending Co', body)

    def test_admin_can_export_purchase_requests_csv(self):
        _login_as(self.client, 'admin')
        response = self.client.get('/api/admin/export/purchase-requests/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = b''.join(response.streaming_content).decode()
        self.assertIn('2026-09-010', body)

    def test_admin_can_filter_purchase_requests_export_by_status(self):
        PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-09-011', status='rejected')
        _login_as(self.client, 'admin')
        response = self.client.get('/api/admin/export/purchase-requests/?status=matched')
        body = b''.join(response.streaming_content).decode()
        self.assertIn('2026-09-010', body)
        self.assertNotIn('2026-09-011', body)


def _csv_body(response):
    return b''.join(response.streaming_content).decode()


class AdminExportFilterTests(TestCase):
    """The table filters (search, date range, Pending Review) carried into the exports."""

    def setUp(self):
        _login_as(self.client, 'admin')

    def _set_created(self, model, obj, iso):
        from django.utils.dateparse import parse_datetime
        model.objects.filter(pk=obj.pk).update(created_at=parse_datetime(iso))

    def test_supplier_export_search_matches_the_table_fields(self):
        Supplier.objects.create(company_name='Acme Corp', email='a@example.com', contact_person='Jo Reyes', status='Approved')
        Supplier.objects.create(company_name='Beta Trading', email='b@example.com', status='Approved')
        body = _csv_body(self.client.get('/api/admin/export/suppliers/?search=reyes'))
        self.assertIn('Acme Corp', body)
        self.assertNotIn('Beta Trading', body)

    def test_pending_review_filter_includes_a_blank_status_like_the_table(self):
        Supplier.objects.create(company_name='Blank Co', email='blank@example.com', status='')
        Supplier.objects.create(company_name='Approved Co', email='ok@example.com', status='Approved')
        body = _csv_body(self.client.get('/api/admin/export/suppliers/?status=Pending%20Review'))
        self.assertIn('Blank Co', body)
        self.assertNotIn('Approved Co', body)

    def test_pr_export_search(self):
        PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-09-010', office_section='ICT Office')
        PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-09-011', office_section='Registrar')
        body = _csv_body(self.client.get('/api/admin/export/purchase-requests/?search=ict'))
        self.assertIn('2026-09-010', body)
        self.assertNotIn('2026-09-011', body)

    def test_date_range_uses_the_viewers_timezone(self):
        # 23:30 UTC on Nov 1 is 07:30 on Nov 2 in Manila.
        early = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-11-001')
        self._set_created(PurchaseRequest, early, '2026-11-01T23:30:00+00:00')
        other = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-11-002')
        self._set_created(PurchaseRequest, other, '2026-11-01T10:00:00+00:00')

        body = _csv_body(self.client.get(
            '/api/admin/export/purchase-requests/?date_from=2026-11-02&date_to=2026-11-02&tz=Asia/Manila'
        ))
        self.assertIn('2026-11-001', body)
        self.assertNotIn('2026-11-002', body)
        # The timestamp is written in the same zone.
        self.assertIn('2026-11-02 07:30', body)

    def test_unknown_timezone_and_impossible_dates_are_ignored(self):
        PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-11-003')
        response = self.client.get(
            '/api/admin/export/purchase-requests/?date_from=2026-02-30&tz=Not/AZone'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('2026-11-003', _csv_body(response))

    def test_text_that_looks_like_a_formula_is_neutralised(self):
        Supplier.objects.create(company_name='=HYPERLINK("http://x")', email='f@example.com', status='Approved')
        body = _csv_body(self.client.get('/api/admin/export/suppliers/'))
        self.assertIn('\'=HYPERLINK', body)
        self.assertNotIn(',=HYPERLINK', body)


class AdminRfqExportTests(TestCase):
    """admin_export_rfqs: one CSV row per issued RFQ, filtered like RFQ Management."""

    def setUp(self):
        from django.utils import timezone
        from api.models import RFQ

        self.RFQ = RFQ
        self.category = Category.objects.create(name='IT Equipment')
        self.pr = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-11-005', office_section='ICT Office')
        self.acme = Supplier.objects.create(company_name='Acme Corp', email='acme@example.com', status='Approved')
        self.beta = Supplier.objects.create(company_name='Beta Trading', email='beta@example.com', status='Approved')
        now = timezone.now()
        self.answered = RFQ.objects.create(
            rfq_no='RFQ-2026-11-005:01', purchase_request=self.pr, category=self.category,
            supplier=self.acme, subject='RFQ', message='m', mode_of_procurement='Small Value Procurement',
            abc='50,000.00', status=RFQ.STATUS_QUOTATION_RECEIVED, sent_at=now, submitted_at=now,
            submitted_pdf='uploads/acme.pdf',
        )
        Quotation.objects.create(
            supplier=self.acme, purchase_request=self.pr, rfq=self.answered, quoted_amount='48250.00',
            estimated_delivery_days=7, warranty_months=12, status=Quotation.STATUS_SUBMITTED,
        )
        self.awaiting = RFQ.objects.create(
            rfq_no='RFQ-2026-11-005:02', purchase_request=self.pr, category=self.category,
            supplier=self.beta, subject='RFQ', message='m', status=RFQ.STATUS_SENT, sent_at=now,
        )
        RFQ.objects.create(purchase_request=self.pr, supplier=self.beta, subject='Draft', message='m')

    def _rows(self, query=''):
        import csv
        response = self.client.get(f'/api/admin/export/rfqs/{query}')
        self.assertEqual(response.status_code, 200)
        return list(csv.reader(_csv_body(response).splitlines()))

    def test_requires_admin(self):
        self.assertEqual(self.client.get('/api/admin/export/rfqs/').status_code, 401)
        _login_as(self.client, 'buyer')
        self.assertEqual(self.client.get('/api/admin/export/rfqs/').status_code, 403)

    def test_one_row_per_issued_rfq_with_its_quotation(self):
        _login_as(self.client, 'admin')
        header, *rows = self._rows()
        self.assertEqual(len(rows), 2)  # the draft is left out
        answered = dict(zip(header, rows[0]))
        self.assertEqual(answered['RFQ No.'], 'RFQ-2026-11-005:01')
        self.assertEqual(answered['PR No.'], '2026-11-005')
        self.assertEqual(answered['Category'], 'IT Equipment')
        self.assertEqual(answered['Supplier'], 'Acme Corp')
        self.assertEqual(answered['ABC'], '50,000.00')
        self.assertEqual(answered['Response Document'], 'Yes')
        self.assertEqual(answered['Quoted Amount'], '48250.00')
        self.assertEqual(answered['Delivery (Days)'], '7')
        self.assertEqual(answered['Quotation Status'], 'Submitted')
        awaiting = dict(zip(header, rows[1]))
        self.assertEqual(awaiting['Status'], 'Awaiting Supplier Response')
        self.assertEqual(awaiting['Quoted Amount'], '')

    def test_draft_quotations_are_not_reported(self):
        Quotation.objects.create(
            supplier=self.beta, purchase_request=self.pr, rfq=self.awaiting, quoted_amount='1.00',
            status=Quotation.STATUS_DRAFT,
        )
        _login_as(self.client, 'admin')
        header, *rows = self._rows('?status=awaiting')
        self.assertEqual(len(rows), 1)
        self.assertEqual(dict(zip(header, rows[0]))['Quoted Amount'], '')

    def test_filters_match_rfq_management(self):
        _login_as(self.client, 'admin')
        _, *received = self._rows('?status=received')
        self.assertEqual([row[0] for row in received], ['RFQ-2026-11-005:01'])
        _, *searched = self._rows('?search=beta')
        self.assertEqual([row[0] for row in searched], ['RFQ-2026-11-005:02'])

    def test_date_range_is_on_the_sent_date(self):
        from django.utils.dateparse import parse_datetime
        self.RFQ.objects.filter(pk=self.awaiting.pk).update(sent_at=parse_datetime('2026-10-15T02:00:00+00:00'))
        _login_as(self.client, 'admin')
        _, *rows = self._rows('?date_from=2026-10-01&date_to=2026-10-31&tz=Asia/Manila')
        self.assertEqual([row[0] for row in rows], ['RFQ-2026-11-005:02'])

    def test_pr_id_limits_the_export_to_one_purchase_request(self):
        other_pr = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-11-0050')
        self.RFQ.objects.create(
            rfq_no='RFQ-2026-11-0050:01', purchase_request=other_pr, supplier=self.acme,
            subject='RFQ', message='m', status=self.RFQ.STATUS_SENT,
        )
        _login_as(self.client, 'admin')
        _, *rows = self._rows(f'?pr_id={self.pr.id}')
        self.assertEqual([row[0] for row in rows], ['RFQ-2026-11-005:01', 'RFQ-2026-11-005:02'])
        _, *none = self._rows('?pr_id=abc')
        self.assertEqual(none, [])

    def test_rfq_management_list_takes_the_same_date_range(self):
        from django.utils.dateparse import parse_datetime
        self.RFQ.objects.filter(pk=self.awaiting.pk).update(sent_at=parse_datetime('2026-10-15T02:00:00+00:00'))
        _login_as(self.client, 'admin')
        payload = self.client.get('/api/rfqs/responses/?date_from=2026-10-01&date_to=2026-10-31').json()
        self.assertEqual([r['rfq_no'] for r in payload['rfqs']], ['RFQ-2026-11-005:02'])


class AdminPrNumberFormatEndpointAuthTests(TestCase):
    """admin_pr_number_format (GET/PATCH): admin-only PR numbering settings."""

    def test_unauthenticated_requests_are_rejected_with_401(self):
        self.assertEqual(self.client.get('/api/admin/pr-number-format/').status_code, 401)
        self.assertEqual(self.client.patch('/api/admin/pr-number-format/', data='{}', content_type='application/json').status_code, 401)

    def test_non_admin_requests_are_rejected_with_403(self):
        _login_as(self.client, 'buyer')
        self.assertEqual(self.client.get('/api/admin/pr-number-format/').status_code, 403)
        self.assertEqual(self.client.patch('/api/admin/pr-number-format/', data='{}', content_type='application/json').status_code, 403)

    def test_admin_can_view_and_update_settings(self):
        _login_as(self.client, 'admin')
        get_response = self.client.get('/api/admin/pr-number-format/')
        self.assertEqual(get_response.status_code, 200)
        self.assertIn('pattern', get_response.json())

        patch_response = self.client.patch(
            '/api/admin/pr-number-format/',
            data=json.dumps({'prefix': 'CTU', 'sequence_digits': 4}),
            content_type='application/json',
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()['prefix'], 'CTU')
        self.assertEqual(patch_response.json()['sequence_digits'], 4)


class AdminPrNotificationSettingsEndpointAuthTests(TestCase):
    """admin_pr_notification_settings (GET/PATCH): admin-only PR email settings."""

    def test_unauthenticated_requests_are_rejected_with_401(self):
        self.assertEqual(self.client.get('/api/admin/pr-notification-settings/').status_code, 401)
        self.assertEqual(
            self.client.patch('/api/admin/pr-notification-settings/', data='{}', content_type='application/json').status_code,
            401,
        )

    def test_non_admin_requests_are_rejected_with_403(self):
        _login_as(self.client, 'buyer')
        self.assertEqual(self.client.get('/api/admin/pr-notification-settings/').status_code, 403)
        self.assertEqual(
            self.client.patch('/api/admin/pr-notification-settings/', data='{}', content_type='application/json').status_code,
            403,
        )

    def test_admin_can_view_and_update_settings(self):
        _login_as(self.client, 'admin')
        get_response = self.client.get('/api/admin/pr-notification-settings/')
        self.assertEqual(get_response.status_code, 200)
        self.assertIn('mute_automatic_transitions', get_response.json())

        patch_response = self.client.patch(
            '/api/admin/pr-notification-settings/',
            data=json.dumps({'notify_matched': False, 'mute_automatic_transitions': True}),
            content_type='application/json',
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertFalse(patch_response.json()['notify_matched'])
        self.assertTrue(patch_response.json()['mute_automatic_transitions'])
        # Untouched fields are left as-is, not reset to defaults.
        self.assertTrue(patch_response.json()['notify_rejected'])

    def test_non_boolean_value_is_rejected(self):
        _login_as(self.client, 'admin')
        response = self.client.patch(
            '/api/admin/pr-notification-settings/',
            data=json.dumps({'enabled': 'yes'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class BuyerEndpointAuthTests(TestCase):
    """next_pr_number_preview as a representative buyer-only endpoint."""

    def test_unauthenticated_request_is_rejected_with_401(self):
        self.assertEqual(self.client.get('/api/pr/next-number/').status_code, 401)

    def test_admin_cannot_use_the_buyer_endpoint(self):
        _login_as(self.client, 'admin')
        self.assertEqual(self.client.get('/api/pr/next-number/').status_code, 403)

    def test_buyer_request_succeeds(self):
        _login_as(self.client, 'buyer')
        response = self.client.get('/api/pr/next-number/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('pr_no', response.json())


class SupplierOwnershipAuthTests(TestCase):
    """supplier_profile as a representative owner_param='supplier_id' endpoint."""

    def setUp(self):
        self.mine = Supplier.objects.create(company_name='My Company', email='me@example.com', status='Approved')
        self.theirs = Supplier.objects.create(company_name='Other Company', email='them@example.com', status='Approved')

    def test_unauthenticated_request_is_rejected_with_401(self):
        response = self.client.get(f'/api/suppliers/{self.mine.id}/profile/')
        self.assertEqual(response.status_code, 401)

    def test_buyer_role_cannot_use_the_supplier_endpoint(self):
        _login_as(self.client, 'buyer')
        response = self.client.get(f'/api/suppliers/{self.mine.id}/profile/')
        self.assertEqual(response.status_code, 403)

    def test_supplier_cannot_access_a_different_suppliers_profile(self):
        _login_as(self.client, 'supplier', supplier=self.mine)
        response = self.client.get(f'/api/suppliers/{self.theirs.id}/profile/')
        self.assertEqual(response.status_code, 403)

    def test_supplier_with_no_bound_supplier_id_is_rejected(self):
        # e.g. a supplier login account that never matched a Supplier record -
        # must never fall back to granting access to an arbitrary supplier.
        _login_as(self.client, 'supplier')
        response = self.client.get(f'/api/suppliers/{self.mine.id}/profile/')
        self.assertEqual(response.status_code, 403)

    def test_supplier_can_access_their_own_profile(self):
        _login_as(self.client, 'supplier', supplier=self.mine)
        response = self.client.get(f'/api/suppliers/{self.mine.id}/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.mine.id)

    def test_admin_can_view_any_suppliers_profile(self):
        # The admin Supplier Management screen opens each registration's
        # details through this endpoint.
        _login_as(self.client, 'admin')
        response = self.client.get(f'/api/suppliers/{self.theirs.id}/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.theirs.id)

    def test_admin_cannot_edit_a_suppliers_profile(self):
        _login_as(self.client, 'admin')
        response = self.client.patch(
            f'/api/suppliers/{self.theirs.id}/profile/',
            data=json.dumps({'company_name': 'Renamed by admin'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.company_name, 'Other Company')

    def test_supplier_cannot_upload_a_document_for_another_supplier(self):
        _login_as(self.client, 'supplier', supplier=self.mine)
        response = self.client.post(f'/api/suppliers/{self.theirs.id}/documents/resubmit/')
        self.assertEqual(response.status_code, 403)


class NotificationOwnershipAuthTests(TestCase):
    """supplier_mark_notification_read: ownership is checked manually inside
    the view (no supplier_id in the URL for the decorator's owner_param)."""

    def setUp(self):
        from api.models import Notification

        self.mine = Supplier.objects.create(company_name='My Company', email='me@example.com', status='Approved')
        self.theirs = Supplier.objects.create(company_name='Other Company', email='them@example.com', status='Approved')
        self.their_notification = Notification.objects.create(
            supplier=self.theirs,
            notification_type=Notification.TYPE_OPPORTUNITY,
            title='t', message='m',
        )

    def test_supplier_cannot_mark_another_suppliers_notification_read(self):
        _login_as(self.client, 'supplier', supplier=self.mine)
        response = self.client.post(f'/api/notifications/{self.their_notification.id}/read/')
        self.assertEqual(response.status_code, 403)
        self.their_notification.refresh_from_db()
        self.assertFalse(self.their_notification.is_read)

    def test_supplier_can_mark_their_own_notification_read(self):
        _login_as(self.client, 'supplier', supplier=self.theirs)
        response = self.client.post(f'/api/notifications/{self.their_notification.id}/read/')
        self.assertEqual(response.status_code, 200)
        self.their_notification.refresh_from_db()
        self.assertTrue(self.their_notification.is_read)


class PurchaseRequestDetailsRedactionTests(TestCase):
    """purchase_request_details: any authenticated role may view it, but
    quotations (other suppliers' bids) are redacted by role/ownership."""

    def setUp(self):
        # A posted opportunity, so suppliers may open it (unposted PRs are
        # hidden from suppliers - see the posting tests).
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU', pr_no='2026-09-001', status=PurchaseRequest.STATUS_MATCHED,
            is_posted=True, submitted_by='enduser1',
        )
        self.supplier_a = Supplier.objects.create(company_name='Supplier A', email='a@example.com', status='Approved')
        self.supplier_b = Supplier.objects.create(company_name='Supplier B', email='b@example.com', status='Approved')
        Quotation.objects.create(supplier=self.supplier_a, purchase_request=self.pr, quoted_amount=1000)
        Quotation.objects.create(supplier=self.supplier_b, purchase_request=self.pr, quoted_amount=2000)

    def test_unauthenticated_request_is_rejected_with_401(self):
        response = self.client.get(f'/api/pr/{self.pr.id}/details/')
        self.assertEqual(response.status_code, 401)

    def test_admin_sees_every_quotation(self):
        _login_as(self.client, 'admin')
        response = self.client.get(f'/api/pr/{self.pr.id}/details/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['quotations']), 2)

    def test_supplier_sees_only_their_own_quotation(self):
        _login_as(self.client, 'supplier', supplier=self.supplier_a)
        response = self.client.get(f'/api/pr/{self.pr.id}/details/')
        self.assertEqual(response.status_code, 200)
        quotations = response.json()['quotations']
        self.assertEqual(len(quotations), 1)
        self.assertEqual(quotations[0]['supplier_id'], self.supplier_a.id)

    def test_buyer_sees_no_quotations(self):
        role = Role.objects.get_or_create(name='buyer')[0]
        _login_as(self.client, 'buyer', user=User.objects.create(username='enduser1', password_hash='x', role=role))
        response = self.client.get(f'/api/pr/{self.pr.id}/details/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['quotations'], [])


class RegisterEndpointAuthTests(TestCase):
    """register (POST /api/register/) creates login accounts - including,
    if the caller could pick any role, an admin account - so it must be
    admin-only rather than public. It's only ever called from the Admin
    dashboard's "create End User account" action."""

    def test_unauthenticated_registration_is_rejected(self):
        response = self.client.post(
            '/api/register/',
            data=json.dumps({'username': 'newadmin', 'password': 'x', 'role': 'admin'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(User.objects.filter(username='newadmin').exists())

    def test_buyer_cannot_self_register_a_buyer_account(self):
        _login_as(self.client, 'buyer')
        response = self.client.post(
            '/api/register/',
            data=json.dumps({'username': 'sneaky-buyer', 'password': 'x', 'role': 'buyer'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_a_buyer_account(self):
        _login_as(self.client, 'admin')
        response = self.client.post(
            '/api/register/',
            data=json.dumps({'username': 'new-buyer', 'password': 'x', 'role': 'buyer'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='new-buyer', role__name='buyer').exists())


class LoginSessionTests(TestCase):
    """login_view / logout_view: session issuance and the removal of the
    client-controllable supplier_id trust."""

    def setUp(self):
        from api.views import hash_password

        self.role = Role.objects.get_or_create(name='supplier')[0]
        self.user = User.objects.create(
            username='suppdemo',
            password_hash=hash_password('Sup3rSecret!'),
            full_name='Jane Doe',
            role=self.role,
            is_active=True,
        )

    def test_login_establishes_a_session_admin_endpoints_accept(self):
        Category.objects.create(name='Office Supplies')
        role = Role.objects.get_or_create(name='admin')[0]
        User.objects.create(username='admindemo', password_hash='', role=role)
        from api.views import hash_password
        User.objects.filter(username='admindemo').update(password_hash=hash_password('AdminPass1!'))

        login = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'admindemo', 'password': 'AdminPass1!', 'role': 'admin'}),
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)

        response = self.client.get('/api/admin/dashboard-summary/')
        self.assertEqual(response.status_code, 200)

    def test_client_supplied_supplier_id_is_ignored_on_login(self):
        # This user's email/full_name don't match ``victim`` at all - a
        # client-supplied supplier_id must not be able to bind the session to
        # someone else's supplier record.
        victim = Supplier.objects.create(company_name='Victim Co', email='victim@example.com', status='Approved')

        login = self.client.post(
            '/api/login/',
            data=json.dumps({
                'username': 'suppdemo', 'password': 'Sup3rSecret!', 'role': 'supplier',
                'supplier_id': victim.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)
        payload = login.json()['user']
        self.assertNotEqual(payload.get('supplier_id'), victim.id)

        # And the session itself must not be bound to the victim either.
        response = self.client.get(f'/api/suppliers/{victim.id}/profile/')
        self.assertEqual(response.status_code, 403)

    def test_login_matches_supplier_by_email(self):
        supplier = Supplier.objects.create(company_name='Jane Co', email='suppdemo@example.com', status='Approved')

        login = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'suppdemo', 'password': 'Sup3rSecret!', 'role': 'supplier'}),
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()['user']['supplier_id'], supplier.id)

        response = self.client.get(f'/api/suppliers/{supplier.id}/profile/')
        self.assertEqual(response.status_code, 200)

    def test_logout_invalidates_the_session(self):
        Supplier.objects.create(company_name='Jane Co', email='suppdemo@example.com', status='Approved')
        self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'suppdemo', 'password': 'Sup3rSecret!', 'role': 'supplier'}),
            content_type='application/json',
        )

        logout = self.client.post('/api/logout/')
        self.assertEqual(logout.status_code, 200)

        response = self.client.get('/api/pr/next-number/')
        self.assertEqual(response.status_code, 401)


class PurchaseRequestImmutabilityAuthTests(TestCase):
    """Once an End User (Buyer) submits a Purchase Request, only the BAC
    Secretariat (admin) may edit it, change its status, or delete it. These
    endpoints must reject a buyer even on a direct, hand-crafted request -
    the React UI hiding the controls is not the enforcement boundary."""

    def setUp(self):
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU', pr_no='2026-09-050', source_filename='original.pdf',
        )
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Bond Paper', quantity=10, unit_cost=5, total_cost=50,
        )

    def test_buyer_cannot_edit_a_submitted_pr(self):
        _login_as(self.client, 'buyer')
        response = self.client.patch(
            f'/api/pr/{self.pr.id}/edit/',
            data=json.dumps({'entity_name': 'Hacked Entity', 'items': []}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.entity_name, 'CTU')
        self.assertEqual(self.pr.source_filename, 'original.pdf')
        self.assertEqual(self.pr.line_items.count(), 1)

    def test_unauthenticated_cannot_edit_a_submitted_pr(self):
        response = self.client.patch(
            f'/api/pr/{self.pr.id}/edit/',
            data=json.dumps({'entity_name': 'Hacked Entity', 'items': []}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_buyer_cannot_change_pr_status(self):
        _login_as(self.client, 'buyer')
        response = self.client.patch(
            f'/api/pr/{self.pr.id}/status/',
            data=json.dumps({'status': 'approved'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, PurchaseRequest.STATUS_UPLOADED)

    def test_buyer_cannot_delete_a_submitted_pr(self):
        _login_as(self.client, 'buyer')
        response = self.client.delete(f'/api/pr/{self.pr.id}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(PurchaseRequest.objects.filter(id=self.pr.id).exists())

    def test_admin_can_edit_the_submitted_pr_without_touching_the_original_document(self):
        # Edits are only allowed before the PR number is assigned.
        PurchaseRequest.objects.filter(id=self.pr.id).update(pr_no=None)
        _login_as(self.client, 'admin')
        response = self.client.patch(
            f'/api/pr/{self.pr.id}/edit/',
            data=json.dumps({
                'entity_name': 'Corrected Entity',
                'items': [{'item_description': 'Corrected item', 'quantity': 5, 'unit_cost': 10}],
                'reason': 'Corrected OCR misread',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.entity_name, 'Corrected Entity')
        self.assertEqual(self.pr.line_items.get().item_description, 'Corrected item')
        # The original uploaded document reference is untouched by the edit.
        self.assertEqual(self.pr.source_filename, 'original.pdf')


class PrRecheckSignaturesAuthTests(TestCase):
    """pr_recheck_signatures: available to the submitting Buyer and to the
    BAC Secretariat (admin) reviewing signature-presence results during PR
    review; no other role."""

    def test_unauthenticated_is_rejected(self):
        response = self.client.post(
            '/api/pr/recheck-signatures/',
            data=json.dumps({'filename': 'x.pdf'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_supplier_is_rejected(self):
        _login_as(self.client, 'supplier')
        response = self.client.post(
            '/api/pr/recheck-signatures/',
            data=json.dumps({'filename': 'x.pdf'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_is_allowed_to_reach_the_view(self):
        _login_as(self.client, 'admin')
        response = self.client.post(
            '/api/pr/recheck-signatures/',
            data=json.dumps({'filename': 'does-not-exist.pdf'}),
            content_type='application/json',
        )
        # Rejected for a missing document (404), not for role (403) - this
        # proves the admin passed the auth check.
        self.assertEqual(response.status_code, 404)


class PrListSourceDocumentTests(TestCase):
    """pr_list must surface the original document reference so the End User
    can view what they submitted (their PR view is otherwise read-only)."""

    def test_pr_list_includes_source_file_url(self):
        PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-09-060', source_filename='mypr.pdf')
        _login_as(self.client, 'admin')
        response = self.client.get('/api/pr/list/')
        record = response.json()[0]
        self.assertTrue(record['source_file_url'].endswith('/uploads/mypr.pdf'))


class EndUserWelcomeEmailTests(TestCase):
    """Creating an End User without a password emails them their username and
    a one-time link to set their own password (no password is ever sent)."""

    def setUp(self):
        Role.objects.get_or_create(name='buyer')
        _login_as(self.client, 'admin')

    def _create(self, **overrides):
        payload = {
            'username': 'ana.cruz', 'fullName': 'Ana Cruz', 'email': 'ana@ctu.edu.ph',
            'unitOffice': 'ICT Office', 'role': 'buyer',
        }
        payload.update(overrides)
        return self.client.post('/api/register/', data=json.dumps(payload), content_type='application/json')

    @staticmethod
    def _token_from(body):
        import re
        match = re.search(r'/reset-password\?token=([\w-]+)&setup=1', body)
        return match.group(1) if match else None

    def test_new_end_user_gets_username_and_a_working_set_password_link(self):
        from django.core import mail

        response = self._create()

        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()['welcome_email_sent'])
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['ana@ctu.edu.ph'])
        self.assertIn('Good day, Ana Cruz.', email.body)
        self.assertIn('Username: ana.cruz', email.body)
        self.assertIn('expires in 3 days', email.body)
        token = self._token_from(email.body)
        self.assertTrue(token)

        # No password works until the link is used...
        self.client.logout()
        login = self.client.post('/api/login/', data=json.dumps({'username': 'ana.cruz', 'password': '', 'role': 'buyer'}), content_type='application/json')
        self.assertNotEqual(login.status_code, 200)

        # ...then the chosen password does, and the link is spent.
        reset = self.client.post('/api/reset-password/', data=json.dumps({'token': token, 'new_password': 'MyOwnPass9'}), content_type='application/json')
        self.assertEqual(reset.status_code, 200, reset.content)
        login = self.client.post('/api/login/', data=json.dumps({'username': 'ana.cruz', 'password': 'MyOwnPass9', 'role': 'buyer'}), content_type='application/json')
        self.assertEqual(login.status_code, 200, login.content)
        again = self.client.post('/api/reset-password/', data=json.dumps({'token': token, 'new_password': 'AnotherPass9'}), content_type='application/json')
        self.assertEqual(again.status_code, 400)

    def test_set_password_link_lasts_three_days(self):
        from datetime import timedelta
        from django.utils import timezone
        from api.models import PasswordResetToken

        self._create()
        token = PasswordResetToken.objects.get(user__username='ana.cruz')
        remaining = token.expires_at - timezone.now()
        self.assertTrue(timedelta(days=2, hours=23) < remaining <= timedelta(days=3))

    def test_an_end_user_without_email_cannot_be_invited(self):
        response = self._create(email='')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username='ana.cruz').exists())

    def test_a_mail_server_failure_still_creates_the_account(self):
        from unittest.mock import patch

        with patch('api.views.EmailMessage.send', side_effect=OSError('SMTP unreachable')), \
                self.assertLogs('api.views', level='ERROR'):
            response = self._create()

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()['welcome_email_sent'])
        self.assertTrue(User.objects.filter(username='ana.cruz').exists())

    def test_other_roles_still_need_a_password(self):
        Role.objects.get_or_create(name='admin')
        response = self._create(username='second-admin', role='admin')

        self.assertEqual(response.status_code, 400)

    def test_a_mail_server_timeout_is_retried_once(self):
        from unittest.mock import patch

        with patch('api.views.EmailMessage.send', side_effect=[TimeoutError('timed out'), 1]) as send, \
                patch('api.views.time.sleep'), self.assertLogs('api.views', level='WARNING'):
            response = self._create()

        self.assertEqual(send.call_count, 2)
        self.assertTrue(response.json()['welcome_email_sent'])

    def test_an_authentication_failure_is_not_retried(self):
        import smtplib
        from unittest.mock import patch

        with patch('api.views.EmailMessage.send', side_effect=smtplib.SMTPAuthenticationError(535, b'bad')) as send, \
                patch('api.views.time.sleep'), self.assertLogs('api.views', level='ERROR'):
            response = self._create()

        self.assertEqual(send.call_count, 1)
        self.assertFalse(response.json()['welcome_email_sent'])

    def test_two_timeouts_give_up_and_report_the_failure(self):
        from unittest.mock import patch

        with patch('api.views.EmailMessage.send', side_effect=TimeoutError('timed out')) as send, \
                patch('api.views.time.sleep'), self.assertLogs('api.views', level='WARNING'):
            response = self._create()

        self.assertEqual(send.call_count, 2)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()['welcome_email_sent'])

    def _resend(self, user_id):
        return self.client.post(f'/api/buyer-accounts/{user_id}/resend-setup/')

    def test_resend_setup_sends_a_new_link_and_the_old_one_stops_working(self):
        from django.core import mail

        self._create()
        old_token = self._token_from(mail.outbox[0].body)
        user = User.objects.get(username='ana.cruz')

        response = self._resend(user.id)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['welcome_email_sent'])
        self.assertEqual(len(mail.outbox), 2)
        new_token = self._token_from(mail.outbox[1].body)
        self.assertNotEqual(new_token, old_token)

        self.client.logout()
        stale = self.client.post('/api/reset-password/', data=json.dumps({'token': old_token, 'new_password': 'MyOwnPass9'}), content_type='application/json')
        self.assertEqual(stale.status_code, 400)
        fresh = self.client.post('/api/reset-password/', data=json.dumps({'token': new_token, 'new_password': 'MyOwnPass9'}), content_type='application/json')
        self.assertEqual(fresh.status_code, 200, fresh.content)

    def test_resend_is_only_for_accounts_that_never_signed_in(self):
        from django.utils import timezone

        self._create()
        user = User.objects.get(username='ana.cruz')
        listed = self.client.get('/api/buyer-accounts/').json()
        self.assertTrue(next(a for a in listed if a['id'] == user.id)['setup_pending'])

        User.objects.filter(pk=user.pk).update(last_login=timezone.now())
        self.assertEqual(self._resend(user.id).status_code, 409)
        listed = self.client.get('/api/buyer-accounts/').json()
        self.assertFalse(next(a for a in listed if a['id'] == user.id)['setup_pending'])

    def test_resend_requires_admin_and_an_end_user_account(self):
        self._create()
        user = User.objects.get(username='ana.cruz')
        admin = User.objects.exclude(pk=user.pk).first()

        self.assertEqual(self._resend(admin.id).status_code, 404)  # not an End User
        self.client.logout()
        self.assertEqual(self._resend(user.id).status_code, 401)
        _login_as(self.client, 'buyer')
        self.assertEqual(self._resend(user.id).status_code, 403)


class AdminAuditTrailExportTests(TestCase):
    """admin_export_pr_audit_trail / admin_export_supplier_change_log."""

    def setUp(self):
        import json as _json
        from api.models import PRAuditLog, PRPostingLog, PurchaseRequestItem, SupplierChangeLog

        self.admin = _login_as(self.client, 'admin')
        self.pr = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-11-010', office_section='ICT Office')
        self.other = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-11-011', office_section='Registrar')
        item = PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Laptop, 16GB RAM', unit='pc', quantity=2, unit_cost=1000,
        )
        PRAuditLog.objects.create(
            pr=self.pr, field_name='purpose', old_value='Old purpose', new_value='New purpose',
            edited_by=self.admin, edited_by_username=self.admin.username, reason='Typo on the form',
        )
        PRAuditLog.objects.create(
            pr=self.pr, item_id=item.id, field_name='quantity', old_value='1.00', new_value='2.00',
            edited_by=self.admin, edited_by_username=self.admin.username, reason='Per end user',
        )
        PRAuditLog.objects.create(
            pr=self.pr, item_id=999, field_name='item', event_type=PRAuditLog.EVENT_ITEM_REMOVED,
            old_value=_json.dumps({'item_description': 'Mouse', 'quantity': '3.00', 'unit': 'pc', 'unit_cost': '250.00'}),
            edited_by=self.admin, edited_by_username=self.admin.username, reason='Duplicate line',
        )
        PRPostingLog.objects.create(
            pr=self.pr, action=PRPostingLog.ACTION_POSTED, changed_by=self.admin,
            changed_by_username=self.admin.username,
        )
        PRPostingLog.objects.create(pr=self.pr, action=PRPostingLog.ACTION_UNPOSTED, automatic=True, reason='Status changed')
        PRAuditLog.objects.create(
            pr=self.other, field_name='purpose', old_value='a', new_value='b',
            edited_by=self.admin, edited_by_username=self.admin.username, reason='x',
        )

        self.acme = Supplier.objects.create(company_name='Acme Corp', email='acme@example.com', status='Approved')
        self.beta = Supplier.objects.create(company_name='Beta Trading', email='beta@example.com', status='Rejected')
        SupplierChangeLog.objects.create(
            supplier=self.acme, event_type=SupplierChangeLog.EVENT_FIELD_EDIT, field_name='contact_person',
            old_value='Jo', new_value='Jo Reyes', changed_by_username='acme', changed_by_role='supplier',
        )
        SupplierChangeLog.objects.create(
            supplier=self.acme, event_type=SupplierChangeLog.EVENT_STATUS, field_name='status',
            old_value='Pending Review', new_value='Approved', note='Complete', changed_by_username='bac',
            changed_by_role='admin',
        )
        SupplierChangeLog.objects.create(
            supplier=self.beta, event_type=SupplierChangeLog.EVENT_STATUS, field_name='status',
            old_value='Pending Review', new_value='Rejected', changed_by_username='bac', changed_by_role='admin',
        )

    def _rows(self, url):
        import csv
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        header, *rows = list(csv.reader(_csv_body(response).splitlines()))
        return [dict(zip(header, row)) for row in rows]

    def test_both_require_admin(self):
        self.client.logout()
        for url in ('/api/admin/export/pr-audit-trail/', '/api/admin/export/supplier-change-log/'):
            self.assertEqual(self.client.get(url).status_code, 401)
        _login_as(self.client, 'buyer')
        for url in ('/api/admin/export/pr-audit-trail/', '/api/admin/export/supplier-change-log/'):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_pr_audit_trail_lists_edits_and_postings_with_labels(self):
        rows = self._rows('/api/admin/export/pr-audit-trail/?search=ict')
        self.assertEqual({row['PR No.'] for row in rows}, {'2026-11-010'})  # filtered like the table
        events = [row['Event'] for row in rows]
        self.assertEqual(events, ['Field edited', 'Field edited', 'Item removed', 'Posted', 'Taken down (automatic)'])

        purpose, quantity, removed, posted, unposted = rows
        self.assertEqual((purpose['Field'], purpose['Old Value'], purpose['New Value']), ('Purpose', 'Old purpose', 'New purpose'))
        self.assertEqual(purpose['Reason'], 'Typo on the form')
        self.assertEqual(purpose['Role'], 'BAC Secretariat')
        self.assertEqual((quantity['Field'], quantity['Item']), ('Quantity', 'Laptop, 16GB RAM'))
        self.assertEqual(removed['Item'], 'Mouse')
        self.assertEqual(removed['Old Value'], 'Mouse · 3.00 pc @ 250.00')
        self.assertEqual(posted['By'], self.admin.username)
        self.assertEqual((unposted['By'], unposted['Reason']), ('System', 'Status changed'))

    def test_supplier_change_log_is_filtered_like_the_table(self):
        rows = self._rows('/api/admin/export/supplier-change-log/?status=Approved')
        self.assertEqual({row['Supplier'] for row in rows}, {'Acme Corp'})
        edit, decision = rows
        self.assertEqual((edit['Event'], edit['Field'], edit['New Value']), ('Profile field edited', 'Contact Person', 'Jo Reyes'))
        self.assertEqual(edit['Role'], 'Supplier')
        self.assertEqual((decision['Event'], decision['Note'], decision['Role']), ('Status changed', 'Complete', 'BAC Secretariat'))

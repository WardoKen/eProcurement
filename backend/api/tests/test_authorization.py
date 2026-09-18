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
        self.pr = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-09-001')
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
        _login_as(self.client, 'buyer')
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
        _login_as(self.client, 'admin')
        response = self.client.patch(
            f'/api/pr/{self.pr.id}/edit/',
            data=json.dumps({
                'entity_name': 'Corrected Entity',
                'items': [{'item_description': 'Corrected item', 'quantity': 5, 'unit_cost': 10}],
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

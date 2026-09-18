import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from api.models import Category, Notification, PurchaseRequest, PurchaseRequestItem, Quotation, RFQ, RFQItem, Role, Supplier, SupplierCategory, SupplierDocument, User
from api.supplier_registration import get_required_business_document_key, validate_supplier_payload
from api.views import hash_password


def _min_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _image_bytes(fmt: str) -> bytes:
    import io
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format=fmt)
    return buffer.getvalue()


_PDF_BYTES = _min_pdf_bytes()
_PNG_BYTES = _image_bytes("PNG")
_JPG_BYTES = _image_bytes("JPEG")


def _login_as(client, role_name, *, user=None, supplier=None):
    """Authenticate the Django test client's session as a user with the given role.

    Mirrors what ``login_view`` stores in the session (user_id/role/username,
    plus supplier_id for supplier accounts), without needing a real password
    round trip in every test. Returns the ``User`` instance used.
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


class SupplierRegistrationValidationTests(SimpleTestCase):
    def test_missing_required_fields_are_reported(self):
        payload = {
            'companyName': '',
            'businessType': 'Sole Proprietorship',
            'businessAddress': '',
            'contactPerson': '',
            'contactNumber': 'abc',
            'email': 'not-an-email',
            'productsServices': '',
            'categories': [],
        }

        errors = validate_supplier_payload(payload, files={}, categories=[])

        self.assertIn('Company Name is required', errors)
        self.assertIn('Business Address is required', errors)
        self.assertIn('Contact Person is required', errors)
        self.assertIn('Phone number must be valid', errors)
        self.assertIn('Email address must be valid', errors)
        self.assertIn('At least one category must be selected', errors)

    def test_business_type_specific_document_is_required(self):
        self.assertEqual(get_required_business_document_key('Sole Proprietorship'), 'dti_registration')
        self.assertEqual(get_required_business_document_key('Corporation'), 'sec_registration')
        self.assertEqual(get_required_business_document_key('Cooperative'), 'cda_registration')
        self.assertIsNone(get_required_business_document_key('Others'))

    def test_missing_required_uploads_are_reported(self):
        payload = {
            'companyName': 'Acme Supply',
            'businessType': 'Sole Proprietorship',
            'businessAddress': '123 Main',
            'contactPerson': 'Jane Doe',
            'contactNumber': '+639171234567',
            'email': 'jane@example.com',
            'productsServices': 'Office supplies',
            'categories': ['Office Supplies'],
        }

        errors = validate_supplier_payload(payload, files={}, categories=['Office Supplies'])

        self.assertIn('Mayor\'s Permit is required', errors)
        self.assertIn('Business Permit is required', errors)
        self.assertIn('PhilGEPS Registration is required', errors)
        self.assertIn('BIR Registration is required', errors)
        self.assertIn('Tax Clearance is required', errors)
        self.assertIn('DTI Registration is required', errors)

    def test_png_files_are_accepted_for_supplier_documents(self):
        payload = {
            'companyName': 'Acme Supply',
            'businessType': 'Sole Proprietorship',
            'businessAddress': '123 Main',
            'contactPerson': 'Jane Doe',
            'contactNumber': '+639171234567',
            'email': 'jane@example.com',
            'productsServices': 'Office supplies',
            'categories': ['Office Supplies'],
        }

        png_file = SimpleUploadedFile('permit.png', _PNG_BYTES, content_type='image/png')
        errors = validate_supplier_payload(
            payload,
            files={
                'mayor_permit': png_file,
                'business_permit': png_file,
                'philgeps_registration': png_file,
                'bir_registration': png_file,
                'tax_clearance': png_file,
                'dti_registration': png_file,
            },
            categories=['Office Supplies'],
        )

        self.assertNotIn('has an unsupported file type', errors)


class SupplierAdminReviewTests(TestCase):
    def test_supplier_registration_creates_login_account(self):
        role = Role.objects.get_or_create(name='supplier')[0]
        category = Category.objects.create(name='Office Supplies')
        response = self.client.post(
            '/api/suppliers/register',
            data={
                'companyName': 'Acme Supply',
                'businessType': 'Sole Proprietorship',
                'businessAddress': '123 Main',
                'contactPerson': 'Jane Doe',
                'contactNumber': '+639171234567',
                'email': 'jane@example.com',
                'productsServices': 'Office supplies',
                'category_ids': str(category.id),
                'username': 'supplierdemo',
                'password': 'Supplier123!',
                'confirmPassword': 'Supplier123!',
                'mayor_permit': SimpleUploadedFile('mayor.pdf', _PDF_BYTES, content_type='application/pdf'),
                'business_permit': SimpleUploadedFile('business.pdf', _PDF_BYTES, content_type='application/pdf'),
                'philgeps_registration': SimpleUploadedFile('philgeps.pdf', _PDF_BYTES, content_type='application/pdf'),
                'bir_registration': SimpleUploadedFile('bir.pdf', _PDF_BYTES, content_type='application/pdf'),
                'tax_clearance': SimpleUploadedFile('tax.pdf', _PDF_BYTES, content_type='application/pdf'),
                'dti_registration': SimpleUploadedFile('dti.pdf', _PDF_BYTES, content_type='application/pdf'),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='supplierdemo', role=role).exists())
        supplier = Supplier.objects.get(email='jane@example.com')
        self.assertTrue(SupplierCategory.objects.filter(supplier=supplier, category=category).exists())

    def _register_supplier(self, *, username, email, company='Acme Supply', password='Supplier123!'):
        Role.objects.get_or_create(name='supplier')
        category = Category.objects.filter(name='Office Supplies').first() or Category.objects.create(name='Office Supplies')

        def pdf(name):
            return SimpleUploadedFile(name, _PDF_BYTES, content_type='application/pdf')

        return self.client.post(
            '/api/suppliers/register',
            data={
                'companyName': company, 'businessType': 'Sole Proprietorship', 'businessAddress': '123 Main',
                'contactPerson': 'Jane Doe', 'contactNumber': '+639171234567', 'email': email,
                'productsServices': 'Office supplies', 'category_ids': str(category.id),
                'username': username, 'password': password, 'confirmPassword': password,
                'mayor_permit': pdf('mayor.pdf'), 'business_permit': pdf('business.pdf'),
                'philgeps_registration': pdf('philgeps.pdf'), 'bir_registration': pdf('bir.pdf'),
                'tax_clearance': pdf('tax.pdf'), 'dti_registration': pdf('dti.pdf'),
            },
            format='multipart',
        )

    def test_supplier_registration_rejects_duplicate_username_without_overwriting(self):
        first = self._register_supplier(username='dup-user', email='first@example.com', company='First Co')
        self.assertEqual(first.status_code, 201)
        original = User.objects.get(username='dup-user')

        second = self._register_supplier(username='dup-user', email='second@example.com', company='Second Co')
        self.assertEqual(second.status_code, 409)

        reloaded = User.objects.get(username='dup-user')
        self.assertEqual(User.objects.filter(username='dup-user').count(), 1)
        self.assertEqual(reloaded.id, original.id)
        self.assertEqual(reloaded.password_hash, original.password_hash)
        # the entire second registration is rolled back, not just the account
        self.assertFalse(Supplier.objects.filter(email='second@example.com').exists())

    def test_supplier_registration_rejects_username_that_differs_only_by_case(self):
        self.assertEqual(self._register_supplier(username='CaseUser', email='a@example.com').status_code, 201)
        clash = self._register_supplier(username='caseuser', email='b@example.com')
        self.assertEqual(clash.status_code, 409)
        self.assertEqual(User.objects.filter(username__iexact='caseuser').count(), 1)

    def test_supplier_login_response_includes_linked_supplier_status(self):
        role = Role.objects.get_or_create(name='supplier')[0]
        User.objects.create(
            username='supplierdemo',
            password_hash=hash_password('supplier123'),
            full_name='Supplier Demo',
            role=role,
            is_active=True,
        )
        supplier = Supplier.objects.create(
            company_name='Acme Supply',
            business_type='Sole Proprietorship',
            email='supplierdemo@example.com',
            status='For Compliance',
        )

        response = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'supplierdemo', 'password': 'supplier123', 'role': 'supplier', 'supplier_id': supplier.id}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['user']['supplier_id'], supplier.id)
        self.assertEqual(payload['user']['supplier_status'], 'For Compliance')

    def test_buyer_account_registration_stores_contact_details(self):
        Role.objects.get_or_create(name='buyer')
        _login_as(self.client, 'admin')
        response = self.client.post(
            '/api/register/',
            data=json.dumps({
                'username': 'buyer-contact',
                'password': 'buyer1234',
                'fullName': 'Buyer Contact',
                'email': 'buyer@example.com',
                'unitOffice': 'Accounting Office',
                'role': 'buyer',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        buyer = User.objects.get(username='buyer-contact')
        self.assertEqual(buyer.email, 'buyer@example.com')
        self.assertEqual(buyer.unit_office, 'Accounting Office')

        login_response = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'buyer-contact', 'password': 'buyer1234', 'role': 'buyer'}),
            content_type='application/json',
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()['user']['email'], 'buyer@example.com')
        self.assertEqual(login_response.json()['user']['unit_office'], 'Accounting Office')

    def test_admin_can_approve_supplier_registration(self):
        supplier = Supplier.objects.create(
            company_name='Acme Supply',
            business_type='Sole Proprietorship',
            email='acme@example.com',
            status='Pending Review',
        )
        _login_as(self.client, 'admin')

        response = self.client.patch(
            f'/api/suppliers/{supplier.id}/status/',
            data=json.dumps({'status': 'Approved'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        supplier.refresh_from_db()
        self.assertEqual(supplier.status, 'Approved')

    def test_admin_can_request_additional_documents(self):
        supplier = Supplier.objects.create(
            company_name='Acme Supply',
            business_type='Sole Proprietorship',
            email='acme@example.com',
            status='Pending Review',
        )
        _login_as(self.client, 'admin')

        response = self.client.patch(
            f'/api/suppliers/{supplier.id}/status/',
            data=json.dumps({'status': 'For Compliance', 'remarks': 'Please upload a clearer PhilGEPS certificate.'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        supplier.refresh_from_db()
        self.assertEqual(supplier.status, 'For Compliance')

    def test_admin_can_verify_documents_without_changing_approved_status(self):
        supplier = Supplier.objects.create(
            company_name='Acme Supply',
            business_type='Sole Proprietorship',
            email='acme@example.com',
            status='Approved',
        )
        document = SupplierDocument.objects.create(
            supplier=supplier,
            doc_type='philgeps_registration',
            filename='philgeps.pdf',
            verification_status='Pending',
        )
        Notification.objects.all().delete()
        _login_as(self.client, 'admin')

        response = self.client.patch(
            f'/api/suppliers/{supplier.id}/status/',
            data=json.dumps({
                'status': 'Approved',
                'document_statuses': {str(document.id): 'Verified'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        document.refresh_from_db()
        supplier.refresh_from_db()
        self.assertEqual(document.verification_status, 'Verified')
        self.assertEqual(supplier.status, 'Approved')
        self.assertEqual(response.json()['documents'][0]['verification_status'], 'Verified')
        # Re-confirming an already-approved supplier must not re-notify them.
        self.assertFalse(Notification.objects.filter(notification_type=Notification.TYPE_PROFILE_APPROVED).exists())

    def test_supplier_status_no_longer_accepts_deactivated(self):
        supplier = Supplier.objects.create(company_name='Acme Supply', email='acme@example.com', status='Approved')
        _login_as(self.client, 'admin')
        response = self.client.patch(
            f'/api/suppliers/{supplier.id}/status/',
            data=json.dumps({'status': 'Deactivated', 'remarks': 'no longer trading'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        supplier.refresh_from_db()
        self.assertEqual(supplier.status, 'Approved')


class AccountDeletionTests(TestCase):
    def setUp(self):
        _login_as(self.client, 'admin')

    def _supplier_role(self):
        return Role.objects.get_or_create(name='supplier')[0]

    def test_admin_can_delete_supplier_and_all_attached_records(self):
        pr = PurchaseRequest.objects.create(entity_name='CTU', pr_no='2026-09-001')
        supplier = Supplier.objects.create(company_name='Acme', email='acme@example.com', status='Approved')
        category = Category.objects.create(name='Office Supplies')
        SupplierCategory.objects.create(supplier=supplier, category=category)
        SupplierDocument.objects.create(supplier=supplier, doc_type='philgeps_registration', filename='p.pdf')
        rfq = RFQ.objects.create(rfq_no='RFQ-2026-9001', purchase_request=pr, supplier=supplier,
                                 subject='RFQ', message='Please quote', status=RFQ.STATUS_SENT)
        Quotation.objects.create(supplier=supplier, purchase_request=pr, rfq=rfq, quoted_amount=100)
        Notification.objects.create(supplier=supplier, notification_type=Notification.TYPE_RFQ_RECEIVED,
                                    title='t', message='m')
        login = User.objects.create(username='acme', password_hash='x', full_name='', role=self._supplier_role())

        response = self.client.delete(f'/api/suppliers/{supplier.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Supplier.objects.filter(id=supplier.id).exists())
        self.assertFalse(SupplierCategory.objects.exists())
        self.assertFalse(SupplierDocument.objects.exists())
        self.assertFalse(RFQ.objects.exists())
        self.assertFalse(Quotation.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(User.objects.filter(id=login.id).exists())
        # unrelated records survive
        self.assertTrue(PurchaseRequest.objects.filter(id=pr.id).exists())

    def test_deleting_supplier_keeps_unrelated_supplier_login(self):
        keep = Supplier.objects.create(company_name='Keep Co', email='keepco@example.com', status='Approved')
        drop = Supplier.objects.create(company_name='Drop Co', email='dropco@example.com', status='Rejected')
        keep_login = User.objects.create(username='keepco', password_hash='x', role=self._supplier_role())
        drop_login = User.objects.create(username='dropco', password_hash='x', role=self._supplier_role())

        response = self.client.delete(f'/api/suppliers/{drop.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(id=keep_login.id).exists())
        self.assertFalse(User.objects.filter(id=drop_login.id).exists())
        self.assertTrue(Supplier.objects.filter(id=keep.id).exists())

    def test_delete_missing_supplier_returns_404(self):
        self.assertEqual(self.client.delete('/api/suppliers/999999/').status_code, 404)

    def test_admin_can_delete_buyer_account(self):
        role = Role.objects.get_or_create(name='buyer')[0]
        buyer = User.objects.create(username='buyer1', password_hash='x', role=role)
        other = User.objects.create(username='buyer2', password_hash='x', role=role)

        response = self.client.delete(f'/api/buyer-accounts/{buyer.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=buyer.id).exists())
        self.assertTrue(User.objects.filter(id=other.id).exists())

    def test_cannot_delete_non_buyer_via_buyer_endpoint(self):
        admin = User.objects.create(username='admin1', password_hash='x',
                                    role=Role.objects.get_or_create(name='admin')[0])
        response = self.client.delete(f'/api/buyer-accounts/{admin.id}/')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(User.objects.filter(id=admin.id).exists())


class RFQWorkflowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Air Conditioning')
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU Tuburan Campus',
            pr_no='2026-08-001',
            category='Air Conditioning',
            purpose='Campus cooling requirements',
        )
        self.item = PurchaseRequestItem.objects.create(
            purchase_request=self.pr,
            item_description='4.0HP Floor Standing Inverter Air Conditioning Unit',
            quantity=1,
            unit='unit',
            category='Air Conditioning',
        )
        self.supplier = Supplier.objects.create(
            company_name='CoolTech Climate Solutions Inc.',
            contact_person='Juan Dela Cruz',
            email='supplier@example.com',
            status='Approved',
        )
        SupplierCategory.objects.create(supplier=self.supplier, category=self.category)
        _login_as(self.client, 'admin')

    def test_admin_can_save_rfq_draft_without_creating_pr(self):
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'subject': 'RFQ subject', 'message': 'RFQ message'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(RFQ.objects.count(), 1)
        self.assertEqual(PurchaseRequest.objects.count(), 1)
        self.assertEqual(response.json()['status'], RFQ.STATUS_DRAFT)
        self.assertEqual(response.json()['quotation_basis'], 'LOT')

    def test_quotation_basis_defaults_to_lot_and_can_be_set_to_line(self):
        create = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'quotation_basis': 'line'}),
            content_type='application/json',
        )
        self.assertEqual(create.status_code, 201)
        rfq_id = create.json()['id']
        self.assertEqual(create.json()['quotation_basis'], 'LINE')
        self.assertEqual(RFQ.objects.get(id=rfq_id).quotation_basis, 'LINE')

        patch = self.client.patch(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'rfq_id': rfq_id, 'quotation_basis': 'garbage'}),
            content_type='application/json',
        )
        self.assertEqual(patch.status_code, 200)
        # An unrecognised value keeps the previously stored basis.
        self.assertEqual(RFQ.objects.get(id=rfq_id).quotation_basis, 'LINE')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sending_rfq_creates_notification_and_email(self):
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({
                'supplier_id': self.supplier.id,
                'mode_of_procurement': 'Small Value Procurement',
                'send': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], RFQ.STATUS_SENT)
        self.assertEqual(Notification.objects.filter(supplier=self.supplier, notification_type=Notification.TYPE_RFQ_RECEIVED).count(), 1)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.supplier.email])
        self.assertEqual(mail.outbox[0].attachments, [])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_cannot_create_second_rfq_for_supplier_after_sending(self):
        sent = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'subject': 'S', 'message': 'M',
                             'mode_of_procurement': 'Small Value Procurement', 'send': True}),
            content_type='application/json',
        )
        self.assertEqual(sent.status_code, 201)

        duplicate = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'subject': 'S2', 'message': 'M2'}),
            content_type='application/json',
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(RFQ.objects.filter(purchase_request=self.pr, supplier=self.supplier).count(), 1)

    def test_second_post_without_rfq_id_reuses_existing_draft(self):
        first = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'subject': 'First', 'message': 'M'}),
            content_type='application/json',
        )
        self.assertEqual(first.status_code, 201)
        rfq_id = first.json()['id']

        second = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'subject': 'Second', 'message': 'M'}),
            content_type='application/json',
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['id'], rfq_id)
        self.assertEqual(RFQ.objects.filter(purchase_request=self.pr, supplier=self.supplier).count(), 1)
        self.assertEqual(RFQ.objects.get(id=rfq_id).subject, 'Second')

    def test_rfq_rejects_supplier_without_matching_category(self):
        other_supplier = Supplier.objects.create(company_name='Other Supplier', email='other@example.com', status='Approved')
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': other_supplier.id}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('eligible', response.json()['message'])

    def test_admin_can_generate_rfq_pdf_preview(self):
        admin_role = Role.objects.get_or_create(name='admin')[0]
        admin_user = User.objects.create(
            username='adminrfq',
            password_hash='hashed',
            full_name='BAC Admin',
            email='admin@example.com',
            role=admin_role,
        )
        _login_as(self.client, 'admin', user=admin_user)

        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({
                'supplier_id': self.supplier.id,
                'subject': 'Request for Quotation',
                'message': 'Please quote for the requested items.',
                'mode_of_procurement': 'Small Value Procurement',
                'generate_pdf': True,
                'preview': True,
                'quotation_no': 'RFQ-2026-001',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['abc'], '₱0.00')
        self.assertIn('/uploads/rfq/', response.json()['pdf_url'])
        rfq = RFQ.objects.get(id=response.json()['id'])
        self.assertTrue(rfq.pdf_file)
        self.assertTrue(Path(settings.BASE_DIR, 'uploads', 'rfq', Path(rfq.pdf_file).name).exists())

    def test_non_admin_cannot_generate_rfq_pdf(self):
        _login_as(self.client, 'supplier', supplier=self.supplier)
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'generate_pdf': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)

    def test_quotation_can_reference_sent_rfq(self):
        rfq = RFQ.objects.create(
            rfq_no='RFQ-2026-0001', purchase_request=self.pr, supplier=self.supplier,
            subject='RFQ', message='Please quote', status=RFQ.STATUS_SENT,
        )
        _login_as(self.client, 'supplier', supplier=self.supplier)
        response = self.client.post(
            f'/api/suppliers/{self.supplier.id}/quotations/',
            data=json.dumps({'purchase_request_id': self.pr.id, 'rfq_id': rfq.id, 'quoted_amount': 1000}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Quotation.objects.get(id=response.json()['quotation_id']).rfq_id, rfq.id)
        rfq.refresh_from_db()
        self.assertEqual(rfq.status, RFQ.STATUS_QUOTATION_RECEIVED)

    def test_quotation_submission_is_allowed_with_csrf_checks_enabled(self):
        rfq = RFQ.objects.create(
            rfq_no='RFQ-2026-0002', purchase_request=self.pr, supplier=self.supplier,
            subject='RFQ', message='Please quote', status=RFQ.STATUS_SENT,
        )
        csrf_checked_client = Client(enforce_csrf_checks=True)
        _login_as(csrf_checked_client, 'supplier', supplier=self.supplier)

        response = csrf_checked_client.post(
            f'/api/suppliers/{self.supplier.id}/quotations/',
            data=json.dumps({'purchase_request_id': self.pr.id, 'rfq_id': rfq.id, 'quoted_amount': 1000}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)


class ManualBACSupplierSelectionTests(TestCase):
    """Manual BAC override: search + select a supplier outside the PR category."""

    def setUp(self):
        self.pr_category = Category.objects.get_or_create(name='Airconditioning and Airconditioning Systems')[0]
        self.other_category = Category.objects.create(name='HVAC Services')
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU Tuburan Campus',
            pr_no='2026-08-001',
            category='Airconditioning and Airconditioning Systems',
            purpose='Campus cooling requirements',
        )
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr,
            item_description='4.0HP Floor Standing Inverter Air Conditioning Unit',
            quantity=1,
            unit='unit',
            category='Airconditioning and Airconditioning Systems',
        )
        # Registered under the PR category -> normal category match.
        self.matched_supplier = Supplier.objects.create(
            company_name='ABC HVAC Solutions', email='abc@example.com', status='Approved',
        )
        SupplierCategory.objects.create(supplier=self.matched_supplier, category=self.pr_category)
        # Capable but registered elsewhere -> only reachable via manual search.
        self.other_supplier = Supplier.objects.create(
            company_name='CoolTech Climate Solutions Inc.',
            contact_person='Juan Dela Cruz',
            email='cooltech@example.com',
            contact_phone='0917-000-0000',
            business_address='Cebu City',
            status='Approved',
        )
        SupplierCategory.objects.create(supplier=self.other_supplier, category=self.other_category)

    # ---- search endpoint ------------------------------------------------------
    def _search(self, term, role='admin'):
        _login_as(self.client, role)
        return self.client.get(f'/api/suppliers/search/?name={term}')

    def test_search_requires_admin_role(self):
        supplier_client = Client()
        _login_as(supplier_client, 'supplier')
        self.assertEqual(supplier_client.get('/api/suppliers/search/?name=cool').status_code, 403)

        buyer_client = Client()
        _login_as(buyer_client, 'buyer')
        self.assertEqual(buyer_client.get('/api/suppliers/search/?name=cool').status_code, 403)

        anon_client = Client()
        self.assertEqual(anon_client.get('/api/suppliers/search/?name=cool').status_code, 401)

    def test_search_is_partial_and_case_insensitive(self):
        for term in ('cool', 'COOL', 'CLIMATE', '  climate  '):
            results = self._search(term).json()['results']
            names = [r['company_name'] for r in results]
            self.assertIn('CoolTech Climate Solutions Inc.', names, term)

    def test_search_does_not_filter_by_pr_category(self):
        # The manual search must surface a supplier that category matching excludes.
        results = self._search('cooltech').json()['results']
        self.assertEqual([r['company_name'] for r in results], ['CoolTech Climate Solutions Inc.'])
        self.assertEqual(results[0]['categories'], ['HVAC Services'])
        self.assertEqual(results[0]['status'], 'Approved')

    def test_blank_query_browses_the_full_supplier_list(self):
        # No search term is a browse, not an error - every supplier comes back.
        names = [r['company_name'] for r in self._search('').json()['results']]
        self.assertIn('CoolTech Climate Solutions Inc.', names)
        self.assertIn('ABC HVAC Solutions', names)

    def test_search_with_no_hits_returns_empty_list(self):
        data = self._search('zzzznomatch').json()
        self.assertEqual(data['results'], [])
        self.assertFalse(data['has_more'])

    def test_search_result_limit_and_has_more_flag(self):
        for n in range(25):
            Supplier.objects.create(company_name=f'Widget Supplier {n:02d}', status='Approved')
        data = self._search('widget supplier').json()
        self.assertEqual(len(data['results']), 20)
        self.assertTrue(data['has_more'])

    def test_exclude_pr_drops_category_matched_suppliers(self):
        # Default "Other Suppliers" list must never repeat the category-matched
        # section: ABC HVAC (in the PR category) is out, CoolTech (elsewhere) stays.
        _login_as(self.client, 'admin')
        data = self.client.get(f'/api/suppliers/search/?exclude_pr={self.pr.id}').json()
        names = [r['company_name'] for r in data['results']]
        self.assertIn('CoolTech Climate Solutions Inc.', names)
        self.assertNotIn('ABC HVAC Solutions', names)

    def test_exclude_pr_still_applies_the_name_filter(self):
        _login_as(self.client, 'admin')
        data = self.client.get(
            f'/api/suppliers/search/?exclude_pr={self.pr.id}&name=abc'
        ).json()
        self.assertEqual(data['results'], [])

    def test_exclude_pr_with_unknown_pr_returns_404(self):
        _login_as(self.client, 'admin')
        self.assertEqual(
            self.client.get('/api/suppliers/search/?exclude_pr=999999').status_code,
            404,
        )

    def test_browse_lists_approved_suppliers_before_others(self):
        Supplier.objects.create(company_name='AAA Pending Co', status='Pending Review')
        results = self._search('').json()['results']
        approved = [r['company_name'] for r in results if r['status'] == 'Approved']
        first_pending_index = next(
            (i for i, r in enumerate(results) if r['status'] != 'Approved'), len(results)
        )
        self.assertTrue(all(
            results.index(r) < first_pending_index
            for r in results if r['company_name'] in approved
        ))

    # ---- manual selection on the RFQ endpoint --------------------------------
    def test_manual_selection_accepts_supplier_outside_pr_category(self):
        _login_as(self.client, 'admin')
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({
                'supplier_id': self.other_supplier.id,
                'selection_type': 'manual_bac',
                'category': '',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['selection_type'], 'manual_bac')
        self.assertEqual(response.json()['selection_type_label'], 'Manual BAC Selection')
        rfq = RFQ.objects.get(id=response.json()['id'])
        self.assertEqual(rfq.selection_type, RFQ.SELECTION_MANUAL_BAC)
        self.assertEqual(rfq.supplier_id, self.other_supplier.id)

    def test_manual_selection_requires_admin_role(self):
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.other_supplier.id, 'selection_type': 'manual_bac'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(RFQ.objects.count(), 0)

    def test_manual_selection_still_rejects_unapproved_supplier(self):
        self.other_supplier.status = 'Rejected'
        self.other_supplier.save(update_fields=['status'])
        _login_as(self.client, 'admin')
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.other_supplier.id, 'selection_type': 'manual_bac'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('approved', response.json()['message'].lower())

    def test_manual_selection_does_not_create_supplier_category(self):
        before = set(
            SupplierCategory.objects.filter(supplier=self.other_supplier)
            .values_list('category__name', flat=True)
        )
        _login_as(self.client, 'admin')
        self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.other_supplier.id, 'selection_type': 'manual_bac'}),
            content_type='application/json',
        )
        after = set(
            SupplierCategory.objects.filter(supplier=self.other_supplier)
            .values_list('category__name', flat=True)
        )
        self.assertEqual(before, after)
        self.assertEqual(before, {'HVAC Services'})

    def test_normal_path_still_rejects_category_mismatch_without_flag(self):
        _login_as(self.client, 'admin')
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.other_supplier.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('eligible', response.json()['message'])

    def test_category_matched_supplier_records_category_match(self):
        _login_as(self.client, 'admin')
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.matched_supplier.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['selection_type'], 'category_match')

    def test_pr_is_unchanged_by_manual_selection(self):
        _login_as(self.client, 'admin')
        self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.other_supplier.id, 'selection_type': 'manual_bac'}),
            content_type='application/json',
        )
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.category, 'Airconditioning and Airconditioning Systems')
        self.assertEqual(self.pr.pr_no, '2026-08-001')
        self.assertEqual(self.pr.line_items.count(), 1)


class RFQModeOfProcurementTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Air Conditioning')
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU Tuburan Campus',
            pr_no='2026-08-001',
            category='Airconditioning and Airconditioning Systems',
            purpose='Campus cooling requirements',
        )
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr,
            item_description='4.0HP Floor Standing Inverter Air Conditioning Unit',
            quantity=1, unit='unit', category='Air Conditioning',
        )
        self.supplier = Supplier.objects.create(
            company_name='CoolTech Climate Solutions Inc.',
            contact_person='Juan Dela Cruz', email='supplier@example.com', status='Approved',
        )
        SupplierCategory.objects.create(supplier=self.supplier, category=self.category)
        _login_as(self.client, 'admin')

    def _create_draft(self, **extra):
        payload = {'supplier_id': self.supplier.id, 'subject': 'RFQ', 'message': 'Please quote'}
        payload.update(extra)
        return self.client.post(
            f'/api/pr/{self.pr.id}/rfq/', data=json.dumps(payload), content_type='application/json',
        )

    def test_procurement_modes_endpoint_lists_configured_options(self):
        response = self.client.get('/api/procurement-modes/')
        self.assertEqual(response.status_code, 200)
        modes = response.json()['modes']
        self.assertIn('Small Value Procurement', modes)

    def test_generate_requires_a_mode(self):
        response = self._create_draft(generate_pdf=True, preview=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Please enter a mode of procurement.')
        self.assertEqual(RFQ.objects.count(), 0)

    def test_custom_typed_mode_is_accepted_and_stored(self):
        response = self._create_draft(mode_of_procurement='  Direct Contracting (special case)  ')
        self.assertEqual(response.status_code, 201)
        rfq = RFQ.objects.get(id=response.json()['id'])
        # Trimmed, but otherwise kept verbatim - not forced onto the suggested list.
        self.assertEqual(rfq.mode_of_procurement, 'Direct Contracting (special case)')

    def test_overlong_mode_is_rejected(self):
        response = self._create_draft(mode_of_procurement='x' * 201)
        self.assertEqual(response.status_code, 400)
        self.assertIn('200 characters', response.json()['message'])

    def test_selected_mode_is_stored_and_returned_and_persists(self):
        create = self._create_draft(mode_of_procurement='Small Value Procurement')
        self.assertEqual(create.status_code, 201)
        rfq_id = create.json()['id']
        self.assertEqual(create.json()['mode_of_procurement'], 'Small Value Procurement')
        self.assertEqual(RFQ.objects.get(id=rfq_id).mode_of_procurement, 'Small Value Procurement')

        reopened = self.client.get(f'/api/pr/{self.pr.id}/rfq/')
        self.assertEqual(reopened.json()['rfqs'][0]['mode_of_procurement'], 'Small Value Procurement')

    def test_changing_mode_updates_same_rfq_without_new_record(self):
        create = self._create_draft(mode_of_procurement='Small Value Procurement',
                                    generate_pdf=True, preview=True)
        self.assertEqual(create.status_code, 201)
        rfq_id = create.json()['id']

        updated = self.client.patch(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'rfq_id': rfq_id,
                             'mode_of_procurement': 'Shopping', 'generate_pdf': True, 'preview': True}),
            content_type='application/json',
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['mode_of_procurement'], 'Shopping')
        self.assertEqual(RFQ.objects.count(), 1)
        self.assertEqual(RFQ.objects.get(id=rfq_id).mode_of_procurement, 'Shopping')
        self.assertIn('/uploads/rfq/', updated.json()['pdf_url'])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_save_then_send_flow_locks_the_rfq(self):
        # Save (mirrors the "Save RFQ" button: always regenerates the preview).
        create = self._create_draft(mode_of_procurement='Shopping', generate_pdf=True, preview=True)
        self.assertEqual(create.status_code, 201)
        rfq_id = create.json()['id']
        self.assertEqual(create.json()['status'], RFQ.STATUS_DRAFT)
        self.assertIn('/uploads/rfq/', create.json()['pdf_url'])

        # Send (mirrors the "Send RFQ to Supplier" button payload).
        sent = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'rfq_id': rfq_id, 'subject': 'RFQ',
                             'message': 'Please quote', 'mode_of_procurement': 'Shopping',
                             'generate_pdf': True, 'preview': False, 'send': True}),
            content_type='application/json',
        )
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.json()['status'], RFQ.STATUS_SENT)
        self.assertEqual(sent.json()['mode_of_procurement'], 'Shopping')
        self.assertEqual(RFQ.objects.count(), 1)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)

    def test_pdf_template_prints_the_selected_mode(self):
        from django.template.loader import render_to_string
        html = render_to_string('rfq/rfq.html', {
            'rfq_no': 'RFQ-1', 'pr_no': '2026-08-001', 'pr_date': '', 'quotation_no': '',
            'mode_of_procurement': 'Negotiated Procurement', 'quotation_basis': 'LOT',
            'supplier': {}, 'abc': 'Php0.00', 'additional_notes': '', 'items': [],
            'signatory_name': 'X', 'signatory_role': 'Y', 'signature_url': '',
        })
        self.assertIn('Negotiated Procurement', html)

    def test_mode_does_not_touch_pr_category_or_matching(self):
        create = self._create_draft(mode_of_procurement='Shopping')
        self.assertEqual(create.status_code, 201)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.category, 'Airconditioning and Airconditioning Systems')
        self.assertEqual(create.json()['purchase_request']['category'],
                         'Airconditioning and Airconditioning Systems')


class SupplierRFQResponseTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Air Conditioning')
        self.pr = PurchaseRequest.objects.create(entity_name='CTU Tuburan Campus', pr_no='2026-08-001',
                                                 category='Air Conditioning', office_section='Campus Admin')
        PurchaseRequestItem.objects.create(purchase_request=self.pr, item_description='Aircon unit',
                                           quantity=1, unit='unit', category='Air Conditioning')
        self.supplier = Supplier.objects.create(company_name='CoolTech Inc.', email='cooltech@example.com',
                                                status='Approved')
        self.other_supplier = Supplier.objects.create(company_name='Rival Co', email='rival@example.com',
                                                      status='Approved')
        self.rfq = RFQ.objects.create(rfq_no='RFQ-2026-0001', purchase_request=self.pr, supplier=self.supplier,
                                      subject='RFQ', message='Please quote', status=RFQ.STATUS_SENT,
                                      pdf_file='rfq/RFQ-2026-0001-1.pdf')

    def _pdf(self, name='completed.pdf'):
        return SimpleUploadedFile(name, _PDF_BYTES, content_type='application/pdf')

    def _upload(self, supplier, rfq, file=None):
        _login_as(self.client, 'supplier', supplier=supplier)
        return self.client.post(
            f'/api/suppliers/{supplier.id}/rfqs/{rfq.id}/response/',
            data={'file': file or self._pdf()},
            format='multipart',
        )

    def test_supplier_uploads_completed_rfq(self):
        response = self._upload(self.supplier, self.rfq)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.rfq.refresh_from_db()
        self.assertTrue(self.rfq.submitted_pdf)
        self.assertIsNotNone(self.rfq.submitted_at)
        self.assertEqual(self.rfq.status, RFQ.STATUS_QUOTATION_RECEIVED)
        self.assertEqual(body['status_label'], 'Response Submitted')
        self.assertTrue(body['submitted_pdf_url'])
        self.assertTrue(body['has_response'])
        self.assertTrue(Notification.objects.filter(
            supplier=self.supplier, notification_type=Notification.TYPE_QUOTATION_SUBMITTED,
            related_rfq_id=self.rfq.id).exists())

    def test_generated_rfq_is_preserved_after_submission(self):
        self._upload(self.supplier, self.rfq)
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.pdf_file, 'rfq/RFQ-2026-0001-1.pdf')
        self.assertNotEqual(self.rfq.submitted_pdf, self.rfq.pdf_file)

    def test_upload_rejects_non_pdf(self):
        bad = SimpleUploadedFile('quote.png', _PNG_BYTES, content_type='image/png')
        response = self._upload(self.supplier, self.rfq, file=bad)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['message'], 'Completed RFQ submissions must be uploaded as a PDF.'
        )
        self.rfq.refresh_from_db()
        self.assertFalse(self.rfq.submitted_pdf)

    def test_upload_rejects_non_pdf_content_behind_pdf_name(self):
        disguised = SimpleUploadedFile('completed.pdf', b'MZ\x90\x00 not a pdf', content_type='application/pdf')
        response = self._upload(self.supplier, self.rfq, file=disguised)
        self.assertEqual(response.status_code, 400)
        self.rfq.refresh_from_db()
        self.assertFalse(self.rfq.submitted_pdf)

    def test_supplier_cannot_upload_to_another_suppliers_rfq(self):
        response = self._upload(self.other_supplier, self.rfq)
        self.assertEqual(response.status_code, 404)
        self.rfq.refresh_from_db()
        self.assertFalse(self.rfq.submitted_pdf)

    def test_upload_rejected_when_rfq_is_draft(self):
        self.rfq.status = RFQ.STATUS_DRAFT
        self.rfq.save(update_fields=['status'])
        response = self._upload(self.supplier, self.rfq)
        self.assertEqual(response.status_code, 409)

    def test_replace_submission(self):
        first = self._upload(self.supplier, self.rfq)
        self.assertFalse(first.json()['replaced'])
        self.rfq.refresh_from_db()
        original_name = self.rfq.submitted_pdf

        second = self._upload(self.supplier, self.rfq, file=self._pdf('revised.pdf'))
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()['replaced'])
        self.rfq.refresh_from_db()
        self.assertNotEqual(self.rfq.submitted_pdf, original_name)

    def test_supplier_only_sees_own_rfqs(self):
        RFQ.objects.create(rfq_no='RFQ-2026-0002', purchase_request=self.pr, supplier=self.other_supplier,
                           subject='RFQ', message='m', status=RFQ.STATUS_SENT)
        _login_as(self.client, 'supplier', supplier=self.supplier)
        response = self.client.get(f'/api/suppliers/{self.supplier.id}/rfqs/')
        self.assertEqual(response.status_code, 200)
        ids = {r['id'] for r in response.json()['rfqs']}
        self.assertEqual(ids, {self.rfq.id})

    def test_admin_rfq_responses_shows_both_documents(self):
        self._upload(self.supplier, self.rfq)
        _login_as(self.client, 'admin')
        response = self.client.get('/api/rfqs/responses/')
        self.assertEqual(response.status_code, 200)
        row = next(r for r in response.json()['rfqs'] if r['id'] == self.rfq.id)
        self.assertTrue(row['generated_pdf_url'])
        self.assertTrue(row['submitted_pdf_url'])
        self.assertEqual(row['supplier']['company_name'], 'CoolTech Inc.')
        self.assertEqual(row['purchase_request']['pr_no'], '2026-08-001')

    def test_admin_rfq_responses_filter_and_auth(self):
        _login_as(self.client, 'admin')
        awaiting = self.client.get('/api/rfqs/responses/?status=awaiting')
        self.assertEqual({r['id'] for r in awaiting.json()['rfqs']}, {self.rfq.id})

        self._upload(self.supplier, self.rfq)
        _login_as(self.client, 'admin')
        received = self.client.get('/api/rfqs/responses/?status=received')
        self.assertEqual({r['id'] for r in received.json()['rfqs']}, {self.rfq.id})
        awaiting_after = self.client.get('/api/rfqs/responses/?status=awaiting')
        self.assertEqual(awaiting_after.json()['rfqs'], [])

        _login_as(self.client, 'supplier', supplier=self.supplier)
        forbidden = self.client.get('/api/rfqs/responses/')
        self.assertEqual(forbidden.status_code, 403)

    def test_existing_quotation_endpoint_still_works(self):
        _login_as(self.client, 'supplier', supplier=self.supplier)
        response = self.client.post(
            f'/api/suppliers/{self.supplier.id}/quotations/',
            data=json.dumps({'purchase_request_id': self.pr.id, 'rfq_id': self.rfq.id, 'quoted_amount': 5000}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Quotation.objects.filter(supplier=self.supplier, purchase_request=self.pr).count(), 1)

    def test_upload_exposes_supplier_file_name(self):
        response = self._upload(self.supplier, self.rfq, file=self._pdf('Completed RFQ - CoolTech.pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['submitted_filename'], 'Completed_RFQ_-_CoolTech.pdf')

    def test_upload_creates_no_duplicate_pr_rfq_or_quotation(self):
        pr_count, rfq_count = PurchaseRequest.objects.count(), RFQ.objects.count()
        self._upload(self.supplier, self.rfq)
        self._upload(self.supplier, self.rfq, file=self._pdf('again.pdf'))  # resubmission
        self.client.get(f'/api/suppliers/{self.supplier.id}/rfqs/')          # refresh
        self.assertEqual(PurchaseRequest.objects.count(), pr_count)
        self.assertEqual(RFQ.objects.count(), rfq_count)
        # The capstone stops at "Admin can view the completed RFQ" - uploading a
        # completed RFQ must never fabricate a Quotation record.
        self.assertEqual(Quotation.objects.filter(rfq=self.rfq).count(), 0)

    def test_upload_keeps_rfq_pr_and_supplier_association(self):
        self._upload(self.supplier, self.rfq)
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.purchase_request_id, self.pr.id)
        self.assertEqual(self.rfq.supplier_id, self.supplier.id)
        self.assertTrue(self.rfq.submitted_pdf)
        self.assertNotEqual(self.rfq.submitted_pdf, self.rfq.pdf_file)


class PurchaseRequestNumberTests(TestCase):
    def setUp(self):
        _login_as(self.client, 'buyer')

    def create_pr(self, entity='Test Entity'):
        return self.client.post(
            '/api/pr/',
            data=json.dumps({'fields': {'entityName': entity, 'requested_items': []}}),
            content_type='application/json',
        )

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_generates_next_number_from_highest_current_month_number(self, _localdate):
        PurchaseRequest.objects.create(entity_name='Existing 1', pr_no='2026-08-001')
        PurchaseRequest.objects.create(entity_name='Existing 7', pr_no='2026-08-007')

        response = self.create_pr()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['pr_no'], '2026-08-008')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_respects_manually_edited_high_number(self, _localdate):
        PurchaseRequest.objects.create(entity_name='Edited', pr_no='2026-08-050')

        response = self.create_pr()

        self.assertEqual(response.json()['pr_no'], '2026-08-051')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_ignores_other_years_and_invalid_numbers(self, _localdate):
        PurchaseRequest.objects.create(entity_name='July', pr_no='2026-07-099')
        PurchaseRequest.objects.create(entity_name='Other year', pr_no='2025-12-999')
        PurchaseRequest.objects.create(entity_name='Current', pr_no='2026-08-005')
        PurchaseRequest.objects.create(entity_name='Invalid', pr_no='2026-08-1000')

        response = self.create_pr()

        self.assertEqual(response.json()['pr_no'], '2026-08-100')

    @patch('api.views.timezone.localdate', return_value=date(2026, 9, 1))
    def test_continues_sequence_for_new_month(self, _localdate):
        PurchaseRequest.objects.create(entity_name='August', pr_no='2026-08-051')

        response = self.create_pr()

        self.assertEqual(response.json()['pr_no'], '2026-09-052')

    @patch('api.views.timezone.localdate', return_value=date(2027, 1, 1))
    def test_resets_for_new_year(self, _localdate):
        PurchaseRequest.objects.create(entity_name='Previous year', pr_no='2026-12-051')

        response = self.create_pr()

        self.assertEqual(response.json()['pr_no'], '2027-01-001')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_saves_valid_custom_number_and_uses_it_for_next_automatic_number(self, _localdate):
        custom_response = self.client.post(
            '/api/pr/',
            data=json.dumps({'fields': {
                'entityName': 'Custom Entity',
                'prNumberMode': 'custom',
                'prNumber': '2026-08-100',
            }}),
            content_type='application/json',
        )
        automatic_response = self.create_pr('Automatic Entity')

        self.assertEqual(custom_response.status_code, 201)
        self.assertEqual(custom_response.json()['pr_no'], '2026-08-100')
        self.assertEqual(automatic_response.json()['pr_no'], '2026-08-101')

    def test_rejects_invalid_or_duplicate_custom_number(self):
        PurchaseRequest.objects.create(entity_name='Existing', pr_no='2026-08-100')
        invalid_response = self.client.post(
            '/api/pr/',
            data=json.dumps({'fields': {'entityName': 'Invalid', 'prNumberMode': 'custom', 'prNumber': '2026-99-100'}}),
            content_type='application/json',
        )
        duplicate_response = self.client.post(
            '/api/pr/',
            data=json.dumps({'fields': {'entityName': 'Duplicate', 'prNumberMode': 'custom', 'prNumber': '2026-08-100'}}),
            content_type='application/json',
        )

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(duplicate_response.status_code, 409)

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_returns_automatic_number_preview(self, _localdate):
        PurchaseRequest.objects.create(entity_name='Existing', pr_no='2026-08-009')

        response = self.client.get('/api/pr/next-number/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['pr_no'], '2026-08-010')

    @patch('api.views.timezone.localdate', return_value=date(2026, 8, 24))
    def test_review_only_creation_waits_for_admin_numbering(self, _localdate):
        response = self.client.post(
            '/api/pr/',
            data=json.dumps({'fields': {
                'entityName': 'Buyer Entity',
                'reviewOnly': True,
                'sourceFilename': 'buyer-pr.pdf',
                'requested_items': [],
                'declaration_acknowledged': True,
            }}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['pr_no'])
        self.assertEqual(response.json()['status'], 'uploaded')
        self.assertEqual(PurchaseRequest.objects.count(), 1)

        pr = PurchaseRequest.objects.get()
        self.assertEqual(pr.source_filename, 'buyer-pr.pdf')
        details_response = self.client.get(f'/api/pr/{pr.id}/details/')
        self.assertEqual(details_response.status_code, 200)
        self.assertTrue(details_response.json()['source_file_url'].endswith('/uploads/buyer-pr.pdf'))
        _login_as(self.client, 'admin')
        finalize_response = self.client.patch(
            f'/api/pr/{pr.id}/edit/',
            data=json.dumps({
                'entity_name': 'Corrected Buyer Entity',
                'items': [],
                'finalize_review': True,
            }),
            content_type='application/json',
        )

        self.assertEqual(finalize_response.status_code, 200)
        pr.refresh_from_db()
        self.assertEqual(PurchaseRequest.objects.count(), 1)
        self.assertEqual(pr.entity_name, 'Corrected Buyer Entity')
        self.assertEqual(pr.status, 'in_review')
        self.assertEqual(pr.pr_no, '2026-08-001')


class SupplierMatchingTests(TestCase):
    def setUp(self):
        _login_as(self.client, 'admin')

    def test_pr_list_includes_quotation_match_flag(self):
        unmatched = PurchaseRequest.objects.create(entity_name='Unmatched Entity', pr_no='2026-08-010')
        matched = PurchaseRequest.objects.create(entity_name='Matched Entity', pr_no='2026-08-011')
        supplier = Supplier.objects.create(company_name='Supplier One')
        Quotation.objects.create(supplier=supplier, purchase_request=matched, quoted_amount=100)

        response = self.client.get('/api/pr/list/')
        records = {record['id']: record for record in response.json()}

        self.assertFalse(records[unmatched.id]['has_quotation'])
        self.assertTrue(records[matched.id]['has_quotation'])

    def test_unmatched_endpoint_returns_existing_unquoted_pr(self):
        unmatched = PurchaseRequest.objects.create(
            entity_name='Unmatched Entity',
            pr_no='2026-08-001',
            date='2026-08-24',
        )
        matched = PurchaseRequest.objects.create(entity_name='Matched Entity', pr_no='2026-08-002')
        supplier = Supplier.objects.create(company_name='Supplier One')
        Quotation.objects.create(supplier=supplier, purchase_request=matched, quoted_amount=100)

        response = self.client.get('/api/pr/unmatched/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.json()], [unmatched.id])

    def test_supplier_matching_uses_supplier_category_relationship(self):
        category = Category.objects.get_or_create(name='Airconditioning and Airconditioning Systems')[0]
        pr = PurchaseRequest.objects.create(entity_name='Aircon Entity', pr_no='2026-08-003')
        PurchaseRequestItem.objects.create(
            purchase_request=pr,
            item_description='Aircon unit',
            category=category.name,
        )
        matching_supplier = Supplier.objects.create(
            company_name='Matching Supplier', status='Approved', business_type='Others',
        )
        unrelated_supplier = Supplier.objects.create(company_name='Unrelated Supplier', status='Approved')
        SupplierCategory.objects.create(supplier=matching_supplier, category=category)
        for key in ('mayor_permit', 'business_permit', 'philgeps_registration', 'bir_registration', 'tax_clearance'):
            SupplierDocument.objects.create(
                supplier=matching_supplier, doc_type=key, filename=f'{key}.pdf',
                verification_status='Verified',
            )

        response = self.client.get(f'/api/pr/{pr.id}/supplier-match/')

        self.assertEqual(response.status_code, 200)
        groups = response.json()['groups']
        self.assertEqual([item['company_name'] for item in groups[0]['suppliers']], [matching_supplier.company_name])
        self.assertNotIn(unrelated_supplier.company_name, [item['company_name'] for item in groups[0]['suppliers']])
        self.assertEqual(groups[0]['category'], category.name)
        self.assertEqual(groups[0]['category_id'], category.id)


class CentralizedFileValidationTests(SimpleTestCase):
    """The shared api.file_validation validator + its endpoint integration."""

    def _f(self, name, data, content_type='application/octet-stream'):
        return SimpleUploadedFile(name, data, content_type=content_type)

    # ---- the validator itself ------------------------------------------------
    def test_pr_accepts_documents_and_images(self):
        from api.file_validation import UploadKind, validate_upload
        for name, data in [
            ('a.pdf', _PDF_BYTES), ('a.jpg', _JPG_BYTES),
            ('a.jpeg', _JPG_BYTES), ('a.png', _PNG_BYTES),
        ]:
            validate_upload(self._f(name, data), UploadKind.PR)  # no exception

    def test_pr_rejects_office_and_archive_and_binary_types(self):
        from api.file_validation import UploadKind, FileValidationError, validate_upload
        for name in ('a.docx', 'a.xlsx', 'a.pptx', 'a.zip', 'a.exe', 'a.txt'):
            with self.assertRaises(FileValidationError):
                validate_upload(self._f(name, b'anything at all here'), UploadKind.PR)

    def test_pr_rejects_renamed_binary(self):
        from api.file_validation import UploadKind, FileValidationError, validate_upload
        with self.assertRaises(FileValidationError):
            validate_upload(self._f('malware.pdf', b'MZ\x90\x00\x03'), UploadKind.PR)
        with self.assertRaises(FileValidationError):
            validate_upload(self._f('doc.png', _PDF_BYTES), UploadKind.PR)  # pdf bytes, .png name

    def test_empty_and_oversize_are_rejected(self):
        from api.file_validation import UploadKind, FileValidationError, validate_upload
        with self.assertRaises(FileValidationError) as ctx:
            validate_upload(self._f('a.pdf', b''), UploadKind.PR)
        self.assertEqual(ctx.exception.message, 'The uploaded file is empty.')

        big = SimpleUploadedFile('a.pdf', _PDF_BYTES)
        big.size = 11 * 1024 * 1024
        with self.assertRaises(FileValidationError) as ctx:
            validate_upload(big, UploadKind.PR)
        self.assertIn('too large', ctx.exception.message)

    def test_completed_rfq_is_pdf_only(self):
        from api.file_validation import UploadKind, FileValidationError, validate_upload
        validate_upload(self._f('r.pdf', _PDF_BYTES), UploadKind.COMPLETED_RFQ)
        for name, data in [('r.jpg', _JPG_BYTES), ('r.png', _PNG_BYTES), ('r.docx', b'PK\x03\x04')]:
            with self.assertRaises(FileValidationError) as ctx:
                validate_upload(self._f(name, data), UploadKind.COMPLETED_RFQ)
            self.assertEqual(
                ctx.exception.message, 'Completed RFQ submissions must be uploaded as a PDF.'
            )

    def test_supplier_requirement_rules_match_pr(self):
        from api.file_validation import UploadKind, FileValidationError, validate_upload
        validate_upload(self._f('permit.jpg', _JPG_BYTES), UploadKind.SUPPLIER_REQUIREMENT)
        with self.assertRaises(FileValidationError):
            validate_upload(self._f('permit.docx', b'PK\x03\x04'), UploadKind.SUPPLIER_REQUIREMENT)

    def test_corrupted_image_is_rejected(self):
        from api.file_validation import UploadKind, FileValidationError, validate_upload
        with self.assertRaises(FileValidationError):
            validate_upload(self._f('photo.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 40), UploadKind.PR)


class FileValidationEndpointTests(TestCase):
    """Invalid uploads never reach storage / OCR / a database record."""

    def test_pr_upload_rejects_docx_before_ocr(self):
        _login_as(self.client, 'buyer')
        with patch('api.views.ocr_service.process_file') as mocked_ocr:
            response = self.client.post(
                '/api/upload/',
                {'file': SimpleUploadedFile('pr.docx', b'PK\x03\x04 zip', content_type='application/octet-stream')},
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Unsupported file type', response.json()['message'])
        mocked_ocr.assert_not_called()

    def test_pr_upload_runs_ocr_for_a_valid_pdf(self):
        _login_as(self.client, 'buyer')
        from ocr.ocr_service import OCRDocument
        stub = OCRDocument(pages=[], raw_text='', source='pdf-text', filename='pr.pdf', textract_blocks=[])
        with patch('api.views.ocr_service.process_file', return_value=stub) as mocked_ocr:
            self.client.post('/api/upload/', {'file': SimpleUploadedFile('pr.pdf', _PDF_BYTES)})
        mocked_ocr.assert_called_once()

    def test_supplier_registration_rejects_docx_requirement(self):
        Role.objects.get_or_create(name='supplier')
        category = Category.objects.create(name='Office Supplies')
        response = self.client.post(
            '/api/suppliers/register',
            data={
                'companyName': 'Acme', 'businessType': 'Sole Proprietorship', 'businessAddress': '1 St',
                'contactPerson': 'Jane', 'contactNumber': '+639171234567', 'email': 'jane@acme.test',
                'productsServices': 'Supplies', 'category_ids': str(category.id),
                'username': 'acmeuser', 'password': 'Supplier123!', 'confirmPassword': 'Supplier123!',
                'mayor_permit': SimpleUploadedFile('mayor.docx', b'PK\x03\x04', content_type='application/octet-stream'),
                'business_permit': SimpleUploadedFile('business.pdf', _PDF_BYTES),
                'philgeps_registration': SimpleUploadedFile('philgeps.pdf', _PDF_BYTES),
                'bir_registration': SimpleUploadedFile('bir.pdf', _PDF_BYTES),
                'tax_clearance': SimpleUploadedFile('tax.pdf', _PDF_BYTES),
                'dti_registration': SimpleUploadedFile('dti.pdf', _PDF_BYTES),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(any('Unsupported file type' in e for e in response.json()['errors']))
        self.assertFalse(Supplier.objects.filter(email='jane@acme.test').exists())
        self.assertEqual(SupplierDocument.objects.count(), 0)

    def test_supplier_resubmit_rejects_docx(self):
        supplier = Supplier.objects.create(company_name='Acme', email='a@a.test', status='For Compliance')
        _login_as(self.client, 'supplier', supplier=supplier)
        response = self.client.post(
            f'/api/suppliers/{supplier.id}/documents/resubmit/',
            data={'doc_type': 'mayor_permit',
                  'file': SimpleUploadedFile('permit.docx', b'PK\x03\x04', content_type='application/octet-stream')},
            format='multipart',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Unsupported file type', response.json()['error'])
        self.assertEqual(SupplierDocument.objects.count(), 0)


class SignaturePresenceValidationTests(TestCase):
    """Buyer cannot submit a PR whose required signatory areas are unsigned."""

    UPLOADS = Path(settings.BASE_DIR) / 'uploads'

    def setUp(self):
        self._written = []
        _login_as(self.client, 'buyer')

    def tearDown(self):
        for path in self._written:
            Path(path).unlink(missing_ok=True)
            Path(str(path) + '.sigcheck.json').unlink(missing_ok=True)

    def _make_pr_pdf(self, name, signed):
        canvas_mod = __import__('reportlab.pdfgen.canvas', fromlist=['Canvas'])
        path = self.UPLOADS / name
        c = canvas_mod.Canvas(str(path), pagesize=(612, 792))
        c.setFont('Helvetica', 10)
        c.drawString(72, 720, 'PURCHASE REQUEST')
        c.drawString(72, 700, 'Entity Name: CTU-Tuburan Campus')
        c.drawString(72, 680, 'Item Description  Quantity  Unit Cost  Total Cost')
        c.drawString(72, 660, 'Supply of demo goods  1  100.00  100.00')
        c.drawString(72, 620, 'Purpose: demonstration')
        cols = {'requested_by': 90, 'funds_available': 250, 'approved_by': 410}
        c.drawString(cols['requested_by'], 200, 'Requested by:')
        c.drawString(cols['funds_available'], 200, 'Funds Available:')
        c.drawString(cols['approved_by'], 200, 'Approved by:')
        c.drawString(72, 176, 'Signature :   ____________   ____________   ____________')
        c.drawString(72, 150, 'Printed Name : JUAN CRUZ    MARIA SANTOS    PEDRO REYES')
        c.drawString(72, 132, 'Designation : Officer     Budget Officer    Director')
        c.drawString(72, 108, 'Specifications verified by Technical Working Group:')
        c.drawString(72, 92, 'Signature :   ____________')
        c.drawString(72, 66, 'Printed Name : ANA DELA CRUZ')
        for key, present in (signed or {}).items():
            if not present:
                continue
            cx = cols[key]
            p = c.beginPath()
            p.moveTo(cx, 182)
            for i in range(1, 24):
                t = i / 23.0
                p.lineTo(cx + t * 90.0, 182 + (14.0 if i % 2 else -10.0) * (0.4 + t))
            c.setLineWidth(1.4)
            c.drawPath(p, stroke=1, fill=0)
        c.showPage()
        c.save()
        self._written.append(path)
        return name

    def _post_pr(self, source_filename, extra=None):
        fields = {
            'entityName': 'CTU-Tuburan Campus',
            'reviewOnly': True,
            'sourceFilename': source_filename,
            'requested_items': [],
            'requested_by_name': 'JUAN CRUZ',
            'funds_available_name': 'MARIA SANTOS',
            'approved_by_name': 'PEDRO REYES',
            'declaration_acknowledged': True,
        }
        fields.update(extra or {})
        return self.client.post(
            '/api/pr/', data=json.dumps({'fields': fields}), content_type='application/json',
        )

    def test_unsigned_pr_is_rejected_with_the_missing_signatories(self):
        name = self._make_pr_pdf('sigtest-unsigned.pdf', signed={})
        response = self._post_pr(name)
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertFalse(body['success'])
        self.assertEqual(
            set(body['missing_signatures']), {'Requested By', 'Funds Available', 'Approved By'}
        )
        self.assertEqual(PurchaseRequest.objects.count(), 0)

    def test_fully_signed_pr_saves(self):
        name = self._make_pr_pdf(
            'sigtest-signed.pdf',
            signed={'requested_by': True, 'funds_available': True, 'approved_by': True},
        )
        response = self._post_pr(name)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(PurchaseRequest.objects.count(), 1)

    def test_partially_signed_pr_names_only_the_missing_one(self):
        name = self._make_pr_pdf(
            'sigtest-partial.pdf', signed={'requested_by': True, 'approved_by': True},
        )
        response = self._post_pr(name)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['missing_signatures'], ['Funds Available'])

    def test_missing_document_does_not_hard_block_the_buyer(self):
        # No file on disk -> upload-time check + disabled button are the gate.
        response = self._post_pr('sigtest-nonexistent.pdf')
        self.assertEqual(response.status_code, 201)

    def test_recheck_endpoint_returns_per_signatory_status(self):
        name = self._make_pr_pdf(
            'sigtest-recheck.pdf',
            signed={'requested_by': True, 'funds_available': True, 'approved_by': True},
        )
        response = self.client.post(
            '/api/pr/recheck-signatures/',
            data=json.dumps({'filename': name}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        validation = response.json()['signature_validation']
        self.assertTrue(validation['summary']['can_save'])
        self.assertEqual(validation['signatories']['requested_by']['state'], 'present')

    def test_recheck_endpoint_404_for_unknown_document(self):
        response = self.client.post(
            '/api/pr/recheck-signatures/',
            data=json.dumps({'filename': 'nope.pdf'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_pr_edit_is_not_subject_to_the_signature_guard(self):
        # The Admin review path (pr_update) must stay unaffected.
        pr = PurchaseRequest.objects.create(entity_name='Legacy PR', status=PurchaseRequest.STATUS_UPLOADED)
        _login_as(self.client, 'admin')
        response = self.client.patch(
            f'/api/pr/{pr.id}/edit/',
            data=json.dumps({'entity_name': 'Legacy PR (edited)', 'items': []}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    # ---- Purchase Request Submission Declaration ---------------------------
    def _signed(self, name='decltest.pdf'):
        return self._make_pr_pdf(
            name, signed={'requested_by': True, 'funds_available': True, 'approved_by': True},
        )

    def test_missing_declaration_is_rejected(self):
        response = self._post_pr(self._signed('decl-missing.pdf'), extra={'declaration_acknowledged': None})
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertTrue(body.get('declaration_required'))
        self.assertIn('acknowledge', body['error'].lower())
        self.assertEqual(PurchaseRequest.objects.count(), 0)

    def test_false_declaration_is_rejected(self):
        for value in (False, 'false', 'no', 0, ''):
            response = self._post_pr(self._signed('decl-false.pdf'), extra={'declaration_acknowledged': value})
            self.assertEqual(response.status_code, 422, value)
        self.assertEqual(PurchaseRequest.objects.count(), 0)

    def test_declaration_check_runs_before_signature_guard(self):
        # Unsigned document AND no declaration -> the declaration error wins,
        # but the save is still blocked either way.
        response = self._post_pr(
            self._make_pr_pdf('decl-order.pdf', signed={}),
            extra={'declaration_acknowledged': False},
        )
        self.assertEqual(response.status_code, 422)
        self.assertTrue(response.json().get('declaration_required'))
        self.assertEqual(PurchaseRequest.objects.count(), 0)

    def test_acknowledged_declaration_is_recorded(self):
        response = self._post_pr(self._signed('decl-ok.pdf'))
        self.assertEqual(response.status_code, 201, response.content)
        pr = PurchaseRequest.objects.get()
        self.assertTrue(pr.declaration_acknowledged)
        self.assertIsNotNone(pr.declaration_acknowledged_at)
        self.assertTrue(response.json()['declaration_acknowledged'])

    def test_double_submit_does_not_create_a_duplicate(self):
        name = self._signed('decl-dup.pdf')
        first = self._post_pr(name)
        self.assertEqual(first.status_code, 201)
        second = self._post_pr(name)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json().get('duplicate'))
        self.assertEqual(second.json()['id'], first.json()['id'])
        self.assertEqual(PurchaseRequest.objects.count(), 1)


class ManualRFQTests(TestCase):
    """Manual / unregistered-supplier RFQ workflow."""

    def setUp(self):
        Role.objects.get_or_create(name='admin')
        self.admin = User.objects.create(
            username='bacadmin', password_hash='x', role=Role.objects.get(name='admin'),
        )
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU-Tuburan Campus', pr_no='2026-09-001',
            category='Airconditioning', grand_total=50000, status=PurchaseRequest.STATUS_MATCHED,
        )
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='4.0HP Aircon unit', quantity=2, unit='unit',
        )
        _login_as(self.client, 'admin', user=self.admin)
        # Kept as an empty dict so the many `**self.admin_headers` call sites
        # below still work unchanged - real auth now comes from the session.
        self.admin_headers = {}

    def _create(self, name="Juan's Aircon Services", mode='Small Value Procurement', **extra):
        return self.client.post(
            f'/api/pr/{self.pr.id}/manual-rfq/',
            data=json.dumps({'manual_supplier_name': name, 'mode_of_procurement': mode, **extra}),
            content_type='application/json', **self.admin_headers,
        )

    def test_create_manual_rfq_assigns_quotation_number_once(self):
        response = self._create()
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertRegex(body['quotation_no'], r'^RFQ-\d{4}-\d{4}$')
        self.assertEqual(body['quotation_no'], body['rfq_no'])
        self.assertEqual(body['supplier']['id'], None)
        self.assertTrue(body['is_manual'])
        self.assertEqual(body['delivery_method'], 'manual')
        self.assertEqual(body['manual_supplier_name'], "Juan's Aircon Services")

        rfq = RFQ.objects.get(id=body['id'])
        self.assertIsNone(rfq.supplier_id)
        self.assertEqual(rfq.status, RFQ.STATUS_SENT)
        self.assertEqual(rfq.created_by_id, self.admin.id)

    def test_no_supplier_or_category_records_are_created(self):
        self._create()
        self.assertEqual(Supplier.objects.count(), 0)
        self.assertEqual(SupplierCategory.objects.count(), 0)

    def test_pdf_omits_supplier_name_but_shows_quotation_number(self):
        body = self._create().json()
        pdf = self.client.get(f'/api/manual-rfqs/{body["id"]}/pdf/', **self.admin_headers)
        self.assertEqual(pdf.status_code, 200)
        from pdfminer.high_level import extract_text
        import io
        content = b''.join(pdf.streaming_content)
        path = Path(settings.BASE_DIR) / 'uploads' / '_manualtest.pdf'
        path.write_bytes(content)
        try:
            text = extract_text(str(path))
        finally:
            path.unlink(missing_ok=True)
        self.assertNotIn('Juan', text)
        self.assertIn(body['quotation_no'], text)

    def test_repeat_same_supplier_and_pr_returns_existing_rfq(self):
        first = self._create().json()
        second = self._create(name="  juan's aircon services  ", mode='Shopping')
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json().get('existing'))
        self.assertEqual(second.json()['id'], first['id'])
        self.assertEqual(second.json()['quotation_no'], first['quotation_no'])
        self.assertEqual(RFQ.objects.filter(delivery_method='manual').count(), 1)

    def test_explicit_new_rfq_gets_a_new_quotation_number(self):
        first = self._create().json()
        again = self._create(force_new=True)
        self.assertEqual(again.status_code, 201)
        self.assertNotEqual(again.json()['quotation_no'], first['quotation_no'])
        self.assertEqual(RFQ.objects.filter(delivery_method='manual').count(), 2)

    def test_multiple_manual_suppliers_get_sequential_numbers(self):
        a = self._create(name='Supplier A').json()['quotation_no']
        b = self._create(name='Supplier B').json()['quotation_no']
        c = self._create(name='Supplier C').json()['quotation_no']
        seqs = sorted(int(x.split('-')[2]) for x in (a, b, c))
        self.assertEqual(seqs, [seqs[0], seqs[0] + 1, seqs[0] + 2])

    def test_redownload_keeps_the_same_quotation_number(self):
        body = self._create().json()
        RFQ.objects.filter(id=body['id']).update(pdf_file='')  # simulate lost server file
        again = self.client.get(f'/api/manual-rfqs/{body["id"]}/pdf/', **self.admin_headers)
        self.assertEqual(again.status_code, 200)
        RFQ.objects.get(id=body['id']).refresh_from_db()
        self.assertEqual(RFQ.objects.get(id=body['id']).rfq_no, body['quotation_no'])

    def test_non_admin_cannot_create_a_manual_rfq(self):
        _login_as(self.client, 'buyer')
        response = self.client.post(
            f'/api/pr/{self.pr.id}/manual-rfq/',
            data=json.dumps({'manual_supplier_name': 'X', 'mode_of_procurement': 'Shopping'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(RFQ.objects.count(), 0)

    def test_name_is_required(self):
        self.assertEqual(self._create(name='   ').status_code, 400)

    def test_quotation_basis_line_is_stored_and_defaults_to_lot(self):
        line = self._create(name='Line Co', quotation_basis='line').json()
        self.assertEqual(RFQ.objects.get(id=line['id']).quotation_basis, 'LINE')
        lot = self._create(name='Default Co').json()
        self.assertEqual(RFQ.objects.get(id=lot['id']).quotation_basis, 'LOT')

    def test_completed_rfq_upload_keeps_number_and_name(self):
        body = self._create().json()
        upload = self.client.post(
            f'/api/manual-rfqs/{body["id"]}/completed/',
            data={'file': SimpleUploadedFile('completed.pdf', _PDF_BYTES, content_type='application/pdf')},
            format='multipart', **self.admin_headers,
        )
        self.assertEqual(upload.status_code, 200)
        rfq = RFQ.objects.get(id=body['id'])
        self.assertTrue(rfq.submitted_pdf)
        self.assertTrue(rfq.pdf_file)  # generated RFQ untouched
        self.assertEqual(rfq.rfq_no, body['quotation_no'])
        self.assertEqual(rfq.manual_supplier_name, "Juan's Aircon Services")

    def test_completed_rfq_upload_rejects_non_pdf(self):
        body = self._create().json()
        upload = self.client.post(
            f'/api/manual-rfqs/{body["id"]}/completed/',
            data={'file': SimpleUploadedFile('c.jpg', _JPG_BYTES, content_type='image/jpeg')},
            format='multipart', **self.admin_headers,
        )
        self.assertEqual(upload.status_code, 400)

    def test_manual_rfqs_list_and_search(self):
        self._create(name="Juan's Aircon Services")
        self._create(name='Metro HVAC')
        listing = self.client.get('/api/manual-rfqs/', **self.admin_headers).json()['rfqs']
        self.assertEqual(len(listing), 2)
        found = self.client.get('/api/manual-rfqs/?search=juan', **self.admin_headers).json()['rfqs']
        self.assertEqual([r['manual_supplier_name'] for r in found], ["Juan's Aircon Services"])

    def test_manual_supplier_never_appears_in_category_matching(self):
        self._create()
        match = self.client.get(f'/api/pr/{self.pr.id}/supplier-match/').json()
        names = [s['company_name'] for group in match['groups'] for s in group['suppliers']]
        self.assertNotIn("Juan's Aircon Services", names)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_manual_and_registered_rfqs_share_one_quotation_sequence(self):
        category = Category.objects.create(name='Aircon Q')
        self.pr.category = 'Aircon Q'
        self.pr.save(update_fields=['category'])
        PurchaseRequestItem.objects.filter(purchase_request=self.pr).update(category='Aircon Q')
        supplier = Supplier.objects.create(company_name='Reg Co', email='reg@example.com', status='Approved')
        SupplierCategory.objects.create(supplier=supplier, category=category)

        def seq(value):
            return int(value.split('-')[2])

        a = self._create(name='Manual A').json()['quotation_no']

        sent = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': supplier.id, 'mode_of_procurement': 'Shopping',
                             'send': True, 'generate_pdf': True}),
            content_type='application/json', **self.admin_headers,
        )
        self.assertEqual(sent.status_code, 201, sent.content)
        b = sent.json()['quotation_no']

        c = self._create(name='Manual B').json()['quotation_no']

        # Continuous, in issue order, no gaps or repeats.
        self.assertEqual([seq(b), seq(c)], [seq(a) + 1, seq(a) + 2])

        # Re-sending the registered RFQ keeps its number.
        resend = self.client.patch(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': supplier.id, 'rfq_id': sent.json()['id'],
                             'mode_of_procurement': 'Shopping', 'send': True, 'generate_pdf': True}),
            content_type='application/json', **self.admin_headers,
        )
        self.assertEqual(resend.json()['quotation_no'], b)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_manual_rfq_number_continues_after_registered_rfqs(self):
        """RFQ-2026-0001, RFQ-2026-0002 registered -> manual RFQ is RFQ-2026-0003."""
        category = Category.objects.create(name='Aircon P')
        self.pr.category = 'Aircon P'
        self.pr.save(update_fields=['category'])
        PurchaseRequestItem.objects.filter(purchase_request=self.pr).update(category='Aircon P')

        def seq(value):
            return int(value.split('-')[2])

        registered = []
        for i in range(2):
            supplier = Supplier.objects.create(
                company_name=f'Reg {i}', email=f'reg{i}@example.com', status='Approved',
            )
            SupplierCategory.objects.create(supplier=supplier, category=category)
            r = self.client.post(
                f'/api/pr/{self.pr.id}/rfq/',
                data=json.dumps({'supplier_id': supplier.id, 'mode_of_procurement': 'Shopping',
                                 'send': True, 'generate_pdf': True}),
                content_type='application/json', **self.admin_headers,
            )
            self.assertEqual(r.status_code, 201, r.content)
            registered.append(r.json()['quotation_no'])

        manual = self._create(name='Manual After').json()['quotation_no']

        self.assertRegex(manual, r'^RFQ-\d{4}-\d{4}$')
        self.assertEqual(seq(manual), seq(registered[1]) + 1)
        self.assertEqual(seq(registered[1]), seq(registered[0]) + 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_deleted_draft_does_not_cause_a_duplicate_number(self):
        """The next number follows the highest generated, not a live row count."""
        first = self._create(name='First').json()['quotation_no']
        second = self._create(name='Second').json()['quotation_no']
        RFQ.objects.filter(rfq_no=first).delete()

        third = self._create(name='Third').json()['quotation_no']
        self.assertNotIn(third, {first, second})
        self.assertEqual(int(third.split('-')[2]), int(second.split('-')[2]) + 1)


class RFQManagementGroupingTests(TestCase):
    """PR-centered RFQ Management view: GET /api/rfqs/responses/?group_by=pr."""

    def setUp(self):
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU Tuburan Campus', pr_no='2026-08-001',
            category='Airconditioning and Airconditioning Systems', office_section='Campus Admin',
        )
        PurchaseRequestItem.objects.create(purchase_request=self.pr, item_description='Aircon unit',
                                           quantity=1, unit='unit', category=self.pr.category)
        self.supplier_a = Supplier.objects.create(company_name='CoolTech Climate Solutions',
                                                  email='a@example.com', status='Approved')
        self.supplier_b = Supplier.objects.create(company_name='ABC HVAC Solutions',
                                                  email='b@example.com', status='Approved')
        self.supplier_c = Supplier.objects.create(company_name='Metro Cooling Services',
                                                  email='c@example.com', status='Approved')
        _login_as(self.client, 'admin')

    def _rfq(self, supplier, no, status=RFQ.STATUS_SENT, submitted=False):
        rfq = RFQ.objects.create(
            rfq_no=no, purchase_request=self.pr, supplier=supplier,
            subject='RFQ', message='Please quote', status=status,
            pdf_file=f'rfq/{no}.pdf', sent_at=timezone.now(),
        )
        if submitted:
            rfq.submitted_pdf = f'supplier_uploads/{no}-completed.pdf'
            rfq.submitted_at = timezone.now()
            rfq.status = RFQ.STATUS_QUOTATION_RECEIVED
            rfq.save(update_fields=['submitted_pdf', 'submitted_at', 'status'])
        return rfq

    def _groups(self, query=''):
        response = self.client.get(f'/api/rfqs/responses/?group_by=pr{query}')
        self.assertEqual(response.status_code, 200)
        return response.json()['purchase_requests']

    def test_one_pr_one_rfq(self):
        self._rfq(self.supplier_a, 'RFQ-2026-0001')
        groups = self._groups()
        self.assertEqual(len(groups), 1)
        summary = groups[0]['rfq_summary']
        self.assertEqual((summary['sent'], summary['responses_received'], summary['awaiting_response']), (1, 0, 1))
        self.assertEqual(summary['status'], 'awaiting_responses')
        self.assertEqual(groups[0]['purchase_request']['pr_no'], '2026-08-001')

    def test_multiple_rfqs_grouped_under_one_pr(self):
        self._rfq(self.supplier_a, 'RFQ-2026-0001')
        self._rfq(self.supplier_b, 'RFQ-2026-0002')
        self._rfq(self.supplier_c, 'RFQ-2026-0003')
        groups = self._groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['rfqs']), 3)
        self.assertEqual(groups[0]['rfq_summary']['sent'], 3)

    def test_partial_responses(self):
        self._rfq(self.supplier_a, 'RFQ-2026-0001', submitted=True)
        self._rfq(self.supplier_b, 'RFQ-2026-0002', submitted=True)
        self._rfq(self.supplier_c, 'RFQ-2026-0003')
        summary = self._groups()[0]['rfq_summary']
        self.assertEqual((summary['sent'], summary['responses_received'], summary['awaiting_response']), (3, 2, 1))
        self.assertEqual(summary['status'], 'responses_in_progress')

    def test_all_responses_received(self):
        self._rfq(self.supplier_a, 'RFQ-2026-0001', submitted=True)
        self._rfq(self.supplier_b, 'RFQ-2026-0002', submitted=True)
        self._rfq(self.supplier_c, 'RFQ-2026-0003', submitted=True)
        summary = self._groups()[0]['rfq_summary']
        self.assertEqual((summary['sent'], summary['responses_received'], summary['awaiting_response']), (3, 3, 0))
        self.assertEqual(summary['status'], 'all_responses_received')

    def test_draft_rfqs_are_excluded(self):
        self._rfq(self.supplier_a, 'RFQ-2026-0001')
        self._rfq(self.supplier_b, 'RFQ-2026-0002', status=RFQ.STATUS_DRAFT)
        groups = self._groups()
        self.assertEqual(groups[0]['rfq_summary']['sent'], 1)
        self.assertEqual({r['rfq_no'] for r in groups[0]['rfqs']}, {'RFQ-2026-0001'})

    def test_search_by_pr_rfq_and_supplier(self):
        other_pr = PurchaseRequest.objects.create(entity_name='Other', pr_no='2026-08-002', category='Office Supplies')
        self._rfq(self.supplier_a, 'RFQ-2026-0001')
        RFQ.objects.create(rfq_no='RFQ-2026-0009', purchase_request=other_pr, supplier=self.supplier_b,
                           subject='RFQ', message='m', status=RFQ.STATUS_SENT, sent_at=timezone.now())

        self.assertEqual({g['purchase_request']['pr_no'] for g in self._groups('&search=2026-08-001')}, {'2026-08-001'})
        self.assertEqual({g['purchase_request']['pr_no'] for g in self._groups('&search=RFQ-2026-0009')}, {'2026-08-002'})
        self.assertEqual({g['purchase_request']['pr_no'] for g in self._groups('&search=CoolTech')}, {'2026-08-001'})

    def test_documents_stay_separate_after_submission(self):
        rfq = self._rfq(self.supplier_a, 'RFQ-2026-0001', submitted=True)
        payload = self._groups()[0]['rfqs'][0]
        self.assertTrue(payload['generated_pdf_url'])
        self.assertTrue(payload['submitted_pdf_url'])
        self.assertNotEqual(payload['generated_pdf_url'], payload['submitted_pdf_url'])
        rfq.refresh_from_db()
        self.assertEqual(rfq.pdf_file, 'rfq/RFQ-2026-0001.pdf')

    def test_grouped_view_requires_admin(self):
        self._rfq(self.supplier_a, 'RFQ-2026-0001')
        _login_as(self.client, 'supplier')
        forbidden = self.client.get('/api/rfqs/responses/?group_by=pr')
        self.assertEqual(forbidden.status_code, 403)

    def test_flat_response_is_unchanged_without_group_by(self):
        self._rfq(self.supplier_a, 'RFQ-2026-0001')
        response = self.client.get('/api/rfqs/responses/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('rfqs', body)
        self.assertNotIn('purchase_requests', body)


class RFQItemTableRenderingTests(TestCase):
    """The generated RFQ item table is built from PurchaseRequestItem rows and
    keeps long descriptions readable (no font shrinking)."""

    LONG_DESCRIPTION = (
        'Supply and Delivery of 4.0HP FLOOR STANDING, INVERTER TYPE AIR CONDITIONING UNIT '
        'including labor charges for the installation, testing and commissioning:\n\n'
        'Capacity: 3 Tons of Refrigeration (3TR) / 4.0 HP\n'
        'Cooling Capacity: Approx. 36,000 BTU/h\n'
        'Refrigerant: R32\n'
        'Power Supply: 220-240V / 60Hz / 1 Phase\n'
        'Noise Level: not more than 55 dB(A)\n'
        'Inclusions: complete set of mounting brackets, interconnecting pipes and wiring\n'
        'Warranty: minimum of one (1) year on parts and services and five (5) years on the compressor\n'
    ) * 2

    def setUp(self):
        self.pr = PurchaseRequest.objects.create(
            entity_name='CTU Tuburan Campus', pr_no='2026-08-010',
            category='Airconditioning and Airconditioning Systems', purpose='Campus cooling',
            grand_total=250000,
        )
        self.supplier = Supplier.objects.create(company_name='CoolTech Climate Solutions',
                                                email='cooltech@example.com', status='Approved')

    def _rfq(self):
        return RFQ.objects.create(
            rfq_no='RFQ-2026-0010', purchase_request=self.pr, supplier=self.supplier,
            subject='RFQ', message='Please quote', status=RFQ.STATUS_DRAFT,
            mode_of_procurement='Small Value Procurement',
        )

    def _pdf_lines(self, path):
        """[(text, min_font_size)] for every visible text line in the PDF."""
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTChar, LTTextContainer

        lines = []
        for page in extract_pages(str(path)):
            for element in page:
                if not isinstance(element, LTTextContainer):
                    continue
                for text_line in element:
                    chars = [c for c in getattr(text_line, '_objs', []) if isinstance(c, LTChar)]
                    text = ''.join(c.get_text() for c in chars).strip()
                    if text:
                        lines.append((text, min(round(c.size, 1) for c in chars)))
        return lines

    def test_quantity_formatting_trims_trailing_zeros(self):
        from api.rfq.services.rfq_generator import _format_quantity
        from decimal import Decimal
        self.assertEqual(_format_quantity(Decimal('1.00')), '1')
        self.assertEqual(_format_quantity(Decimal('2.50')), '2.5')
        self.assertEqual(_format_quantity(Decimal('10.00')), '10')
        self.assertEqual(_format_quantity(Decimal('0')), '0')

    def test_each_pr_item_becomes_one_row_with_sequential_numbering(self):
        PurchaseRequestItem.objects.create(purchase_request=self.pr, item_description='Ballpoint pen, black', quantity=50, unit='box')
        PurchaseRequestItem.objects.create(purchase_request=self.pr, item_description='Bond paper A4\nsubstance 20', quantity=100, unit='ream')
        PurchaseRequestItem.objects.create(purchase_request=self.pr, item_description=self.LONG_DESCRIPTION, quantity=4, unit='unit')

        from api.rfq.services.rfq_generator import generate_rfq_pdf
        _, path = generate_rfq_pdf(self._rfq())
        lines = self._pdf_lines(path)
        text = '\n'.join(t for t, _ in lines)

        # One row per DB item with its structured quantity / unit.
        self.assertIn('Ballpoint pen, black', text)
        self.assertIn('50/box', text)
        self.assertIn('100/ream', text)
        self.assertIn('4/unit', text)
        # Multiline description keeps its own line break, not a new item.
        self.assertIn('Bond paper A4', text)
        self.assertIn('substance 20', text)
        # Item numbers come from the PR item sequence (1, 2, 3) and render as
        # their own short cell, never derived from OCR line numbers.
        self.assertEqual(
            sorted({t for t, _ in lines if t in {'1', '2', '3'}}),
            ['1', '2', '3'],
        )

    def test_long_description_is_rendered_in_full_and_stays_readable(self):
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description=self.LONG_DESCRIPTION, quantity=4, unit='unit',
        )
        from api.rfq.services.rfq_generator import generate_rfq_pdf
        _, path = generate_rfq_pdf(self._rfq())
        lines = self._pdf_lines(path)
        text = '\n'.join(t for t, _ in lines)

        # Full technical spec present - nothing truncated.
        for fragment in ('FLOOR STANDING', 'Refrigerant: R32', '220-240V / 60Hz / 1 Phase',
                         'five (5) years on the compressor'):
            self.assertIn(fragment, text)

        # No microscopic text: every line that carries description wording is >= 8pt.
        description_sizes = [
            size for t, size in lines
            if any(k in t for k in ('Refrigerant', 'Cooling Capacity', 'Power Supply', 'Warranty', 'FLOOR STANDING'))
        ]
        self.assertTrue(description_sizes)
        self.assertGreaterEqual(min(description_sizes), 8.0)

    def test_supplier_fill_in_columns_are_left_blank(self):
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Aircon unit', quantity=1, unit='unit',
            unit_cost=45000, total_cost=45000,
        )
        from api.rfq.services.rfq_generator import generate_rfq_pdf
        _, path = generate_rfq_pdf(self._rfq())
        text = '\n'.join(t for t, _ in self._pdf_lines(path))
        # PR unit / total cost must never be pre-filled as a quotation value.
        self.assertNotIn('45000', text.replace(',', ''))
        self.assertNotIn('45,000', text)

    def test_generated_pdf_includes_every_pr_item_even_outside_the_rfq_category(self):
        # A mixed-category PR: this RFQ is linked (via RFQItem) to only the
        # aircon item, but the generated document must still list the
        # janitorial item too - the supplier can see the whole PR and just
        # leaves the unit price blank for anything outside their category.
        aircon_item = PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Split-type aircon unit',
            quantity=1, unit='unit', category='Airconditioning and Airconditioning Systems',
        )
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Industrial floor mop',
            quantity=5, unit='pc', category='Janitorial Supplies',
        )
        rfq = self._rfq()
        RFQItem.objects.create(rfq=rfq, purchase_request_item=aircon_item)

        from api.rfq.services.rfq_generator import generate_rfq_pdf
        _, path = generate_rfq_pdf(rfq)
        text = '\n'.join(t for t, _ in self._pdf_lines(path))

        self.assertIn('Split-type aircon unit', text)
        self.assertIn('Industrial floor mop', text)

    def test_supplier_identity_fields_are_blank_on_generated_rfq(self):
        # The supplier writes Company Name / Address / TIN by hand on the printed
        # copy - they must never be pre-filled from the Supplier record.
        self.supplier.business_address = '123 Real Street, Cebu City'
        self.supplier.tin = '123-456-789-000'
        self.supplier.save(update_fields=['business_address', 'tin'])
        PurchaseRequestItem.objects.create(
            purchase_request=self.pr, item_description='Aircon unit', quantity=1, unit='unit',
        )
        from api.rfq.services.rfq_generator import generate_rfq_pdf
        _, path = generate_rfq_pdf(self._rfq())
        text = '\n'.join(t for t, _ in self._pdf_lines(path))

        self.assertIn('Company Name:', text)
        self.assertIn('Address:', text)
        self.assertIn('TIN:', text)
        self.assertNotIn('CoolTech Climate Solutions', text)
        self.assertNotIn('123 Real Street', text)
        self.assertNotIn('123-456-789-000', text)

    def test_template_converts_description_newlines_to_breaks(self):
        from django.template.loader import render_to_string
        html = render_to_string('rfq/rfq.html', {
            'rfq_no': 'R', 'pr_no': 'P', 'pr_date': '', 'quotation_no': '',
            'mode_of_procurement': 'Shopping', 'quotation_basis': 'LOT', 'supplier': {},
            'abc': 'Php0.00', 'additional_notes': '',
            'items': [{'index': 1, 'item_description': 'Line one\nLine two',
                       'quantity': 1, 'quantity_display': '1', 'unit': 'lot', 'stock_property_no': ''}],
            'signatory_name': 'X', 'signatory_role': 'Y', 'signature_url': '',
        })
        self.assertIn('Line one<br>Line two', html.replace('<br />', '<br>'))


class BuyerLiveStatusTests(TestCase):
    """End-user Live Status: GET /api/pr/list/?submitted_by= exposes a
    high-level, supplier-free procurement stage per Purchase Request."""

    def _pr(self, no, status, submitted_by='buyer1', **kwargs):
        return PurchaseRequest.objects.create(
            entity_name='CTU Tuburan Campus', pr_no=no, status=status,
            office_section='General Services Office', submitted_by=submitted_by,
            date=date(2026, 9, 7), grand_total=478500, **kwargs,
        )

    def _rfq(self, pr, no, sent=False, responded=False):
        rfq = RFQ.objects.create(
            rfq_no=no, purchase_request=pr,
            supplier=Supplier.objects.create(company_name=f'Supplier {no}', status='Approved'),
            subject='RFQ', message='m',
            status=RFQ.STATUS_SENT if sent or responded else RFQ.STATUS_DRAFT,
            sent_at=timezone.now() if sent or responded else None,
        )
        if responded:
            rfq.submitted_pdf = f'uploads/{no}.pdf'
            rfq.submitted_at = timezone.now()
            rfq.status = RFQ.STATUS_QUOTATION_RECEIVED
            rfq.save(update_fields=['submitted_pdf', 'submitted_at', 'status'])
        return rfq

    def _record(self, pr, submitted_by='buyer1'):
        response = self.client.get(f'/api/pr/list/?submitted_by={submitted_by}')
        self.assertEqual(response.status_code, 200)
        return next(r for r in response.json() if r['id'] == pr.id)

    def test_stage_submitted(self):
        pr = self._pr('2026-09-001', PurchaseRequest.STATUS_UPLOADED)
        self.assertEqual(self._record(pr)['display_stage'], 'submitted')

    def test_stage_under_bac_review(self):
        pr = self._pr('2026-09-002', PurchaseRequest.STATUS_IN_REVIEW)
        rec = self._record(pr)
        self.assertEqual(rec['display_stage'], 'under_review')
        self.assertEqual(rec['display_status'], 'Under BAC Review')

    def test_stage_supplier_matching(self):
        pr = self._pr('2026-09-003', PurchaseRequest.STATUS_MATCHED)
        PurchaseRequestItem.objects.create(purchase_request=pr, item_description='x', category='Cat')
        self._rfq(pr, 'RFQ-1')  # a draft RFQ must not advance the stage
        self.assertEqual(self._record(pr)['display_stage'], 'supplier_matching')

    def test_stage_rfq_sent(self):
        pr = self._pr('2026-09-004', PurchaseRequest.STATUS_MATCHED)
        PurchaseRequestItem.objects.create(purchase_request=pr, item_description='x', category='Cat')
        self._rfq(pr, 'RFQ-1', sent=True)
        self._rfq(pr, 'RFQ-2', sent=True)
        rec = self._record(pr)
        self.assertEqual(rec['display_stage'], 'rfq_sent')
        self.assertEqual((rec['rfq_sent_count'], rec['rfq_response_count']), (2, 0))
        self.assertTrue(rec['stage_timestamps']['rfq_sent'])

    def test_stage_supplier_response(self):
        pr = self._pr('2026-09-005', PurchaseRequest.STATUS_MATCHED)
        PurchaseRequestItem.objects.create(purchase_request=pr, item_description='x', category='Cat')
        self._rfq(pr, 'RFQ-1', responded=True)
        self._rfq(pr, 'RFQ-2', sent=True)
        rec = self._record(pr)
        self.assertEqual(rec['display_stage'], 'supplier_response')
        self.assertEqual((rec['rfq_sent_count'], rec['rfq_response_count']), (2, 1))
        self.assertTrue(rec['stage_timestamps']['supplier_response'])

    def test_stage_completed(self):
        pr = self._pr('2026-09-006', PurchaseRequest.STATUS_APPROVED)
        self.assertEqual(self._record(pr)['display_stage'], 'completed')

    def test_stage_rejected(self):
        pr = self._pr('2026-09-007', PurchaseRequest.STATUS_REJECTED)
        rec = self._record(pr)
        self.assertEqual(rec['display_stage'], 'rejected')
        self.assertEqual(rec['display_status'], 'Rejected')

    def test_multiple_prs_each_keep_their_own_stage(self):
        a = self._pr('2026-09-010', PurchaseRequest.STATUS_UPLOADED)
        b = self._pr('2026-09-011', PurchaseRequest.STATUS_MATCHED)
        PurchaseRequestItem.objects.create(purchase_request=b, item_description='x', category='Cat')
        self._rfq(b, 'RFQ-B', sent=True)
        stages = {r['pr_no']: r['display_stage'] for r in self.client.get('/api/pr/list/?submitted_by=buyer1').json()}
        self.assertEqual(stages['2026-09-010'], 'submitted')
        self.assertEqual(stages['2026-09-011'], 'rfq_sent')

    def test_response_never_exposes_supplier_information(self):
        pr = self._pr('2026-09-020', PurchaseRequest.STATUS_MATCHED)
        PurchaseRequestItem.objects.create(purchase_request=pr, item_description='x', category='Cat')
        rfq = self._rfq(pr, 'RFQ-SECRET-2026', responded=True)
        Quotation.objects.create(supplier=rfq.supplier, purchase_request=pr, rfq=rfq, quoted_amount=987654)
        record = self._record(pr)
        blob = json.dumps(record)
        # No supplier identity, RFQ number, quotation figure, or match score.
        for leak in ('SecretSupplier', rfq.supplier.company_name, 'RFQ-SECRET-2026',
                     '987654', 'match_score', 'quoted_amount', 'compliance'):
            self.assertNotIn(leak, blob)
        # Only the high-level stage vocabulary is present.
        self.assertNotIn('rfq_no', record)
        self.assertNotIn('supplier', record)  # no per-supplier key on the record

    def test_pr_date_is_returned_for_the_timeline(self):
        pr = self._pr('2026-09-030', PurchaseRequest.STATUS_IN_REVIEW)
        self.assertEqual(self._record(pr)['date'], '2026-09-07')

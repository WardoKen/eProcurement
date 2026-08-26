import json
from datetime import date
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from api.models import Category, Notification, PurchaseRequest, PurchaseRequestItem, Quotation, RFQ, Role, Supplier, SupplierCategory, User
from api.supplier_registration import get_required_business_document_key, validate_supplier_payload
from api.views import hash_password


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

        png_file = SimpleUploadedFile('permit.png', b'valid', content_type='image/png')
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
                'mayor_permit': SimpleUploadedFile('mayor.pdf', b'pdf', content_type='application/pdf'),
                'business_permit': SimpleUploadedFile('business.pdf', b'pdf', content_type='application/pdf'),
                'philgeps_registration': SimpleUploadedFile('philgeps.pdf', b'pdf', content_type='application/pdf'),
                'bir_registration': SimpleUploadedFile('bir.pdf', b'pdf', content_type='application/pdf'),
                'tax_clearance': SimpleUploadedFile('tax.pdf', b'pdf', content_type='application/pdf'),
                'dti_registration': SimpleUploadedFile('dti.pdf', b'pdf', content_type='application/pdf'),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username='supplierdemo', role=role).exists())
        supplier = Supplier.objects.get(email='jane@example.com')
        self.assertTrue(SupplierCategory.objects.filter(supplier=supplier, category=category).exists())

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
            email='acme@example.com',
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

        response = self.client.patch(
            f'/api/suppliers/{supplier.id}/status/',
            data=json.dumps({'status': 'For Compliance', 'remarks': 'Please upload a clearer PhilGEPS certificate.'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        supplier.refresh_from_db()
        self.assertEqual(supplier.status, 'For Compliance')


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

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sending_rfq_creates_notification_and_email(self):
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': self.supplier.id, 'send': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], RFQ.STATUS_SENT)
        self.assertEqual(Notification.objects.filter(supplier=self.supplier, notification_type=Notification.TYPE_RFQ_RECEIVED).count(), 1)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.supplier.email])

    def test_rfq_rejects_supplier_without_matching_category(self):
        other_supplier = Supplier.objects.create(company_name='Other Supplier', email='other@example.com', status='Approved')
        response = self.client.post(
            f'/api/pr/{self.pr.id}/rfq/',
            data=json.dumps({'supplier_id': other_supplier.id}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('eligible', response.json()['message'])

    def test_quotation_can_reference_sent_rfq(self):
        rfq = RFQ.objects.create(
            rfq_no='RFQ-2026-0001', purchase_request=self.pr, supplier=self.supplier,
            subject='RFQ', message='Please quote', status=RFQ.STATUS_SENT,
        )
        response = self.client.post(
            f'/api/suppliers/{self.supplier.id}/quotations/',
            data=json.dumps({'purchase_request_id': self.pr.id, 'rfq_id': rfq.id, 'quoted_amount': 1000}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Quotation.objects.get(id=response.json()['quotation_id']).rfq_id, rfq.id)
        rfq.refresh_from_db()
        self.assertEqual(rfq.status, RFQ.STATUS_QUOTATION_RECEIVED)


class PurchaseRequestNumberTests(TestCase):
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
    def test_ignores_other_months_and_invalid_numbers(self, _localdate):
        PurchaseRequest.objects.create(entity_name='July', pr_no='2026-07-099')
        PurchaseRequest.objects.create(entity_name='Other year', pr_no='2025-12-999')
        PurchaseRequest.objects.create(entity_name='Current', pr_no='2026-08-005')
        PurchaseRequest.objects.create(entity_name='Invalid', pr_no='2026-08-1000')

        response = self.create_pr()

        self.assertEqual(response.json()['pr_no'], '2026-08-006')

    @patch('api.views.timezone.localdate', return_value=date(2026, 9, 1))
    def test_resets_for_new_month(self, _localdate):
        PurchaseRequest.objects.create(entity_name='August', pr_no='2026-08-051')

        response = self.create_pr()

        self.assertEqual(response.json()['pr_no'], '2026-09-001')

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
        self.assertEqual(pr.status, 'matched')
        self.assertEqual(pr.pr_no, '2026-08-001')


class SupplierMatchingTests(TestCase):
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
        category = Category.objects.create(name='Airconditioning and Airconditioning Systems')
        pr = PurchaseRequest.objects.create(entity_name='Aircon Entity', pr_no='2026-08-003')
        PurchaseRequestItem.objects.create(
            purchase_request=pr,
            item_description='Aircon unit',
            category=category.name,
        )
        matching_supplier = Supplier.objects.create(company_name='Matching Supplier')
        unrelated_supplier = Supplier.objects.create(company_name='Unrelated Supplier')
        SupplierCategory.objects.create(supplier=matching_supplier, category=category)

        response = self.client.get(f'/api/pr/{pr.id}/supplier-match/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['company_name'] for item in response.json()[0]['suppliers']], [matching_supplier.company_name])
        self.assertNotIn(unrelated_supplier.company_name, [item['company_name'] for item in response.json()[0]['suppliers']])

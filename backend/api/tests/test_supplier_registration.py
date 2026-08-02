import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from api.models import Role, Supplier, User
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
                'categories': 'Office Supplies',
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

    def test_supplier_login_response_includes_linked_supplier_status(self):
        role = Role.objects.create(name='supplier')
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

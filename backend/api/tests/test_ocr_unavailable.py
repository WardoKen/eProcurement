"""Coverage for AWS Textract being missing or misconfigured.

Two distinct failure modes, both of which used to surface badly:

1. No AWS region/credentials at all. The Textract client was built at import
   time in ``api.views``, so boto3's NoRegionError took down *every* endpoint
   before Django finished starting - not just PR upload.
2. Credentials present but rejected (expired token, no Textract permission).
   The client swallowed those errors into an empty document, so the upload
   endpoint blamed the user's file ("does not appear to be a Purchase
   Request", 422) for what is really a server outage.

Both now produce a 503 with a machine-readable ``error_code`` and the uploaded
file is kept, so the Buyer can still enter the PR manually against it.
"""
import os
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from api.models import Role, User
from ocr.ocr_service import OCRUnavailableError, TextractOCRService


def _min_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


_PDF_BYTES = _min_pdf_bytes()


def _login_as_buyer(client):
    role = Role.objects.get_or_create(name='buyer')[0]
    user = User.objects.create(username='ocr-buyer', password_hash='x', role=role, is_active=True)
    session = client.session
    session['user_id'] = user.id
    session['role'] = 'buyer'
    session['username'] = user.username
    session.save()
    return user


class AppBootsWithoutAwsConfigTests(TestCase):
    """Regression: a missing AWS region must not break app startup."""

    def test_views_module_imports_with_no_aws_region(self):
        import importlib

        import api.views

        cleared = {key: os.environ.pop(key, None) for key in
                   ('AWS_REGION', 'AWS_DEFAULT_REGION', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY')}
        try:
            reloaded = importlib.reload(api.views)
            self.assertTrue(hasattr(reloaded, 'get_ocr_service'))
        finally:
            for key, value in cleared.items():
                if value is not None:
                    os.environ[key] = value
            importlib.reload(api.views)

    def test_management_check_passes_with_no_aws_region(self):
        """End-to-end boot check in a clean interpreter.

        Runs in a subprocess with python-dotenv neutralized: the repo-root
        .env supplies AWS_REGION, so clearing os.environ in-process alone
        would not actually simulate an unconfigured server.
        """
        import subprocess
        import sys
        from pathlib import Path

        backend_root = Path(__file__).resolve().parent.parent.parent
        script = (
            "import os, dotenv;"
            "dotenv.load_dotenv = lambda *a, **k: False;"
            "[os.environ.pop(k, None) for k in "
            "('AWS_REGION','AWS_DEFAULT_REGION','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY')];"
            "os.environ['DJANGO_SETTINGS_MODULE']='eprocure.settings';"
            "import django; django.setup();"
            "[os.environ.pop(k, None) for k in ('AWS_REGION','AWS_DEFAULT_REGION')];"
            "from django.core.management import call_command; call_command('check')"
        )
        result = subprocess.run(
            [sys.executable, '-c', script],
            cwd=str(backend_root), capture_output=True, text=True, timeout=180,
        )

        self.assertEqual(result.returncode, 0, msg=f'boot failed:\n{result.stderr}')
        self.assertNotIn('NoRegionError', result.stderr)

    def test_service_construction_without_region_raises_typed_error(self):
        cleared = {key: os.environ.pop(key, None) for key in ('AWS_REGION', 'AWS_DEFAULT_REGION')}
        try:
            with patch('ocr.ocr_service.boto3.client', side_effect=NoRegionError()):
                with self.assertRaises(OCRUnavailableError) as ctx:
                    TextractOCRService(language='en')
            self.assertFalse(ctx.exception.configured)
        finally:
            for key, value in cleared.items():
                if value is not None:
                    os.environ[key] = value


class UploadEndpointOcrOutageTests(TestCase):
    """The upload endpoint reports an OCR outage as 503, never 500 or 422."""

    def setUp(self):
        _login_as_buyer(self.client)

    def _upload(self):
        return self.client.post('/api/upload/', {'file': SimpleUploadedFile('pr.pdf', _PDF_BYTES)})

    def test_client_construction_failure_returns_503_not_configured(self):
        with patch('api.views.get_ocr_service',
                   side_effect=OCRUnavailableError('no region', configured=False)):
            response = self._upload()

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertFalse(body['success'])
        self.assertEqual(body['error_code'], 'ocr_not_configured')
        self.assertFalse(body['ocr_available'])
        self.assertIn('not configured', body['message'])

    def test_raw_botocore_error_from_process_file_is_still_503(self):
        """Safety net: an untranslated botocore error must not become a 500."""
        service = MagicMock()
        service.process_file.side_effect = NoCredentialsError()
        with patch('api.views.get_ocr_service', return_value=service):
            response = self._upload()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error_code'], 'ocr_not_configured')

    def test_rejected_credentials_return_503_request_failed(self):
        service = MagicMock()
        service.process_file.side_effect = OCRUnavailableError(
            'Textract rejected the request (ExpiredTokenException)', configured=True
        )
        with patch('api.views.get_ocr_service', return_value=service):
            response = self._upload()

        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body['error_code'], 'ocr_request_failed')
        self.assertNotIn('ExpiredTokenException', body['message'])
        self.assertNotIn('AWS', body['message'])

    def test_uploaded_document_is_preserved_for_manual_entry(self):
        """The product decision: the file survives an OCR outage.

        ``/api/upload/`` creates no PurchaseRequest row (``create_pr`` does),
        so there is no record to flag - what must not be lost is the stored
        document, returned here so the Buyer can key the PR in by hand.
        """
        from django.conf import settings as dj_settings
        from pathlib import Path

        service = MagicMock()
        service.process_file.side_effect = OCRUnavailableError('no region', configured=False)
        with patch('api.views.get_ocr_service', return_value=service):
            response = self._upload()

        body = response.json()
        self.assertEqual(response.status_code, 503)
        self.assertTrue(body['filename'])
        self.assertIn('/uploads/', body['fileUrl'])
        saved = Path(dj_settings.BASE_DIR) / 'uploads' / body['filename']
        self.assertTrue(saved.is_file(), 'uploaded document must be kept when OCR is unavailable')
        saved.unlink(missing_ok=True)

    def test_pr_scan_reports_outage_as_503_not_unparseable_422(self):
        service = MagicMock()
        service.process_file.side_effect = OCRUnavailableError('no region', configured=False)
        with patch('api.views.get_ocr_service', return_value=service):
            response = self.client.post('/api/pr/scan/', {'file': SimpleUploadedFile('pr.pdf', _PDF_BYTES)})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error_code'], 'ocr_not_configured')


class TextractErrorTranslationTests(TestCase):
    """Auth/config faults escape the client; document faults keep falling back."""

    def _service(self):
        with patch('ocr.ocr_service.boto3.client') as client:
            service = TextractOCRService(language='en')
        service._client = MagicMock()
        return service

    def _client_error(self, code):
        return ClientError({'Error': {'Code': code, 'Message': 'denied'}}, 'AnalyzeDocument')

    def test_access_denied_raises_configured_outage(self):
        service = self._service()
        service._client.analyze_document.side_effect = self._client_error('AccessDeniedException')

        with self.assertRaises(OCRUnavailableError) as ctx:
            service._analyze_document_bytes(b'bytes')

        self.assertTrue(ctx.exception.configured)
        service._client.detect_document_text.assert_not_called()

    def test_expired_token_raises_configured_outage(self):
        service = self._service()
        service._client.analyze_document.side_effect = self._client_error('ExpiredTokenException')

        with self.assertRaises(OCRUnavailableError):
            service._analyze_document_bytes(b'bytes')

    def test_missing_credentials_raises_not_configured_outage(self):
        service = self._service()
        service._client.analyze_document.side_effect = NoCredentialsError()

        with self.assertRaises(OCRUnavailableError) as ctx:
            service._analyze_document_bytes(b'bytes')

        self.assertFalse(ctx.exception.configured)

    def test_unsupported_document_still_falls_back_to_detect_text(self):
        service = self._service()
        service._client.analyze_document.side_effect = self._client_error('UnsupportedDocumentException')
        service._client.detect_document_text.return_value = {'Blocks': []}

        self.assertEqual(service._analyze_document_bytes(b'bytes'), {'Blocks': []})

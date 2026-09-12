import csv
import hashlib
import json
import re
import secrets
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from io import BytesIO

from django.http import JsonResponse, StreamingHttpResponse
from django.core.mail import EmailMessage
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.template.loader import render_to_string
from django.db import IntegrityError, transaction
from django.db.models import Avg, Case, Count, Exists, IntegerField, Min, OuterRef, Q, Value, When
from django.db.models.functions import TruncMonth
from django.conf import settings
from django.utils.text import slugify
from xhtml2pdf import pisa

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

try:
    from ocr.ocr_service import TextractOCRService
    from ocr.layout_parser import DocumentLayoutParser
    from ocr.purchase_request_parser import parse_purchase_request
    from ocr.form_autofill import FormAutoFillService
    from ocr.validation import ValidationService
    from ocr.debug_utils import write_debug_json
    from ocr import signature_detection
except ImportError:  # pragma: no cover
    from backend.ocr.ocr_service import TextractOCRService
    from backend.ocr.layout_parser import DocumentLayoutParser
    from backend.ocr.purchase_request_parser import parse_purchase_request
    from backend.ocr.form_autofill import FormAutoFillService
    from backend.ocr.validation import ValidationService
    from backend.ocr.debug_utils import write_debug_json
    from backend.ocr import signature_detection

from .models import Role, Supplier, User, SupplierDocument, Category, SupplierCategory
from .models import PurchaseRequest, PurchaseRequestItem, PRNumberSequence, Quotation, Notification, RFQ, RFQItem
from .auth import require_auth
from .file_validation import UploadKind, FileValidationError, validate_upload
from .supplier_registration import (
    REQUIRED_UPLOAD_KEYS,
    OPTIONAL_UPLOAD_KEYS,
    MAX_UPLOAD_SIZE,
    get_required_business_document_key,
    sanitize_text,
    validate_supplier_payload,
    _save_supplier_upload,
)

from api.rfq.services.rfq_generator import generate_rfq_pdf
from api.rfq.procurement_modes import (
    procurement_mode_choices,
    normalize_procurement_mode,
)

UPLOADS_DIR = Path(settings.BASE_DIR) / 'uploads'
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


ocr_service = TextractOCRService(language='en')
layout_parser = DocumentLayoutParser()
auto_fill_service = FormAutoFillService()
validation_service = ValidationService()


def normalize_text(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '')).strip()


# --- Signature-presence validation (uploaded PR) ---------------------------
# The signature check runs once at upload, then the derived regions + result are
# cached in a sidecar file next to the upload so "Recheck Signatures" and the
# Save guard can re-measure the document without re-running OCR/Textract.
SIGNATORY_NAME_FIELDS = {
    signature_detection.REQUESTED_BY: ('requested_by_name', 'requestedBy'),
    signature_detection.FUNDS_AVAILABLE: ('funds_available_name',),
    signature_detection.APPROVED_BY: ('approved_by_name',),
    signature_detection.TWG: ('twg_name',),
}


def _signatory_names(fields: dict) -> dict:
    names = {}
    for key, aliases in SIGNATORY_NAME_FIELDS.items():
        for alias in aliases:
            value = str((fields or {}).get(alias) or '').strip()
            if value:
                names[key] = value
                break
    return names


def _declaration_acknowledged(fields: dict) -> bool:
    """Strict check for the PR Submission Declaration acknowledgement flag.

    Only an explicit boolean ``True`` (or the string ``"true"``) counts -
    ``False`` / missing / ``None`` / anything else is treated as not acknowledged.
    """
    value = (fields or {}).get('declaration_acknowledged')
    if value is None:
        value = (fields or {}).get('declarationAcknowledged')
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == 'true'


def _sigcheck_path(filename: str) -> Path:
    safe = Path(str(filename or '')).name
    return UPLOADS_DIR / f'{safe}.sigcheck.json'


def _write_sigcheck(filename: str, regions: dict, result: dict) -> None:
    if not filename:
        return
    payload = {
        'version': signature_detection.SIDECAR_VERSION,
        'filename': Path(str(filename)).name,
        'generated_at': timezone.now().isoformat(),
        'regions': regions,
        'result': result,
    }
    try:
        with open(_sigcheck_path(filename), 'w', encoding='utf-8') as handle:
            json.dump(payload, handle)
    except OSError:
        pass


def _read_sigcheck(filename: str) -> dict | None:
    if not filename:
        return None
    try:
        with open(_sigcheck_path(filename), encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if data.get('version') != signature_detection.SIDECAR_VERSION:
        return None
    return data


def run_signature_validation(filename: str, textract_blocks, names: dict) -> dict:
    """Analyse the uploaded document and persist the regions + result sidecar."""
    file_path = UPLOADS_DIR / Path(str(filename or '')).name
    if not file_path.is_file():
        return signature_detection.blank_result(names)
    result = signature_detection.analyze(file_path, textract_blocks, names=names)
    _write_sigcheck(filename, result.get('regions', {}), result)
    return result


def recheck_signature_validation(filename: str, names: dict) -> dict:
    """Re-measure signatures using the cached regions, or a fresh analysis."""
    file_path = UPLOADS_DIR / Path(str(filename or '')).name
    if not file_path.is_file():
        return signature_detection.blank_result(names)
    sidecar = _read_sigcheck(filename)
    if sidecar and sidecar.get('regions'):
        result = signature_detection.reanalyze(file_path, sidecar['regions'], names=names)
    else:
        result = signature_detection.analyze(file_path, None, names=names)
    _write_sigcheck(filename, result.get('regions', {}), result)
    return result


def _signature_guard(filename: str, names: dict):
    """Return an error payload when required signatures are not all present.

    ``None`` means the save may proceed. The check re-analyses the actual
    document; a document that cannot be found on disk is not blocked here (the
    upload-time check + disabled button are the front line), but any real
    uploaded file referenced in a bypass attempt is re-verified.
    """
    file_path = UPLOADS_DIR / Path(str(filename or '')).name
    if not filename or not file_path.is_file():
        return None
    result = recheck_signature_validation(filename, names)
    summary = result.get('summary', {})
    if summary.get('can_save'):
        return None
    missing = summary.get('missing_signatures') or []
    unverifiable = summary.get('unverifiable_signatures') or []
    if unverifiable and not missing:
        error = (
            'One or more required signatures could not be verified. '
            'Please review the original document and recheck signatures before saving.'
        )
    else:
        error = 'Purchase Request cannot be saved because one or more required signatures are missing.'
    return {
        'success': False,
        'error': error,
        'missing_signatures': missing,
        'unverifiable_signatures': unverifiable,
        'signature_validation': result,
    }


def extract_text_from_upload(path: Path, filename: str) -> tuple[dict, str]:
    lower_name = filename.lower()
    if lower_name.endswith('.pdf') or lower_name.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.tif')):
        document = ocr_service.process_file(path, filename)
        layout = layout_parser.parse(document)
        return {
            "document": document.to_dict(),
            "layout": layout,
            "textract_blocks": document.textract_blocks,
            "textract_response": document.textract_response,
        }, 'ocr'
    return {'document': {'pages': [], 'raw_text': '', 'source': 'none', 'filename': filename}, 'layout': {'blocks': [], 'text': '', 'line_count': 0}}, 'none'


def is_purchase_request_document(document: dict, parsed: dict) -> bool:
    raw_text = str(document.get('raw_text') or '')
    normalized_text = re.sub(r'[^a-z0-9]+', ' ', raw_text.lower()).strip()
    if re.search(r'purchase request|purchase requisition', normalized_text):
        return True

    structural_terms = (
        'pr no', 'requested by', 'approved by', 'funds available',
        'item description', 'unit cost', 'quantity', 'grand total',
    )
    matched_terms = sum(term in normalized_text for term in structural_terms)
    has_items = bool(parsed.get('requested_items') or parsed.get('items'))
    has_header = bool(parsed.get('entityName') or parsed.get('prNumber') or parsed.get('fundCluster'))
    return matched_terms >= 2 and (has_items or has_header)


def get_line_value(lines: list[str], source: str, labels: list[str], fallback_pattern: str | None = None) -> str | None:
    regex = re.compile(rf"^(?:{'|'.join(map(re.escape, labels))})\s*[:\-]\s*(.+)$", re.I)
    for line in lines:
        match = regex.match(line)
        if match:
            return normalize_text(match.group(1))
    if fallback_pattern:
        fallback = re.search(fallback_pattern, source, re.I)
        if fallback:
            return normalize_text(fallback.group(1))
    return None


def get_table_description(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        if re.search(r'\bDescription\b|\bStock No\b', line, re.I):
            for next_line in lines[index + 1:]:
                if not next_line:
                    continue
                if re.match(r'^(supplier|address|tin|date|p\.o\.|p\.r\.|mode|total|amount|place of delivery|delivery term|payment term)', next_line, re.I):
                    break
                if re.match(r'^\d+\.', next_line) or re.match(r'^units?', next_line, re.I) or re.match(r'^\S+\s+units?\s+', next_line, re.I):
                    return normalize_text(next_line)
                if re.search(r'\bclamp meter\b|\bdescription\b', next_line, re.I):
                    return normalize_text(next_line)
    return None


def extract_fields_from_text(text: str) -> dict:
    source = (text or '').replace('\r', '')
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    return {
        'supplier': get_line_value(lines, source, ['supplier'], r'Supplier\s*[:\-]\s*([^\n]+)'),
        'address': get_line_value(lines, source, ['address'], r'Address\s*[:\-]\s*([^\n]+)'),
        'tin': get_line_value(lines, source, ['tin'], r'TIN\s*[:\-]\s*([^\n]+)'),
        'poNumber': get_line_value(lines, source, ['p.o. no', 'po no', 'p.o. number', 'po number'], r'P\.O\.\s*No\.\?\s*[:\-]\s*([A-Za-z0-9-]+)'),
        'date': get_line_value(lines, source, ['date'], r'Date\s*[:\-]\s*([^\n]+)'),
        'prNumber': get_line_value(lines, source, ['p.r. no', 'pr no', 'pr number'], r'P\.R\.\s*No\.\?\s*[:\-]\s*([A-Za-z0-9-]+)'),
        'modeOfProcurement': get_line_value(lines, source, ['mode of procurement'], r'Mode of Procurement\s*[:\-]?\s*([^\n]+)'),
        'placeOfDelivery': get_line_value(lines, source, ['place of delivery'], r'Place of Delivery\s*[:\-]?\s*([^\n]+)'),
        'paymentTerm': get_line_value(lines, source, ['payment term'], r'Payment Term\s*[:\-]?\s*([^\n]+)'),
        'totalAmount': (get_line_value(lines, source, ['total amount'], r'Total\s*Amount\s*[:\-]?\s*₱?\s*([0-9,\.]+)')
                        or get_line_value(lines, source, ['total'], r'Total\s*[:\-]?\s*₱?\s*([0-9,\.]+)')
                        or get_line_value(lines, source, ['amount'], r'Amount\s*[:\-]?\s*₱?\s*([0-9,\.]+)')),
        'items': (get_table_description(lines)
                  or get_line_value(lines, source, ['description'], r'Description\s*[:\-]?\s*([^\n]+)')
                  or get_line_value(lines, source, ['item', 'items'], r'Items?\s*[:\-]?\s*([^\n]+)')),
    }


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 310000, dklen=32)
    return f"{salt}:{derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or ':' not in stored_hash:
        return False
    salt, hash_value = stored_hash.split(':', 1)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 310000, dklen=32)
    return secrets.compare_digest(hash_value, derived.hex())


def json_error(message: str, status: int = 400):
    return JsonResponse({'success': False, 'message': message}, status=status)


PR_NUMBER_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{3}$')


def next_pr_number(today=None, lock=False):
    today = today or timezone.localdate()
    prefix = f'{today:%Y-%m}-'
    year_prefix = f'{today:%Y}-'
    if lock:
        # The advisory-lock row is normally seeded by migration 0009, but guard
        # against environments where it is missing so numbering never 500s.
        PRNumberSequence.objects.get_or_create(key='global')
        PRNumberSequence.objects.select_for_update().filter(key='global').first()

    highest = 0
    valid_number = re.compile(rf'^{re.escape(year_prefix)}\d{{2}}-(\d{{3}})$')
    for value in PurchaseRequest.objects.filter(pr_no__startswith=year_prefix).values_list('pr_no', flat=True):
        match = valid_number.fullmatch(value or '')
        if match:
            highest = max(highest, int(match.group(1)))

    return f'{prefix}{highest + 1:03d}'


def generate_pr_number():
    return next_pr_number(lock=True)


_RFQ_NUMBER_RE = re.compile(r'^RFQ-(\d{4})-(\d+)$')


def validate_custom_pr_number(value):
    number = str(value or '').strip()
    if not PR_NUMBER_PATTERN.fullmatch(number):
        return None
    try:
        datetime.strptime(number[:7], '%Y-%m')
    except ValueError:
        return None
    return number


@require_GET
@require_auth(role='buyer')
def next_pr_number_preview(request):
    return JsonResponse({'pr_no': next_pr_number()})


@csrf_exempt
@require_POST
@require_auth(role='buyer')
def upload_file(request):
    file = request.FILES.get('file')
    if not file:
        return json_error('No file uploaded', 400)

    # Authoritative validation before any storage or OCR/Textract work.
    try:
        validate_upload(file, UploadKind.PR)
    except FileValidationError as exc:
        return json_error(exc.message, 400)

    filename = f"{int(time.time() * 1000)}_{file.name}"
    file_path = UPLOADS_DIR / filename
    with open(file_path, 'wb') as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    payload, source = extract_text_from_upload(file_path, file.name)
    write_debug_json('textract_response.json', payload.get('textract_response') or {})
    document = payload.get('document', {})
    layout = payload.get('layout', {})
    parsed = parse_purchase_request(document.get('raw_text', ''), layout, payload.get('textract_blocks') or [])
    # Date values in scanned table cells can be separated from the ``Date:``
    # label by OCR. Recover the visible date directly from the raw text.
    parsed_header = parsed.setdefault('header', {})
    if not parsed_header.get('date'):
        date_match = re.search(r'\b(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{4})\b', document.get('raw_text', ''))
        if date_match:
            try:
                parsed_header['date'] = datetime.strptime(
                    f'{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}', '%m/%d/%Y'
                ).date().isoformat()
            except ValueError:
                pass
    if not is_purchase_request_document(document, parsed):
        file_path.unlink(missing_ok=True)
        return json_error('This file does not appear to be a Purchase Request. Upload a PR document.', 422)

    auto_filled = auto_fill_service.populate(parsed)
    validation = validation_service.validate(parsed)
    signature_validation = run_signature_validation(
        filename, payload.get('textract_blocks') or [], _signatory_names({**auto_filled, **parsed})
    )
    response_payload = {
        'success': True,
        'fields': {**auto_filled, **parsed},
        'rawText': document.get('raw_text', ''),
        'source': source,
        'filename': filename,
        'fileUrl': request.build_absolute_uri(f'/uploads/{filename}'),
        'ocr': document,
        'validation': validation,
        'signature_validation': signature_validation,
    }
    write_debug_json('final_output.json', response_payload)
    return JsonResponse(response_payload)


@csrf_exempt
@require_POST
@require_auth(role='buyer')
def pr_recheck_signatures(request):
    """Re-run signature-presence validation for an already-uploaded PR document.

    Backs the "Recheck Signatures" action - no re-upload and no re-OCR (the
    signature regions derived at upload time are reused).
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (TypeError, json.JSONDecodeError):
        return json_error('Invalid JSON payload', 400)

    filename = str(data.get('filename') or data.get('sourceFilename') or '').strip()
    if not filename:
        return json_error('A source document filename is required.', 400)
    if not (UPLOADS_DIR / Path(filename).name).is_file():
        return json_error('The uploaded document could not be found. Please re-upload it.', 404)

    names = _signatory_names(data.get('fields') or data)
    result = recheck_signature_validation(filename, names)
    return JsonResponse({'success': True, 'signature_validation': result})


@csrf_exempt
@require_POST
@require_auth(role='buyer')
def pr_scan(request):
    """Accept a single PDF upload, run the extractor and return parsed JSON.

    Returns 422 when no table/items were detected so the frontend can fall back to manual entry.
    """
    f = request.FILES.get('file')
    if not f:
        return json_error('No file uploaded', 400)

    try:
        validate_upload(f, UploadKind.PR)
    except FileValidationError as exc:
        return json_error(exc.message, 400)

    filename = f"{int(time.time() * 1000)}_{f.name}"
    file_path = UPLOADS_DIR / filename
    with open(file_path, 'wb') as dest:
        for chunk in f.chunks():
            dest.write(chunk)

    try:
        payload, source = extract_text_from_upload(file_path, f.name)
        write_debug_json('textract_response.json', payload.get('textract_response') or {})
        document = payload.get('document', {})
        layout = payload.get('layout', {})

        parsed = parse_purchase_request(document.get('raw_text', ''), layout, payload.get('textract_blocks') or [])

        validation = parsed.get('validation', {})
    except ValueError as ve:
        return JsonResponse({'success': False, 'message': str(ve)}, status=422)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': 'Failed to parse document'}, status=422)

    # If no items found, signal unparseable (likely scanned or table-missing)
    requested = parsed.get('requested_items') or parsed.get('items') or []
    if not requested:
        return JsonResponse({'success': False, 'message': 'No table detected or extraction produced no items'}, status=422)

    response_payload = {
        'success': True,
        'fields': parsed,
        'rawText': document.get('raw_text', ''),
        'source': source,
        'filename': filename,
        'fileUrl': request.build_absolute_uri(f'/uploads/{filename}'),
        'validation': validation,
    }
    write_debug_json('final_output.json', response_payload)
    return JsonResponse(response_payload)


@csrf_exempt
@require_POST
@require_auth(role='buyer')
def create_pr(request):
    """Create a PurchaseRequest and its line items from validated JSON (officer-confirmed).

    Expects JSON body with keys matching parser output, especially `entityName` and `requested_items`.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return json_error('Invalid JSON payload', 400)

    fields = data.get('fields') or data or {}
    entity = normalize_text(fields.get('entityName') or fields.get('entity_name') or '')
    if not entity:
        return json_error('entityName is required', 400)

    items = fields.get('requested_items') or fields.get('line_items') or fields.get('items') or []
    numbering_mode = str(fields.get('prNumberMode') or fields.get('pr_number_mode') or 'automatic').lower()
    review_only = bool(fields.get('reviewOnly') or fields.get('review_only'))
    custom_pr_number = validate_custom_pr_number(fields.get('prNumber') or fields.get('pr_no'))

    declaration_ack = _declaration_acknowledged(fields)

    # The Buyer submission path (review_only) has two independent gates, both
    # enforced here and never trusted from the browser: the required signatures
    # must be detected on the document, AND the submitter must have acknowledged
    # the Purchase Request Submission Declaration. The Admin review/edit path
    # (pr_update) is unaffected.
    if review_only:
        source_filename = str(fields.get('sourceFilename') or fields.get('source_filename') or '').strip()

        if not declaration_ack:
            return JsonResponse({
                'success': False,
                'error': 'Please acknowledge the Purchase Request Submission Declaration before submitting.',
                'declaration_required': True,
            }, status=422)

        # Guard against an accidental double-submission (double click, retry):
        # the same document just submitted by the same user is returned, not
        # duplicated.
        if source_filename:
            recent = PurchaseRequest.objects.filter(
                source_filename=source_filename,
                submitted_by=normalize_text(fields.get('submittedBy') or fields.get('submitted_by') or ''),
                created_at__gte=timezone.now() - timedelta(minutes=2),
            ).order_by('-created_at').first()
            if recent is not None:
                return JsonResponse({
                    'success': True, 'id': recent.id, 'pr_no': recent.pr_no,
                    'status': recent.status, 'duplicate': True,
                    'created_at': recent.created_at.isoformat(),
                }, status=200)

        blocked = _signature_guard(source_filename, _signatory_names(fields))
        if blocked is not None:
            return JsonResponse(blocked, status=422)

    if review_only:
        assigned_pr_number = None
    elif numbering_mode == 'custom':
        if not custom_pr_number:
            return json_error('Custom PR number must use YYYY-MM-NNN format', 400)
        if PurchaseRequest.objects.filter(pr_no=custom_pr_number).exists():
            return json_error('PR number is already assigned', 409)
    elif numbering_mode != 'automatic':
        return json_error('Invalid PR numbering mode', 400)

    try:
        with transaction.atomic():
            if not review_only:
                assigned_pr_number = custom_pr_number if numbering_mode == 'custom' else generate_pr_number()
            pr = PurchaseRequest.objects.create(
                entity_name=entity,
                category=normalize_text(fields.get('category') or fields.get('pr_category') or '') or None,
                fund_cluster=normalize_text(fields.get('fundCluster') or fields.get('fund_cluster') or ''),
                office_section=normalize_text(fields.get('officeSection') or fields.get('office_section') or ''),
                pr_no=assigned_pr_number,
                source_filename=normalize_text(fields.get('sourceFilename') or fields.get('source_filename') or ''),
                submitted_by=normalize_text(fields.get('submittedBy') or fields.get('submitted_by') or ''),
                responsibility_center_code=normalize_text(fields.get('responsibilityCenterCode') or fields.get('responsibility_center_code') or ''),
                date=fields.get('date') or None,
                purpose=fields.get('purpose') or '',
                requested_by=fields.get('requested_by_name') or fields.get('requestedBy') or '',
                funds_available_by=fields.get('funds_available_name') or '',
                approved_by=fields.get('approved_by_name') or '',
                twg_verified_by=fields.get('twg_name') or '',
                status=PurchaseRequest.STATUS_UPLOADED,
                grand_total=fields.get('grand_total') or 0,
                declaration_acknowledged=bool(declaration_ack),
                declaration_acknowledged_at=timezone.now() if declaration_ack else None,
            )

            for item in items:
                qty = item.get('quantity') or item.get('qty') or '0'
                unit_cost = item.get('unit_cost') or item.get('unitCost') or '0'
                total_cost = item.get('total_cost') or item.get('totalCost') or ''
                try:
                    from decimal import Decimal

                    qty_d = Decimal(str(qty).replace(',', '') or '0')
                    unit_cost_d = Decimal(str(unit_cost).replace(',', '') or '0')
                    total_cost_d = Decimal(str(total_cost).replace(',', '') or (qty_d * unit_cost_d))
                except Exception:
                    qty_d = 0
                    unit_cost_d = 0
                    total_cost_d = 0

                PurchaseRequestItem.objects.create(
                    purchase_request=pr,
                    stock_property_no=item.get('stock_no') or item.get('stockPropertyNumber') or '',
                    unit=item.get('unit') or '',
                    item_description=item.get('description') or item.get('item_description') or '',
                    quantity=qty_d,
                    unit_cost=unit_cost_d,
                    total_cost=total_cost_d,
                )
    except IntegrityError:
        return json_error('PR number is already assigned', 409)
    except Exception as exc:
        return json_error('Failed to save Purchase Request', 500)

    return JsonResponse({
        'success': True, 'id': pr.id, 'pr_no': pr.pr_no, 'status': pr.status,
        'created_at': pr.created_at.isoformat(),
        'declaration_acknowledged': pr.declaration_acknowledged,
    }, status=201)


@require_GET
def health(request):
    return JsonResponse({'status': 'ok', 'message': 'Backend is running'})


OPPORTUNITY_CATEGORIES = [
    'Advertising Agency Services', 'Agricultural Chemicals',
    'Agricultural Machinery and Equipment',
    'Agricultural Products (Seeds, Seedlings, Plants..)',
    'Airconditioning and Airconditioning Systems',
    'Airconditioning Maintenance Services', 'Aircraft Spare Parts',
    'Ammunitions and Explosives', 'Animal Feeds', 'Appliances',
    'Architectural Design', 'Arts and Crafts Accessories and Supplies',
    'Audio and Visual Equipment', 'Automation Equipment', 'Aviation Products',
    'Aviation Services', 'Bedclothes, Linens and Towels', 'Beverages',
    'Books, Maps and Other Publications', 'Cargo Forwarding and Hauling Services',
    'Catering Services', 'Chemical Detergents', 'Chemicals and Chemical Products',
    'Communication Equipment',
    'Communication Equipment & Parts and Accessories', 'Computer Furniture',
    'Construction Equipment', 'Construction Management Services',
    'Construction Materials and Supplies', 'Construction Projects',
    'Consulting Services', 'Corporate Giveaways', 'Dairy Products',
    'Diagnostic and Laboratory Services', 'Drugs and Medicines',
    'Editorial, Design, Graphic and Fine Art Services',
    'Educational Materials and Supplies', 'Electrical Supplies',
    'Electrical Systems and Lighting Components',
    'Electronic Parts and Components',
    'Engineering and Laboratory Testing Equipment',
    'Environmental Health/Safety Equipment', 'Events Management', 'Fertilizers',
    'Fire Fighting & Rescue and Safety Equipment', 'Fixtures', 'Flags',
    'Food Processing Equipment', 'Food Stuff', 'Freight Forwarder Services',
    'Fuels/Fuel Additives & Lubricants & Anti Corrosive', 'Furniture',
    'Furniture Parts and Accessories', 'Games and Toys',
    'Gaming Equipment and Paraphernalia', 'Garments', 'General Contractor',
    'General Engineering Services', 'General Merchandise',
    'General Repair and Maintenance Services', 'Geotechnical Instrumentation',
    'Grocery Items', 'Guns and Weapons', 'Hardware and Construction Supplies',
    'Helicopters - Parts', 'Horizontal Directional Drilling',
    'Hospital / Medical Equipment', 'Hospital / Medical Equipment Services',
    'Hotel and Lodging and Meeting Facilities', 'Hydrological Instruments',
    'Industrial Machinery and Equipment', 'Industrial pumps and compressors',
    'Industrial Safety Equipment', 'Information Technology',
    'Information Technology Parts & Peripheral',
    'Institutional food services equipment', 'Internet Services',
    'Investigative Equipment', 'IT Broadcasting and Telecommunications',
    'Janitorial Equipment', 'Janitorial Services', 'Janitorial Supplies',
    'Kitchenware', 'Laboratory Supplies and Equipment', 'Laundry Services',
    'Lease and Rental of Property or Building',
    'Lifting equipment and accessories',
    'Live Animals (Livestock, Birds, Live fish & etc..)', 'Machine Tools',
    'Mail and Cargo Transport Services', 'Mailing Supplies', 'Marine Transport',
    'Maritime Spare Parts', 'Market Research Services',
    'Medical and Dental Equipment', 'Medical Supplies and Laboratory Instrument',
    'Metal Fabrication', 'Meteorological Equipments and Instruments',
    'Microfilm Equipment', 'Microfilm Equipment - Supplies and Accesories',
    'Mining Equipment and Supplies', 'Musical Instrument Parts and Accesories',
    'Musical Instruments', 'Navigation Equipment', 'Newspapers',
    'Office Equipment', 'Office Equipment Parts and Accessories',
    'Office Equipment Supplies and Consumables', 'Office Supplies and Devices',
    'Oil/Heat Chemical Resistant Rubber', 'Ordnance Products',
    'Packaging Supplies and Materials', 'Personal Care Products',
    'Pest Control Products', 'Pest Control Services', 'Photographic Equipment',
    'Photographic Parts, Supplies and Accessories', 'Photography Services',
    'Plastic Products', 'Power Generation and Distribution Machinery',
    'Preserved or Processed Foods', 'Print and Broadcast and Aerial Advertising',
    'Printing Services', 'Printing Supplies',
    'Public Relations Programs or Services', 'Purses, handbags and bags',
    'Pyrotechnics and Fireworks', 'Quartermaster Items',
    'Radiological/Diagnostic Equipment',
    'Real Estate Developement and Maintenance', 'Reproduction Services',
    'Rice Milling Services', 'Safety and Occupational Products',
    'Sale of Property or Building', 'Security Services',
    'Security Surveillance and Detection Equipment', 'Services',
    'Signage and Accessories', 'Sporting Goods', 'Structured Cabling',
    'Sub-station Contractors', 'Surveying Instruments', 'Surveying Services',
    'Systems Integration', 'Telecommunications Engineering',
    'Telecommunications Provider', 'Textiles',
    'Timepieces and Jewelry and Gemstone Products', 'Tokens and Awards',
    'Traffic Control Systems', 'Transmission and Distribution Lines',
    'Transportation and Communications Services',
    'Travel, Food, Lodging and Entertainment Services',
    'Vehicle Parts and Accessories', 'Vehicle Repair and Maintenance',
    'Vehicles', 'Veterinary Products and Supplies', 'Video Production Services',
    'Waste Management and Recycling',
    'Water and Waste Water Treatment Supply & Disposal',
    'Water Service Connection Materials/Fittings',
    'Well Drilling and Construction Services',
]


@require_GET
def categories_view(request):
    categories = list(
        Category.objects.filter(is_active=True).order_by('name')
    )

    result = []
    for category in categories:
        result.append({'id': category.id, 'name': category.name, 'count': 0})
    return JsonResponse(result, safe=False)


@require_GET
def get_roles(request):
    roles = list(Role.objects.order_by('id').values('id', 'name', 'description'))
    return JsonResponse(roles, safe=False)


# ── End-user (buyer) facing PR progress ─────────────────────────────────────
# The buyer sees a high-level procurement status derived from the PR status and
# the RFQ lifecycle only - never supplier identities, matching scores, or
# quotations. The backend stays the source of truth for the stage.
BUYER_PR_STAGES = [
    'submitted', 'under_review', 'supplier_matching', 'rfq_sent',
    'supplier_response', 'completed',
]

BUYER_PR_STAGE_LABELS = {
    'submitted': 'Submitted',
    'under_review': 'Under BAC Review',
    'supplier_matching': 'Supplier Matching',
    'rfq_sent': 'RFQ Sent',
    'supplier_response': 'Supplier Response',
    'completed': 'Completed',
    'rejected': 'Rejected',
}

BUYER_PR_STAGE_DESCRIPTIONS = {
    'submitted': 'Your Purchase Request has been submitted and is queued for BAC review.',
    'under_review': 'Your Purchase Request is currently being reviewed by the BAC Secretariat.',
    'supplier_matching': 'Your Purchase Request is being matched with eligible suppliers.',
    'rfq_sent': 'A Request for Quotation has been issued to qualified suppliers.',
    'supplier_response': 'A supplier response to the Request for Quotation has been received.',
    'completed': 'Your Purchase Request has completed the current procurement workflow.',
    'rejected': 'Your Purchase Request was not approved by the BAC Secretariat.',
}


def _buyer_pr_stage(pr_status, rfq_sent_count, rfq_response_count):
    """Collapse the internal PR + RFQ state into one buyer-facing stage key."""
    if pr_status == PurchaseRequest.STATUS_REJECTED:
        return 'rejected'
    if pr_status == PurchaseRequest.STATUS_APPROVED:
        return 'completed'
    if rfq_response_count:
        return 'supplier_response'
    if rfq_sent_count:
        return 'rfq_sent'
    if pr_status == PurchaseRequest.STATUS_MATCHED:
        return 'supplier_matching'
    if pr_status == PurchaseRequest.STATUS_IN_REVIEW:
        return 'under_review'
    return 'submitted'


@require_GET
def pr_list(request):
    category = request.GET.get('category', '').strip()
    submitted_by = request.GET.get('submitted_by', '').strip()
    qs = (
        PurchaseRequest.objects.order_by('-created_at')
        .annotate(items_count=Count('line_items'))
        .annotate(has_quotation=Exists(Quotation.objects.filter(purchase_request_id=OuterRef('pk'))))
        .annotate(assigned_category_exists=Exists(
            PurchaseRequestItem.objects
            .filter(purchase_request_id=OuterRef('pk'))
            .exclude(category__isnull=True)
            .exclude(category='')
        ))
    )
    if category:
        qs = qs.filter(category=category)
    if submitted_by:
        qs = qs.filter(submitted_by=submitted_by)
    prs = qs.values(
            'id',
            'entity_name',
            'pr_no',
            'office_section',
            'category',
            'status',
            'purpose',
            'date',
            'requested_by',
            'approved_by',
            'grand_total',
            'created_at',
            'items_count',
            'has_quotation',
            'assigned_category_exists',
        )
    records = list(prs)

    # RFQ rollup per PR in a single grouped query (no N+1). Only non-draft RFQs
    # count as "sent"; a non-empty submitted_pdf counts as a supplier response.
    rfq_rollup = {
        row['purchase_request']: row
        for row in (
            RFQ.objects
            .filter(purchase_request_id__in=[r['id'] for r in records])
            .exclude(status=RFQ.STATUS_DRAFT)
            .values('purchase_request')
            .annotate(
                sent=Count('id'),
                responded=Count('id', filter=Q(submitted_pdf__gt='')),
                first_sent_at=Min('sent_at'),
                first_response_at=Min('submitted_at'),
            )
        )
    }

    for record in records:
        if record.pop('assigned_category_exists') is False and record['status'] == PurchaseRequest.STATUS_MATCHED:
            record['status'] = PurchaseRequest.STATUS_IN_REVIEW

        rollup = rfq_rollup.get(record['id'], {})
        sent = rollup.get('sent') or 0
        responded = rollup.get('responded') or 0
        stage = _buyer_pr_stage(record['status'], sent, responded)

        record['rfq_sent_count'] = sent
        record['rfq_response_count'] = responded
        record['display_stage'] = stage
        record['display_status'] = BUYER_PR_STAGE_LABELS[stage]
        record['status_description'] = BUYER_PR_STAGE_DESCRIPTIONS[stage]
        # Real timestamps only - stages without a dedicated timestamp field
        # (review, matching, completed) are left out rather than invented.
        record['stage_timestamps'] = {
            'submitted': record['created_at'],
            'rfq_sent': rollup.get('first_sent_at'),
            'supplier_response': rollup.get('first_response_at'),
        }

    return JsonResponse(records, safe=False)


@csrf_exempt
@require_http_methods(["PATCH"])
@require_auth(role='admin')
def pr_update_status(request, pr_id: int):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return json_error('Invalid JSON payload', 400)

    status = str(payload.get('status') or '').strip()
    allowed = {choice[0] for choice in PurchaseRequest.STATUS_CHOICES}
    if status not in allowed:
        return json_error('Invalid PR status', 400)

    updated = PurchaseRequest.objects.filter(id=pr_id).update(status=status)
    if not updated:
        return json_error('Purchase Request not found', 404)

    return JsonResponse({'success': True, 'id': pr_id, 'status': status})


@csrf_exempt
@require_http_methods(["PATCH"])
@require_auth(role='admin')
def pr_update(request, pr_id: int):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return json_error('Invalid JSON payload', 400)

    try:
        pr = PurchaseRequest.objects.get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)

    entity_name = str(payload.get('entity_name') or '').strip()
    if not entity_name:
        return json_error('Entity name is required', 400)

    items = payload.get('items', [])
    if not isinstance(items, list):
        return json_error('Items must be a list', 400)

    try:
        from decimal import Decimal
        with transaction.atomic():
            finalize_review = bool(payload.get('finalize_review'))
            numbering_mode = str(payload.get('pr_number_mode') or 'automatic').lower()
            if finalize_review and not pr.pr_no:
                if numbering_mode == 'custom':
                    assigned_number = validate_custom_pr_number(payload.get('custom_pr_number'))
                    if not assigned_number:
                        return json_error('Custom PR number must use YYYY-MM-NNN format', 400)
                    if PurchaseRequest.objects.filter(pr_no=assigned_number).exclude(id=pr.id).exists():
                        return json_error('PR number is already assigned', 409)
                else:
                    assigned_number = generate_pr_number()
                pr.pr_no = assigned_number
            if finalize_review:
                pr.status = PurchaseRequest.STATUS_IN_REVIEW
            pr.entity_name = entity_name
            pr.source_filename = str(payload.get('source_filename') or pr.source_filename or '').strip()
            pr.category = str(payload.get('category') or '').strip() or None
            pr.fund_cluster = str(payload.get('fund_cluster') or '').strip()
            pr.office_section = str(payload.get('office_section') or '').strip()
            pr.responsibility_center_code = str(payload.get('responsibility_center_code') or '').strip()
            pr.date = payload.get('date') or None
            pr.purpose = str(payload.get('purpose') or '').strip()
            pr.requested_by = str(payload.get('requested_by') or '').strip()
            pr.funds_available_by = str(payload.get('funds_available_by') or '').strip()
            pr.approved_by = str(payload.get('approved_by') or '').strip()
            pr.twg_verified_by = str(payload.get('twg_verified_by') or '').strip()
            pr.grand_total = sum(
                Decimal(str(item.get('quantity') or 0)) * Decimal(str(item.get('unit_cost') or 0))
                for item in items
            )
            update_fields = ['entity_name', 'source_filename', 'category', 'fund_cluster', 'office_section', 'responsibility_center_code', 'date', 'purpose', 'requested_by', 'funds_available_by', 'approved_by', 'twg_verified_by', 'grand_total']
            if finalize_review:
                update_fields.extend(['pr_no', 'status'])
            pr.save(update_fields=update_fields)
            pr.line_items.all().delete()
            for item in items:
                quantity = Decimal(str(item.get('quantity') or 0))
                unit_cost = Decimal(str(item.get('unit_cost') or 0))
                PurchaseRequestItem.objects.create(
                    purchase_request=pr,
                    stock_property_no=str(item.get('stock_property_no') or '').strip(),
                    unit=str(item.get('unit') or '').strip(),
                    item_description=str(item.get('item_description') or '').strip(),
                    quantity=quantity,
                    unit_cost=unit_cost,
                    total_cost=quantity * unit_cost,
                    category=str(item.get('category') or '').strip() or None,
                )
    except (ArithmeticError, ValueError, TypeError):
        return json_error('Invalid Purchase Request values', 400)

    return JsonResponse({'success': True, 'id': pr.id, 'pr_no': pr.pr_no, 'status': pr.status, 'grand_total': float(pr.grand_total)})


@csrf_exempt
@require_http_methods(["DELETE"])
@require_auth(role='admin')
def pr_delete(request, pr_id: int):
    deleted, _ = PurchaseRequest.objects.filter(id=pr_id).delete()
    if not deleted:
        return json_error('Purchase Request not found', 404)
    return JsonResponse({'success': True, 'id': pr_id})


@csrf_exempt
@require_POST
@require_auth(role='admin')
def register(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return json_error('Invalid JSON payload', 400)

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role_name = data.get('role', 'buyer')
    full_name = data.get('fullName', '').strip()
    email = data.get('email', '').strip()
    unit_office = data.get('unitOffice', '').strip()

    if not username or not password:
        return json_error('Username and password are required', 400)

    if role_name not in ('admin', 'buyer', 'supplier'):
        role_name = 'buyer'

    role = Role.objects.filter(name=role_name).first()
    if not role:
        return json_error('Invalid role selected', 400)

    password_hash = hash_password(password)
    try:
        with transaction.atomic():
            user = User.objects.create(
                username=username,
                password_hash=password_hash,
                full_name=full_name,
                email=email,
                unit_office=unit_office,
                role=role,
                is_active=True,
            )
    except IntegrityError:
        return json_error('Username already exists', 409)

    return JsonResponse({'success': True, 'userId': user.id, 'role': role_name}, status=201)


@require_GET
@require_auth(role='admin')
def buyer_account_list(request):
    accounts = User.objects.filter(role__name='buyer').select_related('role').order_by('-created_at')
    payload = [{
        'id': account.id,
        'username': account.username,
        'full_name': account.full_name,
        'email': account.email,
        'unit_office': account.unit_office,
        'created_at': account.created_at,
        'last_login': account.last_login,
    } for account in accounts]
    return JsonResponse(payload, safe=False)


@csrf_exempt
@require_http_methods(['DELETE'])
@require_auth(role='admin')
def buyer_account_delete(request, user_id: int):
    account = User.objects.filter(id=user_id, role__name='buyer').first()
    if not account:
        return json_error('Buyer account not found', 404)

    account.delete()
    return JsonResponse({'success': True, 'id': user_id})


@csrf_exempt
@require_POST
def login_view(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return json_error('Invalid JSON payload', 400)

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    role_name = data.get('role', 'buyer')

    if not username or not password:
        return json_error('Username and password are required', 400)

    user = User.objects.filter(username=username, is_active=True).select_related('role').first()
    if not user or not verify_password(password, user.password_hash):
        return json_error('Invalid username or password', 401)

    if role_name and user.role.name != role_name:
        return json_error('Role mismatch', 403)

    # Resolve which Supplier record this account represents. There is no FK
    # between User and Supplier (see ``_supplier_login_accounts``), so this is
    # derived from the same account-matches-supplier heuristic used
    # elsewhere - it is NEVER taken from client input. A client-supplied
    # ``supplier_id`` would let anyone log in with their own credentials and
    # bind the session to a different supplier's data, so it is ignored, and
    # an account with no server-derivable match gets no supplier binding at
    # all rather than an arbitrary one.
    supplier_payload = None
    supplier = None
    if user.role.name == 'supplier':
        supplier = Supplier.objects.filter(email__icontains=username).order_by('-created_at').first()
        if supplier is None and user.full_name:
            supplier = Supplier.objects.filter(
                contact_person__iexact=user.full_name.strip()
            ).order_by('-created_at').first()
        if supplier is not None:
            supplier_payload = {
                'supplier_id': supplier.id,
                'supplier_status': supplier.status,
            }

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    # Start a fresh session for this login (flush drops any prior anonymous
    # session data and rotates the session key) and record only what the
    # server itself resolved above.
    request.session.flush()
    request.session['user_id'] = user.id
    request.session['role'] = user.role.name
    request.session['username'] = user.username
    if supplier is not None:
        request.session['supplier_id'] = supplier.id

    return JsonResponse({
        'success': True,
        'message': 'Login successful',
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role.name,
            'full_name': user.full_name,
            'email': user.email,
            'unit_office': user.unit_office,
            **(supplier_payload or {}),
        },
    })


@csrf_exempt
@require_POST
def logout_view(request):
    request.session.flush()
    return JsonResponse({'success': True})


@csrf_exempt
@require_auth(role='admin')
def supplier_list_create(request):
    if request.method == 'GET':
        suppliers = list(
            Supplier.objects.order_by('-created_at').values(
                'id',
                'company_name',
                'email',
                'status',
                'business_type',
                'tin',
                'contact_person',
                'products_services',
                'created_at',
            )
        )
        for supplier in suppliers:
            supplier['documents_count'] = SupplierDocument.objects.filter(supplier_id=supplier['id']).count()
            supplier['categories'] = list(
                SupplierCategory.objects.filter(supplier_id=supplier['id']).select_related('category').values_list('category__name', flat=True)
            )
        return JsonResponse(suppliers, safe=False)

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return json_error('Invalid JSON payload', 400)

    company_name = data.get('companyName', '').strip()
    email = data.get('email', '').strip()
    contact_phone = data.get('contactPhone', '').strip()

    supplier = Supplier.objects.create(
        company_name=company_name,
        email=email,
        contact_phone=contact_phone,
        status='Pending',
    )
    return JsonResponse({'id': supplier.id}, status=201)


@require_GET
@require_auth(role='admin')
def suppliers_search(request):
    """Manual BAC supplier search by company name.

    Separate from ``pr_supplier_match`` on purpose: this endpoint answers "does
    the BAC Secretariat know another supplier who can provide this requirement?"
    and never applies the PR procurement-category filter. It does NOT mark
    results as eligible or category-matched - the caller must treat every hit as
    an "Other Supplier" pending an explicit manual selection.

    With ``exclude_pr=<pr id>`` the PR's category-matched suppliers are removed
    from the results, so the caller can show every remaining ("other") supplier
    by default without a search term and without duplicating the category-matched
    section. A short/blank query is a browse of that list, not an error.

    Restricted to admin/BAC users; buyers and suppliers cannot use it.
    """
    query = normalize_text(request.GET.get('name') or request.GET.get('q') or '')

    supplier_qs = Supplier.objects.all()
    if query:
        # ``icontains`` gives case-insensitive partial matching on every DB
        # backend the project supports; ``normalize_text`` collapsed whitespace.
        supplier_qs = supplier_qs.filter(company_name__icontains=query)

    # Drop suppliers already registered under the PR's procurement category -
    # those belong to the category-matched section, never to "Other Suppliers".
    exclude_pr = request.GET.get('exclude_pr')
    if exclude_pr:
        try:
            pr = PurchaseRequest.objects.prefetch_related('line_items').get(id=exclude_pr)
        except (PurchaseRequest.DoesNotExist, ValueError):
            return json_error('Purchase Request not found', 404)
        pr_category_names = {item.category for item in pr.line_items.all() if item.category}
        if pr.category:
            pr_category_names.add(pr.category)
        if pr_category_names:
            in_category_ids = SupplierCategory.objects.filter(
                category__name__in=pr_category_names
            ).values_list('supplier_id', flat=True)
            supplier_qs = supplier_qs.exclude(id__in=in_category_ids)

    limit = 20
    # Approved suppliers first so the selectable ones lead the default browse,
    # then alphabetical.
    supplier_qs = supplier_qs.annotate(
        _approved_first=Case(
            When(status='Approved', then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('_approved_first', 'company_name')
    matches = list(supplier_qs[:limit + 1])
    has_more = len(matches) > limit
    matches = matches[:limit]

    results = []
    for supplier in matches:
        categories = list(
            SupplierCategory.objects.filter(supplier=supplier)
            .select_related('category')
            .values_list('category__name', flat=True)
        )
        results.append({
            'id': supplier.id,
            'company_name': supplier.company_name,
            'status': supplier.status,
            'contact_person': supplier.contact_person,
            'email': supplier.email,
            'contact_phone': supplier.contact_phone,
            'business_address': supplier.business_address,
            'business_type': supplier.business_type,
            'nature_of_business': supplier.nature_of_business,
            'products_services': supplier.products_services or supplier.goods_services,
            'categories': categories,
        })

    return JsonResponse({
        'results': results,
        'query': query,
        'count': len(results),
        'has_more': has_more,
    })


KNOWN_SUPPLIER_STATUSES = ['Pending', 'Pending Review', 'In Review', 'For Compliance', 'Approved', 'Rejected']
KNOWN_DOCUMENT_STATUSES = ['Pending', 'Verified', 'Rejected']


def _status_breakdown(queryset, known_order, field='status'):
    """Count rows per ``field`` value, ordered with ``known_order`` first.

    Any status value present in the data but not in ``known_order`` (legacy or
    unexpected values) is appended afterwards rather than silently dropped.
    """
    counts = {row[field]: row['count'] for row in queryset.values(field).annotate(count=Count('id'))}
    breakdown = [{'status': status, 'count': counts.pop(status, 0)} for status in known_order]
    breakdown.extend({'status': status, 'count': count} for status, count in sorted(counts.items()))
    return breakdown


def _pr_monthly_volume(months=6):
    """Purchase request counts for each of the last ``months`` calendar months, oldest first."""
    now = timezone.localtime()
    year, month = now.year, now.month
    month_keys = []
    for _ in range(months):
        month_keys.append((year, month))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    month_keys.reverse()

    range_start = datetime(month_keys[0][0], month_keys[0][1], 1, tzinfo=now.tzinfo)
    counts_by_month = {
        row['month'].strftime('%Y-%m'): row['count']
        for row in (
            PurchaseRequest.objects.filter(created_at__gte=range_start)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
    }
    return [
        {'month': f'{year:04d}-{month:02d}', 'count': counts_by_month.get(f'{year:04d}-{month:02d}', 0)}
        for year, month in month_keys
    ]


def _rfq_stats():
    sent_rfqs = RFQ.objects.filter(sent_at__isnull=False).annotate(quotation_count=Count('quotations'))
    aggregates = sent_rfqs.aggregate(
        total_sent=Count('id'),
        with_response=Count('id', filter=Q(quotation_count__gt=0)),
        avg_quotations=Avg('quotation_count'),
    )
    return {
        'total_sent': aggregates['total_sent'] or 0,
        'with_response': aggregates['with_response'] or 0,
        'avg_quotations_per_rfq': round(aggregates['avg_quotations'] or 0, 2),
    }


@require_GET
@require_auth(role='admin')
def admin_dashboard_summary(request):
    """Return live summary counts and breakdowns for the BAC administrator dashboard."""
    supplier_category_breakdown = list(
        Category.objects.annotate(
            verified_supplier_count=Count(
                'supplier_categories',
                filter=Q(supplier_categories__supplier__status='Approved'),
                distinct=True,
            )
        )
        .values('name', 'verified_supplier_count')
        .order_by('-verified_supplier_count', 'name')
    )

    return JsonResponse({
        # Legacy fields, kept for any other consumer of this endpoint.
        'pending_suppliers': Supplier.objects.filter(status__in=['Pending', 'Pending Review']).count(),
        'under_review_suppliers': Supplier.objects.filter(status='In Review').count(),
        'action_required_suppliers': Supplier.objects.filter(status='For Compliance').count(),
        'total_suppliers': Supplier.objects.count(),
        'total_purchase_requests': PurchaseRequest.objects.count(),
        'pending_purchase_requests': PurchaseRequest.objects.filter(status__in=['uploaded', 'in_review', 'matched']).count(),
        'approved_purchase_requests': PurchaseRequest.objects.filter(status='approved').count(),

        'supplier_status_breakdown': _status_breakdown(Supplier.objects, KNOWN_SUPPLIER_STATUSES),
        'supplier_category_breakdown': [
            {'category': row['name'], 'count': row['verified_supplier_count']}
            for row in supplier_category_breakdown
        ],
        'document_status_breakdown': _status_breakdown(
            SupplierDocument.objects, KNOWN_DOCUMENT_STATUSES, field='verification_status'
        ),
        'pr_status_breakdown': _status_breakdown(
            PurchaseRequest.objects, [choice[0] for choice in PurchaseRequest.STATUS_CHOICES]
        ),
        'pr_monthly_volume': _pr_monthly_volume(),
        'rfq_stats': _rfq_stats(),
    })


def _parse_date_range(request):
    """Parse ``date_from``/``date_to`` (YYYY-MM-DD) query params into a Q filter, or None."""
    date_from = parse_date(request.GET.get('date_from', '') or '')
    date_to = parse_date(request.GET.get('date_to', '') or '')
    q = Q()
    if date_from:
        q &= Q(created_at__date__gte=date_from)
    if date_to:
        q &= Q(created_at__date__lte=date_to)
    return q


class _Echo:
    """A file-like object that returns what it's given, for streaming CSV rows."""

    def write(self, value):
        return value


def _csv_stream_response(filename, header, rows):
    writer = csv.writer(_Echo())

    def generate():
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(generate(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@require_GET
@require_auth(role='admin')
def admin_export_suppliers(request):
    """Stream a CSV of suppliers, optionally filtered by status/category/date range."""
    queryset = Supplier.objects.all().order_by('company_name')

    status = request.GET.get('status', '').strip()
    if status:
        queryset = queryset.filter(status=status)

    category = request.GET.get('category', '').strip()
    if category:
        queryset = queryset.filter(supplier_categories__category__name=category)

    queryset = queryset.filter(_parse_date_range(request)).distinct()
    queryset = queryset.prefetch_related('supplier_categories__category')

    def rows():
        for supplier in queryset.iterator(chunk_size=200):
            categories = '; '.join(sc.category.name for sc in supplier.supplier_categories.all())
            yield [
                supplier.id,
                supplier.company_name,
                supplier.business_type,
                supplier.tin,
                supplier.contact_person,
                supplier.contact_phone,
                supplier.email,
                supplier.status,
                categories,
                supplier.business_address,
                supplier.created_at.strftime('%Y-%m-%d %H:%M') if supplier.created_at else '',
            ]

    header = [
        'ID', 'Company Name', 'Business Type', 'TIN', 'Contact Person', 'Contact Phone',
        'Email', 'Status', 'Categories', 'Business Address', 'Created At',
    ]
    return _csv_stream_response('suppliers.csv', header, rows())


@require_GET
@require_auth(role='admin')
def admin_export_purchase_requests(request):
    """Stream a CSV of purchase requests, optionally filtered by status/category/date range."""
    queryset = PurchaseRequest.objects.all().order_by('-created_at')

    status = request.GET.get('status', '').strip()
    if status:
        queryset = queryset.filter(status=status)

    category = request.GET.get('category', '').strip()
    if category:
        queryset = queryset.filter(category=category)

    queryset = queryset.filter(_parse_date_range(request))

    def rows():
        for pr in queryset.iterator():
            yield [
                pr.id,
                pr.pr_no or '',
                pr.entity_name,
                pr.category or '',
                pr.office_section or '',
                pr.status,
                pr.grand_total,
                pr.requested_by or '',
                pr.date.strftime('%Y-%m-%d') if pr.date else '',
                pr.created_at.strftime('%Y-%m-%d %H:%M') if pr.created_at else '',
            ]

    header = [
        'ID', 'PR No.', 'Entity Name', 'Category', 'Office/Section', 'Status',
        'Grand Total', 'Requested By', 'PR Date', 'Created At',
    ]
    return _csv_stream_response('purchase_requests.csv', header, rows())


@csrf_exempt
def supplier_register(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

    submitted_category_ids = request.POST.getlist('category_ids')
    selected_category_ids = []
    invalid_category_ids = []
    for value in submitted_category_ids:
        try:
            category_id = int(value)
        except (TypeError, ValueError):
            invalid_category_ids.append(value)
            continue
        if category_id not in selected_category_ids:
            selected_category_ids.append(category_id)

    active_categories = {
        category.id: category
        for category in Category.objects.filter(id__in=selected_category_ids, is_active=True)
    }
    invalid_category_ids.extend(
        str(category_id) for category_id in selected_category_ids if category_id not in active_categories
    )
    selected_category_objects = [
        active_categories[category_id]
        for category_id in selected_category_ids
        if category_id in active_categories
    ]
    legacy_category_names = request.POST.getlist('categories') or request.POST.getlist('category') or []

    payload = {
        'companyName': request.POST.get('companyName', ''),
        'businessType': request.POST.get('businessType', '') or 'Sole Proprietorship',
        'businessAddress': request.POST.get('businessAddress', ''),
        'tin': request.POST.get('tin', ''),
        'contactPerson': request.POST.get('contactPerson', ''),
        'contactNumber': request.POST.get('contactNumber', ''),
        'email': request.POST.get('email', ''),
        'productsServices': request.POST.get('productsServices', ''),
        'categories': [category.name for category in selected_category_objects] if submitted_category_ids else legacy_category_names,
        'username': request.POST.get('username', ''),
        'password': request.POST.get('password', ''),
        'confirmPassword': request.POST.get('confirmPassword', ''),
    }

    business_document_key = get_required_business_document_key(payload['businessType'])
    files = {}
    for key in REQUIRED_UPLOAD_KEYS + OPTIONAL_UPLOAD_KEYS + [business_document_key] + ['additional_docs', 'otherEligibilityFiles']:
        if not key:
            continue
        uploaded = request.FILES.getlist(key)
        if uploaded:
            files[key] = uploaded[0]
        elif key == 'otherEligibilityFiles':
            files[key] = request.FILES.getlist('otherEligibilityFiles')

    errors = validate_supplier_payload(payload, files=files, categories=list(Category.objects.filter(is_active=True).values_list('name', flat=True)))
    if invalid_category_ids:
        errors.append('One or more selected supplier categories are invalid or inactive.')
    if errors:
        return JsonResponse({'success': False, 'message': 'Please correct the highlighted issues.', 'errors': errors}, status=400)

    normalized_email = payload['email'].strip().lower()
    if Supplier.objects.filter(email__iexact=normalized_email).exists():
        return JsonResponse({'success': False, 'message': 'A supplier with this email address is already registered.'}, status=409)

    categories = [sanitize_text(item) for item in payload.get('categories', []) if sanitize_text(item)]
    selected_category_names = []
    for category_name in categories:
        if category_name not in selected_category_names:
            selected_category_names.append(category_name)

    if not selected_category_names:
        return JsonResponse({'success': False, 'message': 'At least one category must be selected.'}, status=400)

    username = sanitize_text(payload.get('username', ''))
    password = payload.get('password', '') or ''
    confirm_password = payload.get('confirmPassword', '') or ''
    if username or password or confirm_password:
        if not username or not password or password != confirm_password:
            return JsonResponse({'success': False, 'message': 'Account setup details are incomplete or passwords do not match.'}, status=400)

    # Never overwrite an existing login. Reject up front (before any file is
    # persisted) if the username is already taken; the unique constraint below
    # is the final guard against a race.
    if username and User.objects.filter(username__iexact=username).exists():
        return JsonResponse({'success': False, 'message': 'This username is already taken. Please choose another.'}, status=409)

    try:
        with transaction.atomic():
            supplier = Supplier.objects.create(
                company_name=sanitize_text(payload['companyName']),
                business_type=sanitize_text(payload['businessType']) or 'Sole Proprietorship',
                business_address=sanitize_text(payload['businessAddress']),
                tin=sanitize_text(payload['tin']),
                contact_person=sanitize_text(payload['contactPerson']),
                contact_phone=sanitize_text(payload['contactNumber']),
                email=normalized_email,
                nature_of_business=sanitize_text(payload.get('natureOfBusiness', '')),
                goods_services=','.join(selected_category_names),
                products_services=sanitize_text(payload.get('productsServices', '')),
                years_in_business=int(payload.get('yearsInBusiness', '0').strip()) if str(payload.get('yearsInBusiness', '')).strip().isdigit() else None,
                status='Pending Review',
            )

            if submitted_category_ids:
                for category_obj in selected_category_objects:
                    SupplierCategory.objects.get_or_create(supplier=supplier, category=category_obj)
            else:
                for category_name in selected_category_names:
                    category_obj = Category.objects.filter(name=category_name, is_active=True).first()
                    if category_obj:
                        SupplierCategory.objects.get_or_create(supplier=supplier, category=category_obj)

            for key in REQUIRED_UPLOAD_KEYS + OPTIONAL_UPLOAD_KEYS + [business_document_key]:
                if not key:
                    continue
                uploaded = request.FILES.get(key)
                if not uploaded:
                    continue
                stored_path = _save_supplier_upload(uploaded)
                SupplierDocument.objects.create(
                    supplier=supplier,
                    doc_type=key,
                    filename=stored_path,
                    original_name=uploaded.name,
                )

            additional_doc_names = request.POST.getlist('additionalDocNames')
            uploaded_additional_files = request.FILES.getlist('additionalFiles')
            for index, file_obj in enumerate(uploaded_additional_files):
                filename = _save_supplier_upload(file_obj)
                doc_name = sanitize_text(additional_doc_names[index]) if index < len(additional_doc_names) else file_obj.name
                SupplierDocument.objects.create(
                    supplier=supplier,
                    doc_type='other_eligibility_requirement',
                    filename=filename,
                    original_name=doc_name,
                )

            if username:
                role = Role.objects.get_or_create(name='supplier')[0]
                User.objects.create(
                    username=username,
                    password_hash=hash_password(password),
                    full_name=sanitize_text(payload.get('contactPerson', '')),
                    role=role,
                    is_active=True,
                )
    except IntegrityError:
        return JsonResponse({'success': False, 'message': 'This username is already taken. Please choose another.'}, status=409)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': 'Failed to save supplier registration.', 'error': str(exc)}, status=500)

    return JsonResponse({'success': True, 'id': supplier.id, 'message': 'Supplier registration submitted successfully. It is now pending review.'}, status=201)


@csrf_exempt
@require_http_methods(["PATCH"])
@require_auth(role='admin')
def supplier_update_status(request, supplier_id: int):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return json_error('Invalid JSON payload', 400)

    status = str(payload.get('status') or '').strip()
    allowed_statuses = {'Pending Review', 'Under Review', 'For Compliance', 'Approved', 'Rejected'}
    if status not in allowed_statuses:
        return json_error('Invalid supplier status', 400)

    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return json_error('Supplier not found', 404)

    remarks = str(payload.get('remarks') or '').strip()
    if status in {'Rejected', 'For Compliance'} and not remarks:
        return json_error('Remarks are required for this decision.', 400)

    was_approved = supplier.status == 'Approved'
    supplier.status = status
    supplier.review_remarks = remarks
    supplier.save(update_fields=['status', 'review_remarks', 'updated_at'])

    document_status_updates = payload.get('document_statuses') or {}
    for document_id, document_status in document_status_updates.items():
        try:
            document = supplier.documents.get(id=document_id)
        except SupplierDocument.DoesNotExist:
            continue
        if str(document_status).strip() in {'Pending', 'Verified', 'Rejected'}:
            document.verification_status = str(document_status).strip()
            document.save(update_fields=['verification_status'])

    if status == 'Approved' and not was_approved:
        Notification.objects.create(
            supplier=supplier,
            notification_type=Notification.TYPE_PROFILE_APPROVED,
            title='Supplier Profile Approved',
            message='Your supplier profile has been approved by the BAC admin.',
        )

    documents = [
        {
            'id': doc.id,
            'doc_type': doc.doc_type,
            'verification_status': doc.verification_status,
        }
        for doc in supplier.documents.order_by('-uploaded_at')
    ]
    return JsonResponse({
        'success': True,
        'id': supplier.id,
        'status': supplier.status,
        'remarks': supplier.review_remarks,
        'documents': documents,
    })


def _supplier_login_accounts(supplier):
    """User logins that can sign in as this supplier.

    There is no FK between Supplier and User, so this mirrors the loose match
    used by ``login_view`` (username contained in the supplier email, or the
    account full name equal to the supplier contact person).
    """
    email = (supplier.email or '').strip().lower()
    contact = (supplier.contact_person or '').strip().lower()
    matched_ids = []
    for account in User.objects.filter(role__name='supplier'):
        username = (account.username or '').strip().lower()
        full_name = (account.full_name or '').strip().lower()
        if (email and username and username in email) or (contact and full_name and full_name == contact):
            matched_ids.append(account.id)
    return User.objects.filter(id__in=matched_ids)


@csrf_exempt
@require_http_methods(["DELETE"])
@require_auth(role='admin')
def supplier_delete(request, supplier_id: int):
    """Permanently remove a supplier and everything attached to it.

    Cascades to SupplierCategory, SupplierDocument, Quotation, Notification and
    RFQ rows, and also deletes the supplier's login account(s).
    """
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return json_error('Supplier not found', 404)

    with transaction.atomic():
        _supplier_login_accounts(supplier).delete()
        supplier.delete()

    return JsonResponse({'success': True, 'id': supplier_id})


# ─── SUPPLIER PORTAL ENDPOINTS ──────────────────────────────────────────────────

@require_GET
@require_auth(role='supplier', owner_param='supplier_id')
def supplier_matching_opportunities(request, supplier_id):
    """Get all Purchase Requests matching supplier's registered categories."""
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)

    if supplier.status != 'Approved':
        return JsonResponse({'opportunities': []})

    required_document_keys = set(REQUIRED_UPLOAD_KEYS)
    business_key = get_required_business_document_key(supplier.business_type)
    if business_key:
        required_document_keys.add(business_key)
    verified_documents = set(
        supplier.documents.filter(verification_status='Verified').values_list('doc_type', flat=True)
    )
    if required_document_keys - verified_documents:
        return JsonResponse({'opportunities': []})

    supplier_category_ids = set(
        SupplierCategory.objects.filter(supplier=supplier, category__is_active=True).values_list('category_id', flat=True)
    )
    if not supplier_category_ids:
        return JsonResponse({'opportunities': []})

    # Get all approved/matched PRs with assigned categories
    prs = PurchaseRequest.objects.filter(
        status__in=['matched', 'approved']
    ).prefetch_related('line_items', 'quotations')

    matching_opportunities = []

    for pr in prs:
        # Resolve reviewed item category names to the active Category master.
        pr_category_ids = set()
        pr_categories = set()
        for item in pr.line_items.all():
            if item.category:
                category = Category.objects.filter(name=item.category, is_active=True).first()
                if category:
                    pr_category_ids.add(category.id)
                    pr_categories.add(category.name)

        if not supplier_category_ids.intersection(pr_category_ids):
            continue

        # Check if supplier already submitted quotation.
        existing_quotation = pr.quotations.filter(supplier=supplier).first()
        quotation_status = existing_quotation.status if existing_quotation else None

        matching_opportunities.append({
            'id': pr.id,
            'pr_no': pr.pr_no,
            'entity_name': pr.entity_name,
            'office_section': pr.office_section,
            'purpose': pr.purpose,
            'category': pr.category or ', '.join(pr_categories),
            'grand_total': float(pr.grand_total),
            'status': pr.status,
            'created_at': pr.created_at.isoformat(),
            'quotation_status': quotation_status,
            'items_count': pr.line_items.count(),
        })

    return JsonResponse({'opportunities': matching_opportunities})


@require_GET
@require_auth(role='supplier', owner_param='supplier_id')
def supplier_dashboard_summary(request, supplier_id):
    """Get summary data for supplier dashboard."""
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)

    supplier_category_ids = set(
        SupplierCategory.objects.filter(supplier=supplier, category__is_active=True).values_list('category_id', flat=True)
    )

    prs = PurchaseRequest.objects.filter(
        status__in=['matched', 'approved']
    ).prefetch_related('line_items', 'quotations')

    matching_count = 0
    for pr in prs:
        pr_category_ids = set()
        for item in pr.line_items.all():
            if item.category:
                category = Category.objects.filter(name=item.category, is_active=True).first()
                if category:
                    pr_category_ids.add(category.id)

        if supplier_category_ids.intersection(pr_category_ids):
            matching_count += 1

    quotations = Quotation.objects.filter(supplier=supplier)

    summary = {
        'company_name': supplier.company_name,
        'verification_status': supplier.status,
        'registered_categories': (supplier.goods_services or 'Not specified').split(',')[0],
        'open_opportunities': matching_count,
        'submitted_quotations': quotations.filter(status__in=['submitted', 'under_review', 'awarded', 'rejected']).count(),
        'awarded_quotations': quotations.filter(status='awarded').count(),
        'pending_quotations': quotations.filter(status='under_review').count(),
        'rejected_quotations': quotations.filter(status='rejected').count(),
        'unread_notifications': Notification.objects.filter(supplier=supplier, is_read=False).count(),
    }

    return JsonResponse(summary)


@csrf_exempt
@require_http_methods(['POST'])
@require_auth(role='supplier', owner_param='supplier_id')
def quotation_attachment_upload(request, supplier_id, quotation_id):
    try:
        quotation = Quotation.objects.get(id=quotation_id, supplier_id=supplier_id)
    except Quotation.DoesNotExist:
        return JsonResponse({'error': 'Quotation not found'}, status=404)
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': 'A PDF quotation file is required'}, status=400)
    try:
        validate_upload(uploaded, UploadKind.COMPLETED_RFQ)
    except FileValidationError as exc:
        return JsonResponse({'error': exc.message}, status=400)
    filename = _save_supplier_upload(uploaded)
    quotation.attachment_filename = filename
    quotation.save(update_fields=['attachment_filename', 'updated_at'])
    return JsonResponse({'success': True, 'attachment_filename': filename,
        'attachment_url': request.build_absolute_uri(f'/uploads/{filename}')})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
@require_auth(role='supplier', owner_param='supplier_id')
def supplier_quotations(request, supplier_id):
    """Get supplier's quotations or submit a new quotation."""
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)

    if request.method == 'GET':
        quotations = Quotation.objects.filter(supplier=supplier).select_related('purchase_request')
        quotation_list = []
        for q in quotations:
            quotation_list.append({
                'id': q.id,
                'pr_no': q.purchase_request.pr_no,
                'pr_id': q.purchase_request.id,
                'quoted_amount': float(q.quoted_amount),
                'estimated_delivery_days': q.estimated_delivery_days,
                'warranty_months': q.warranty_months,
                'remarks': q.remarks,
                'attachment_filename': q.attachment_filename,
                'attachment_url': request.build_absolute_uri(f'/uploads/{q.attachment_filename}') if q.attachment_filename else '',
                'status': q.status,
                'created_at': q.created_at.isoformat(),
                'updated_at': q.updated_at.isoformat(),
            })
        return JsonResponse({'quotations': quotation_list})

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            pr_id = data.get('purchase_request_id')
            rfq_id = data.get('rfq_id')
            quoted_amount = data.get('quoted_amount')
            estimated_delivery_days = data.get('estimated_delivery_days')
            warranty_months = data.get('warranty_months')
            remarks = data.get('remarks', '')

            if not pr_id or not quoted_amount:
                return JsonResponse({
                    'error': 'Missing required fields: purchase_request_id, quoted_amount'
                }, status=400)

            try:
                pr = PurchaseRequest.objects.get(id=pr_id)
            except PurchaseRequest.DoesNotExist:
                return JsonResponse({'error': 'Purchase Request not found'}, status=404)

            rfq = RFQ.objects.filter(id=rfq_id, supplier=supplier, purchase_request=pr, status=RFQ.STATUS_SENT).first() if rfq_id else None
            if rfq_id and not rfq:
                return JsonResponse({'error': 'RFQ not found or no longer accepting quotations'}, status=400)

            # Check if quotation already exists
            existing = Quotation.objects.filter(supplier=supplier, purchase_request=pr).first()
            if existing and existing.status != 'draft':
                return JsonResponse({
                    'error': f'Quotation already {existing.status} for this PR'
                }, status=400)

            if existing:
                # Update existing draft
                existing.quoted_amount = quoted_amount
                existing.estimated_delivery_days = estimated_delivery_days
                existing.warranty_months = warranty_months
                existing.remarks = remarks
                if rfq:
                    existing.rfq = rfq
                existing.status = 'submitted'
                existing.save()
                quotation = existing
            else:
                # Create new quotation
                quotation = Quotation.objects.create(
                    supplier=supplier,
                    purchase_request=pr,
                    rfq=rfq,
                    quoted_amount=quoted_amount,
                    estimated_delivery_days=estimated_delivery_days,
                    warranty_months=warranty_months,
                    remarks=remarks,
                    status='submitted'
                )

            if rfq:
                rfq.status = RFQ.STATUS_QUOTATION_RECEIVED
                rfq.save(update_fields=['status', 'updated_at'])

            # Create notification
            Notification.objects.create(
                supplier=supplier,
                notification_type=Notification.TYPE_QUOTATION_SUBMITTED,
                title='Quotation Submitted',
                message=f'Your quotation for PR {pr.pr_no} has been submitted successfully.',
                related_pr_id=pr.id,
                related_quotation_id=quotation.id
            )

            return JsonResponse({
                'success': True,
                'quotation_id': quotation.id,
                'message': 'Quotation submitted successfully'
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@require_GET
@require_auth(role='supplier', owner_param='supplier_id')
def supplier_notifications(request, supplier_id):
    """Get supplier's notifications."""
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)

    notifications = Notification.objects.filter(supplier=supplier)[:50]
    notification_list = []
    for n in notifications:
        notification_list.append({
            'id': n.id,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'related_pr_id': n.related_pr_id,
            'related_rfq_id': n.related_rfq_id,
            'created_at': n.created_at.isoformat(),
        })

    return JsonResponse({'notifications': notification_list})


@require_POST
@require_auth(role='supplier')
def supplier_mark_notification_read(request, notification_id):
    """Mark a notification as read.

    ``notification_id`` alone doesn't carry a ``supplier_id`` for the
    ``owner_param`` check on the decorator, so ownership is verified here
    instead - a supplier may only mark their own notifications read.
    """
    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)
    if notification.supplier_id != request.auth_supplier_id:
        return JsonResponse({'error': 'You do not have permission to access this notification.'}, status=403)
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True})


@require_http_methods(['GET', 'PATCH'])
@require_auth(role='supplier', owner_param='supplier_id')
def supplier_profile(request, supplier_id):
    """Get or update supplier profile."""
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)

    if request.method == 'GET':
        documents = [
            {
                'id': doc.id,
                'doc_type': doc.doc_type,
                'original_name': doc.original_name,
                'filename': doc.filename,
                'verification_status': doc.verification_status,
                'uploaded_at': doc.uploaded_at.isoformat(),
                'file_url': request.build_absolute_uri(f'/uploads/{doc.filename}'),
            }
            for doc in supplier.documents.order_by('-uploaded_at')
        ]
        categories = list(
            SupplierCategory.objects.filter(supplier=supplier).select_related('category').values_list('category__name', flat=True)
        )
        category_ids = list(
            SupplierCategory.objects.filter(supplier=supplier).values_list('category_id', flat=True)
        )
        return JsonResponse({
            'id': supplier.id,
            'company_name': supplier.company_name,
            'business_type': supplier.business_type,
            'business_address': supplier.business_address,
            'tin': supplier.tin,
            'contact_person': supplier.contact_person,
            'contact_phone': supplier.contact_phone,
            'nature_of_business': supplier.nature_of_business,
            'goods_services': supplier.goods_services,
            'products_services': supplier.products_services,
            'years_in_business': supplier.years_in_business,
            'email': supplier.email,
            'status': supplier.status,
            'review_remarks': supplier.review_remarks,
            'categories': categories,
            'category_ids': category_ids,
            'created_at': supplier.created_at.isoformat(),
            'documents': documents,
        })

    elif request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            selected_categories = None
            if 'category_ids' in data:
                category_ids = data.get('category_ids')
                if not isinstance(category_ids, list):
                    return JsonResponse({'error': 'category_ids must be a list'}, status=400)
                try:
                    normalized_ids = list(dict.fromkeys(int(category_id) for category_id in category_ids))
                except (TypeError, ValueError):
                    return JsonResponse({'error': 'Category IDs must be valid integers'}, status=400)
                selected_categories = list(Category.objects.filter(id__in=normalized_ids, is_active=True))
                if len(selected_categories) != len(normalized_ids):
                    return JsonResponse({'error': 'One or more selected categories are invalid or inactive'}, status=400)

            # Only allow updating specific fields
            allowed_fields = [
                'company_name', 'business_address', 'tin', 'contact_person',
                'contact_phone', 'email', 'nature_of_business', 'goods_services', 'business_type'
            ]

            for field in allowed_fields:
                if field in data:
                    setattr(supplier, field, data[field])

            with transaction.atomic():
                supplier.save()
                if selected_categories is not None:
                    selected_ids = [category.id for category in selected_categories]
                    SupplierCategory.objects.filter(supplier=supplier).exclude(category_id__in=selected_ids).delete()
                    for category in selected_categories:
                        SupplierCategory.objects.get_or_create(supplier=supplier, category=category)

            updated_categories = list(
                SupplierCategory.objects.filter(supplier=supplier).select_related('category').values_list('category__name', flat=True)
            )
            return JsonResponse({'success': True, 'supplier': {
                'id': supplier.id,
                'company_name': supplier.company_name,
                'business_address': supplier.business_address,
                'tin': supplier.tin,
                'contact_person': supplier.contact_person,
                'contact_phone': supplier.contact_phone,
                'nature_of_business': supplier.nature_of_business,
                'goods_services': supplier.goods_services,
                'email': supplier.email,
                'categories': updated_categories,
                'category_ids': list(SupplierCategory.objects.filter(supplier=supplier).values_list('category_id', flat=True)),
            }})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@require_POST
@require_auth(role='supplier', owner_param='supplier_id')
def supplier_resubmit_document(request, supplier_id):
    """Store a replacement supplier document for BAC verification."""
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)

    document_type = str(request.POST.get('doc_type') or '').strip()
    uploaded = request.FILES.get('file')
    if not document_type or not uploaded:
        return JsonResponse({'error': 'Document type and file are required'}, status=400)
    try:
        validate_upload(uploaded, UploadKind.SUPPLIER_REQUIREMENT)
    except FileValidationError as exc:
        return JsonResponse({'error': exc.message}, status=400)

    filename = _save_supplier_upload(uploaded)
    document = SupplierDocument.objects.create(
        supplier=supplier,
        doc_type=document_type,
        filename=filename,
        original_name=uploaded.name,
        verification_status='Pending',
    )
    # A replacement document must send the supplier account back through BAC review.
    if supplier.status == 'For Compliance':
        supplier.status = 'Pending Review'
        supplier.save(update_fields=['status'])
    return JsonResponse({'success': True, 'supplier_status': supplier.status, 'document': {
        'id': document.id, 'doc_type': document.doc_type,
        'filename': document.filename, 'original_name': document.original_name,
        'verification_status': document.verification_status,
        'uploaded_at': document.uploaded_at.isoformat(),
        'file_url': request.build_absolute_uri(f'/uploads/{document.filename}'),
    }})


@require_GET
@require_auth()
def purchase_request_details(request, pr_id):
    """Get detailed information about a Purchase Request.

    Quotations are commercially sensitive - a supplier competing on this PR
    must never see another supplier's bid. Only an admin (BAC Secretariat)
    sees every quotation; a supplier sees only their own, and a buyer sees
    none (buyers never see supplier identities or quotations, matching the
    rest of the buyer-facing API - see ``_buyer_pr_stage``).
    """
    try:
        pr = PurchaseRequest.objects.get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return JsonResponse({'error': 'Purchase Request not found'}, status=404)

    items = []
    for item in pr.line_items.all():
        items.append({
            'id': item.id,
            'stock_property_no': item.stock_property_no,
            'item_description': item.item_description,
            'quantity': float(item.quantity),
            'unit': item.unit,
            'unit_cost': float(item.unit_cost),
            'total_cost': float(item.total_cost),
            'category': item.category,
        })

    all_quotations = pr.quotations.select_related('supplier').all()
    if request.auth_role == 'admin':
        visible_quotations = all_quotations
    elif request.auth_role == 'supplier':
        visible_quotations = [q for q in all_quotations if q.supplier_id == request.auth_supplier_id]
    else:
        visible_quotations = []

    quotations = [{
        'id': q.id, 'supplier_id': q.supplier_id,
        'supplier_name': q.supplier.company_name,
        'quoted_amount': float(q.quoted_amount), 'status': q.status,
        'attachment_filename': q.attachment_filename,
        'attachment_url': request.build_absolute_uri(f'/uploads/{q.attachment_filename}') if q.attachment_filename else '',
    } for q in visible_quotations]

    return JsonResponse({
        'id': pr.id,
        'pr_no': pr.pr_no,
        'source_filename': pr.source_filename,
        'source_file_url': request.build_absolute_uri(f'/uploads/{pr.source_filename}') if pr.source_filename else '',
        'entity_name': pr.entity_name,
        'fund_cluster': pr.fund_cluster,
        'office_section': pr.office_section,
        'responsibility_center_code': pr.responsibility_center_code,
        'date': pr.date.isoformat() if pr.date else '',
        'purpose': pr.purpose,
        'requested_by': pr.requested_by,
        'funds_available_by': pr.funds_available_by,
        'approved_by': pr.approved_by,
        'twg_verified_by': pr.twg_verified_by,
        'category': pr.category,
        'grand_total': float(pr.grand_total),
        'status': pr.status,
        'created_at': pr.created_at.isoformat(),
        'items': items,
        'quotations': quotations,
    })


@csrf_exempt
@require_POST
def verify_recaptcha(request):
    return JsonResponse({'success': True})


# ─── PR Item Category Assignment ─────────────────────────────────────────────

@require_GET
@require_auth(role='admin')
def pr_items_view(request, pr_id):
    """Return all line items for a given Purchase Request."""
    try:
        PurchaseRequest.objects.get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)
    items = list(
        PurchaseRequestItem.objects
        .filter(purchase_request_id=pr_id)
        .values('id', 'item_description', 'quantity', 'unit_cost', 'total_cost',
                'unit', 'stock_property_no', 'category')
    )
    return JsonResponse(items, safe=False)


@csrf_exempt
@require_POST
@require_auth(role='admin')
def pr_items_assign_categories(request, pr_id):
    """Save the selected category for each Purchase Request item."""
    try:
        pr = PurchaseRequest.objects.get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return json_error('Invalid JSON payload', 400)

    assignments = data.get('assignments', [])
    if not isinstance(assignments, list):
        return json_error('assignments must be a list', 400)

    with transaction.atomic():
        for a in assignments:
            item_id = a.get('item_id')
            category = str(a.get('category') or '').strip() or None
            if item_id:
                PurchaseRequestItem.objects.filter(
                    id=item_id, purchase_request_id=pr_id
                ).update(category=category)

        assigned_categories = list(
            PurchaseRequestItem.objects
            .filter(purchase_request_id=pr_id)
            .exclude(category__isnull=True)
            .exclude(category='')
            .values_list('category', flat=True)
            .distinct()
        )
        pr.category = ', '.join(assigned_categories) or None
        all_items_categorized = (
            pr.line_items.exists()
            and not pr.line_items.filter(category__isnull=True).exists()
            and not pr.line_items.filter(category='').exists()
        )
        pr.status = PurchaseRequest.STATUS_MATCHED if all_items_categorized else PurchaseRequest.STATUS_IN_REVIEW
        pr.save(update_fields=['category', 'status'])

    return JsonResponse({'success': True, 'category': pr.category or '', 'status': pr.status})


def _item_brief(item):
    return {
        'id': item.id,
        'item_description': item.item_description or '',
        'quantity': float(item.quantity or 0),
        'unit': item.unit or '',
        'unit_cost': float(item.unit_cost or 0),
        'total_cost': float(item.total_cost or 0),
        'category': item.category or '',
    }


@require_GET
@require_auth(role='admin')
def pr_supplier_match(request, pr_id):
    """Category-grouped supplier matching for a Purchase Request.

    A mixed-category PR is split into one procurement group per distinct item
    category. Each group carries its own items and its own category-matched
    suppliers; items with no category are returned separately and belong to no
    group until the BAC assigns one.

    A supplier is category-matched for a group only when it is registered under
    that group's category, is approved, and every registration compliance
    document required for its business type has been verified by BAC.
    """
    try:
        pr = PurchaseRequest.objects.get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)

    all_items = list(PurchaseRequestItem.objects.filter(purchase_request_id=pr_id).order_by('id'))
    uncategorized = [i for i in all_items if not (i.category or '').strip()]

    # Group items by category name. Category.name is unique, so the name is a
    # stable group key; resolve the id where a Category row exists (task 25).
    grouped = {}
    for item in all_items:
        name = (item.category or '').strip()
        if not name:
            continue
        grouped.setdefault(name, []).append(item)

    category_ids = dict(
        Category.objects.filter(name__in=list(grouped)).values_list('name', 'id')
    )
    category_names = sorted(grouped)

    # Compliance profile for every approved supplier registered under any of the
    # PR's group categories - computed once, reused per group.
    candidate_ids = set(
        SupplierCategory.objects
        .filter(category__name__in=category_names, supplier__status='Approved')
        .values_list('supplier_id', flat=True)
    )
    suppliers_by_id = {
        s.id: s for s in Supplier.objects.filter(id__in=candidate_ids)
    }
    required_document_keys = set(REQUIRED_UPLOAD_KEYS)
    compliance_by_id = {}
    for supplier in suppliers_by_id.values():
        required_keys = set(required_document_keys)
        business_key = get_required_business_document_key(supplier.business_type)
        if business_key:
            required_keys.add(business_key)
        verified_documents = set(
            supplier.documents.filter(verification_status='Verified')
            .values_list('doc_type', flat=True)
        )
        missing_documents = sorted(required_keys - verified_documents)
        compliance_by_id[supplier.id] = {
            'eligible': not missing_documents,
            'missing_documents': missing_documents,
            'required_documents': sorted(required_keys),
            'compliance_percentage': round(((len(required_keys) - len(missing_documents)) / len(required_keys)) * 100) if required_keys else 100,
        }

    groups = []
    for name in category_names:
        cat_supplier_ids = set(
            SupplierCategory.objects.filter(category__name=name)
            .values_list('supplier_id', flat=True)
        )
        matched = []
        for supplier_id in cat_supplier_ids:
            supplier = suppliers_by_id.get(supplier_id)
            compliance = compliance_by_id.get(supplier_id)
            if not supplier or not compliance or not compliance['eligible']:
                continue
            matched.append({
                'id': supplier.id,
                'company_name': supplier.company_name,
                'tin': supplier.tin,
                'email': supplier.email,
                'contact_person': supplier.contact_person,
                'contact_phone': supplier.contact_phone,
                'business_address': supplier.business_address,
                'goods_services': supplier.goods_services,
                'nature_of_business': supplier.nature_of_business,
                'business_type': supplier.business_type,
                'status': supplier.status,
                'match_score': 1,
                'category_match': True,
                'compliance_status': 'Eligible',
                **compliance,
            })
        matched.sort(key=lambda s: s['company_name'].lower())
        group_items = grouped[name]
        groups.append({
            'category': name,
            'category_id': category_ids.get(name),
            'item_count': len(group_items),
            'items': [_item_brief(i) for i in group_items],
            'suppliers': matched,
            'eligibility_rule': 'Approved supplier with all required compliance documents verified',
        })

    return JsonResponse({
        'pr': {
            'id': pr.id,
            'pr_no': pr.pr_no,
            'entity_name': pr.entity_name,
            'office_section': pr.office_section or '',
            'date': pr.date.isoformat() if pr.date else '',
            'purpose': pr.purpose or '',
            'category': pr.category or '',
            'grand_total': float(pr.grand_total or 0),
        },
        'item_count': len(all_items),
        'category_count': len(category_names),
        'groups': groups,
        'uncategorized_items': [_item_brief(i) for i in uncategorized],
    })


@require_GET
@require_auth(role='admin')
def pr_unmatched_list(request):
    """Return existing PRs that do not yet have a supplier quotation."""
    prs = (
        PurchaseRequest.objects
        .filter(quotations__isnull=True)
        .prefetch_related('line_items')
        .order_by('-created_at')
        .distinct()
    )
    result = []
    for pr in prs:
        categories = sorted({item.category for item in pr.line_items.all() if item.category})
        result.append({
            'id': pr.id,
            'pr_no': pr.pr_no,
            'date': pr.date.isoformat() if pr.date else None,
            'entity_name': pr.entity_name,
            'office_section': pr.office_section,
            'category': pr.category or ', '.join(categories),
            'purpose': pr.purpose,
            'status': pr.status,
            'grand_total': float(pr.grand_total),
            'items_count': pr.line_items.count(),
        })
    return JsonResponse(result, safe=False)


# Supplier-facing labels for the RFQ lifecycle. Reuses the existing status
# values (draft / sent / quotation_received / completed) - no parallel system.
RFQ_STATUS_LABELS = {
    RFQ.STATUS_DRAFT: 'Draft',
    RFQ.STATUS_SENT: 'Awaiting Supplier Response',
    RFQ.STATUS_QUOTATION_RECEIVED: 'Response Submitted',
    RFQ.STATUS_COMPLETED: 'Completed',
}


def _pr_rfq_progress_status(sent, received):
    """PR-level RFQ progress derived from issued vs. responded counts."""
    if sent <= 0:
        return 'no_rfqs'
    if received <= 0:
        return 'awaiting_responses'
    if received < sent:
        return 'responses_in_progress'
    return 'all_responses_received'


def _rfq_payload(rfq, request):
    pr = rfq.purchase_request
    # This RFQ's own items - the category group it covers, not the whole PR.
    # Legacy RFQs with no linked items fall back to every PR item.
    linked = list(
        rfq.rfq_items.select_related('purchase_request_item').order_by('purchase_request_item_id')
    )
    source_items = [li.purchase_request_item for li in linked] if linked else list(pr.line_items.all())
    items = [{
        'id': item.id,
        'item_description': item.item_description,
        'quantity': float(item.quantity),
        'unit': item.unit or '',
        'unit_cost': float(item.unit_cost or 0),
        'total_cost': float(item.total_cost or 0),
        'category': item.category or '',
    } for item in source_items]
    pdf_url = ''
    if rfq.pdf_file:
        pdf_url = request.build_absolute_uri(f'/uploads/{rfq.pdf_file}')
    submitted_pdf_url = ''
    submitted_filename = ''
    if rfq.submitted_pdf:
        submitted_pdf_url = request.build_absolute_uri(f'/uploads/{rfq.submitted_pdf}')
        # Stored as "<uuid hex>_<original name>" - show the supplier's own name.
        stored_name = Path(rfq.submitted_pdf).name
        submitted_filename = re.sub(r'^[0-9a-f]{32}_', '', stored_name) or stored_name
    abc_value = rfq.abc or (f"₱{float(pr.grand_total or 0):,.2f}" if pr.grand_total else '₱0.00')
    return {
        'id': rfq.id,
        'rfq_no': rfq.rfq_no or '',
        'status': rfq.status,
        'status_label': RFQ_STATUS_LABELS.get(rfq.status, rfq.get_status_display()),
        'selection_type': rfq.selection_type,
        'selection_type_label': rfq.get_selection_type_display(),
        # The procurement category group this RFQ serves.
        'category': rfq.category.name if rfq.category_id else (rfq.purchase_request.category or ''),
        'category_id': rfq.category_id,
        'item_count': len(items),
        'subject': rfq.subject,
        'message': rfq.message,
        'abc': abc_value,
        # The RFQ number is the quotation number - one shared RFQ-YYYY-NNNN
        # sequence across registered and manual RFQs (see _rfq_number). Blank
        # until the RFQ is issued.
        'quotation_no': rfq.rfq_no or '',
        'mode_of_procurement': normalize_procurement_mode(rfq.mode_of_procurement),
        'quotation_basis': rfq.quotation_basis or RFQ.QUOTATION_BASIS_LOT,
        'additional_notes': rfq.additional_notes,
        'pdf_file': rfq.pdf_file,
        'pdf_url': pdf_url,
        # Generated RFQ (BAC -> supplier); alias kept for clarity in new UI.
        'generated_pdf_url': pdf_url,
        # Completed RFQ uploaded by the supplier.
        'submitted_pdf_url': submitted_pdf_url,
        'submitted_filename': submitted_filename,
        'submitted_at': rfq.submitted_at.isoformat() if rfq.submitted_at else None,
        'has_response': bool(rfq.submitted_pdf),
        'created_at': rfq.created_at.isoformat(),
        'sent_at': rfq.sent_at.isoformat() if rfq.sent_at else None,
        'delivery_method': rfq.delivery_method,
        'is_manual': rfq.is_manual,
        'supplier_type': 'manual' if rfq.is_manual else 'registered',
        'supplier_name': rfq.supplier_display_name,
        'manual_supplier_name': rfq.manual_supplier_name,
        'created_by': rfq.created_by.username if rfq.created_by_id else '',
        'purchase_request': {
            'id': pr.id,
            'pr_no': pr.pr_no,
            'date': pr.date.isoformat() if pr.date else '',
            'entity_name': pr.entity_name,
            'office_section': pr.office_section or '',
            'purpose': pr.purpose or '',
            'category': pr.category or '',
            'items': items,
        },
        'supplier': {
            'id': rfq.supplier.id,
            'company_name': rfq.supplier.company_name,
            'business_address': rfq.supplier.business_address,
            'tin': rfq.supplier.tin,
            'contact_person': rfq.supplier.contact_person,
            'contact_phone': rfq.supplier.contact_phone,
            'email': rfq.supplier.email,
        } if rfq.supplier_id else {
            'id': None,
            'company_name': rfq.manual_supplier_name,
            'business_address': '', 'tin': '', 'contact_person': '',
            'contact_phone': '', 'email': '',
        },
    }


def _rfq_number(today=None, lock=False):
    """Next ``RFQ-YYYY-NNNN`` number - the single sequence every RFQ draws from.

    Registered-supplier and manual / unregistered-supplier RFQs share this one
    counter, so a manual RFQ issued after ``RFQ-2026-0002`` becomes
    ``RFQ-2026-0003``. The next value follows the highest number already
    generated for the year (scan of existing ``rfq_no`` values), so a deleted
    draft never causes a collision. This number is also what prints on the RFQ
    as the Quotation No.
    """
    today = today or timezone.localdate()
    year = f'{today:%Y}'
    if lock:
        # Advisory-lock row (see next_pr_number) serialises concurrent issuance.
        PRNumberSequence.objects.get_or_create(key='rfq')
        PRNumberSequence.objects.select_for_update().filter(key='rfq').first()

    highest = 0
    for value in RFQ.objects.values_list('rfq_no', flat=True):
        match = _RFQ_NUMBER_RE.fullmatch((value or '').strip())
        if match and match.group(1) == year:
            highest = max(highest, int(match.group(2)))
    return f'RFQ-{year}-{highest + 1:04d}'


@require_GET
@require_auth(role='admin')
def procurement_modes_view(request):
    """Suggested procurement modes offered on the RFQ preparation form.

    These populate the field's autocomplete list; an admin may also type a mode
    that is not listed here.
    """
    return JsonResponse({'modes': procurement_mode_choices()})


def _format_peso(amount) -> str:
    return f"₱{float(amount or 0):,.2f}"


def _resolve_rfq_group(pr, payload):
    """Resolve the procurement category group an RFQ request targets.

    Returns ``(category, items, error_response)``:
      * ``category``  - the ``Category`` row the group belongs to
      * ``items``     - the PR's ``PurchaseRequestItem`` rows in that category
                        (optionally narrowed to a validated ``item_ids`` subset)
      * ``error_response`` - a ``JsonResponse`` to return instead, or ``None``

    Enforces item/category consistency (task 15/16/37): every returned item
    belongs to this PR and to the requested category.
    """
    pr_items = list(pr.line_items.all())
    distinct = sorted({(i.category or '').strip() for i in pr_items if (i.category or '').strip()})

    name = str(payload.get('category') or payload.get('category_name') or '').strip()
    if not name:
        if len(distinct) == 1:
            # A single-category PR needs no explicit group.
            name = distinct[0]
        elif not distinct:
            # Legacy / not-yet-categorised PR: no grouping possible - the RFQ
            # covers every item, exactly as before category grouping existed.
            return None, list(pr_items), None
        else:
            return None, None, json_error(
                'This Purchase Request spans multiple procurement categories - select the category group for this RFQ.',
                400,
            )

    category = Category.objects.filter(name=name).first()
    if category is None:
        return None, None, json_error(f'Unknown procurement category "{name}".', 400)

    group_items = [i for i in pr_items if (i.category or '').strip() == name]
    if not group_items:
        return None, None, json_error('No items on this Purchase Request belong to that category.', 400)

    raw_ids = payload.get('item_ids')
    if raw_ids:
        try:
            wanted = {int(x) for x in raw_ids}
        except (TypeError, ValueError):
            return None, None, json_error('item_ids must be a list of item IDs.', 400)
        group_ids = {i.id for i in group_items}
        if not wanted.issubset(group_ids):
            return None, None, json_error(
                'One or more selected items do not belong to this Purchase Request and category.', 400
            )
        group_items = [i for i in group_items if i.id in wanted]

    return category, group_items, None


def _sync_rfq_items(rfq, items):
    """Make ``rfq.rfq_items`` exactly the given PurchaseRequestItem set."""
    wanted_ids = {i.id for i in items}
    existing_ids = set(
        rfq.rfq_items.values_list('purchase_request_item_id', flat=True)
    )
    to_add = wanted_ids - existing_ids
    to_remove = existing_ids - wanted_ids
    if to_remove:
        rfq.rfq_items.filter(purchase_request_item_id__in=to_remove).delete()
    if to_add:
        RFQItem.objects.bulk_create(
            [RFQItem(rfq=rfq, purchase_request_item_id=item_id) for item_id in to_add],
            ignore_conflicts=True,
        )


@csrf_exempt
@require_http_methods(['GET', 'POST', 'PATCH'])
@require_auth(role='admin')
def admin_rfq(request, pr_id):
    try:
        pr = PurchaseRequest.objects.prefetch_related('line_items').get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)

    if request.method == 'GET':
        rfqs = (
            RFQ.objects.filter(purchase_request=pr)
            .select_related('supplier', 'category')
            .prefetch_related('rfq_items__purchase_request_item')
        )
        return JsonResponse({'rfqs': [_rfq_payload(rfq, request) for rfq in rfqs]})

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, json.JSONDecodeError):
        return json_error('Invalid JSON payload', 400)

    supplier_id = payload.get('supplier_id')
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except (Supplier.DoesNotExist, TypeError, ValueError):
        return json_error('Supplier not found', 404)

    # Mandatory supplier restriction - enforced for BOTH the normal path and a
    # manual BAC selection. Manual selection only ever bypasses the CATEGORY
    # match requirement, never the approval/active-status rule.
    if supplier.status != 'Approved':
        return json_error('Supplier is not eligible because the supplier is not approved.', 400)

    # A manual BAC selection is a deliberate override recorded for audit. The
    # whole endpoint is admin-only (see decorator), so no separate check is
    # needed here beyond identifying the selection type.
    is_manual_selection = (
        str(payload.get('selection_type') or '').strip() == RFQ.SELECTION_MANUAL_BAC
        or bool(payload.get('manual_selection'))
    )

    # Resolve the procurement category group this RFQ serves and the exact PR
    # items it covers. Every RFQ now belongs to one category group and contains
    # ONLY that group's items - never the whole PR (task 14/15).
    group_category, group_items, category_error = _resolve_rfq_group(pr, payload)
    if category_error:
        return category_error

    supplier_category_names = set(SupplierCategory.objects.filter(
        supplier=supplier, category__is_active=True
    ).values_list('category__name', flat=True))

    if is_manual_selection:
        selection_type = RFQ.SELECTION_MANUAL_BAC
    else:
        selection_type = RFQ.SELECTION_CATEGORY_MATCH
        if group_category is not None:
            eligible = group_category.name in supplier_category_names
        else:
            # Legacy uncategorised PR: fall back to the PR-level category.
            pr_names = {(i.category or '').strip() for i in pr.line_items.all() if (i.category or '').strip()}
            if pr.category:
                pr_names.add(pr.category)
            eligible = bool(pr_names & supplier_category_names)
        if not eligible:
            return json_error(
                'Supplier is not eligible for this procurement category - it is not category-matched. '
                'Use a manual BAC selection to proceed with a supplier outside the category.',
                400,
            )

    rfq_id = payload.get('rfq_id')
    rfq = RFQ.objects.filter(id=rfq_id, purchase_request=pr).first() if rfq_id else None
    if rfq and rfq.supplier_id != supplier.id:
        return json_error('RFQ does not belong to the selected supplier.', 400)
    if rfq and rfq.category_id and group_category is not None and rfq.category_id != group_category.id:
        return json_error('RFQ belongs to a different procurement category group.', 400)

    # Prevent duplicate RFQs for the same supplier + category group on the same
    # PR. A still-draft RFQ for that group is reused; an issued one blocks a new
    # request. A supplier may still receive a separate RFQ for another group.
    if not rfq:
        existing_for_group = (
            RFQ.objects.filter(purchase_request=pr, supplier=supplier, category=group_category)
            .order_by('-created_at').first()
        )
        if existing_for_group and existing_for_group.status != RFQ.STATUS_DRAFT:
            return json_error(
                'An RFQ for this supplier and procurement category has already been issued for this Purchase Request.',
                409,
            )
        rfq = existing_for_group

    default_subject = f"Request for Quotation - PR {pr.pr_no or pr.id}"
    default_message = (
        f"Dear {supplier.contact_person or supplier.company_name},\n\n"
        "Greetings.\n\n"
        f"The {pr.entity_name} is requesting a quotation for the items/services specified in Purchase Request "
        f"{pr.pr_no or pr.id}. Please provide your quotation based on the specifications and quantities indicated.\n\n"
        "Kindly submit your quotation through the eProcure system or through the designated submission process.\n\n"
        "Thank you.\n\nRegards,\nBAC Secretariat"
    )

    valid_quotation_bases = {choice[0] for choice in RFQ.QUOTATION_BASIS_CHOICES}

    def _resolve_quotation_basis(raw, fallback):
        candidate = str(raw or '').strip().upper()
        return candidate if candidate in valid_quotation_bases else fallback

    should_send = bool(payload.get('send'))
    generate_pdf = bool(payload.get('generate_pdf') or payload.get('preview'))

    # Mode of Procurement - admin-entered. The configured list
    # (api/rfq/procurement_modes.py) drives the suggestions offered on the form,
    # but the admin may also type a mode that is not on the list. Never inferred
    # from the PR and kept independent of the PR category.
    if 'mode_of_procurement' in payload:
        mode_of_procurement = normalize_procurement_mode(payload.get('mode_of_procurement'))
        if len(mode_of_procurement) > 200:
            return json_error('Mode of procurement must be 200 characters or fewer.', 400)
    else:
        mode_of_procurement = normalize_procurement_mode(rfq.mode_of_procurement if rfq else '')

    if (generate_pdf or should_send) and not mode_of_procurement:
        return json_error('Please enter a mode of procurement.', 400)

    group_abc_default = _format_peso(sum(float(i.total_cost or 0) for i in group_items)) or '₱0.00'

    rfq_created = rfq is None
    if not rfq:
        abc_value = str(payload.get('abc') or group_abc_default)
        with transaction.atomic():
            rfq = RFQ.objects.create(
                rfq_no=None,  # assigned only when the RFQ is issued (see below)
                purchase_request=pr,
                supplier=supplier,
                category=group_category,
                created_by=request.auth_user,
                subject=str(payload.get('subject') or default_subject).strip(),
                message=str(payload.get('message') or default_message).strip(),
                abc=abc_value.strip(),
                additional_notes=str(payload.get('additional_notes') or '').strip(),
                mode_of_procurement=mode_of_procurement,
                quotation_basis=_resolve_quotation_basis(payload.get('quotation_basis'), RFQ.QUOTATION_BASIS_LOT),
                selection_type=selection_type,
            )
            _sync_rfq_items(rfq, group_items)
    else:
        abc_value = str(payload.get('abc') or (rfq.abc or group_abc_default)).strip()
        rfq.subject = str(payload.get('subject') or rfq.subject).strip()
        rfq.message = str(payload.get('message') or rfq.message).strip()
        rfq.abc = abc_value
        rfq.mode_of_procurement = mode_of_procurement
        rfq.quotation_basis = _resolve_quotation_basis(payload.get('quotation_basis'), rfq.quotation_basis or RFQ.QUOTATION_BASIS_LOT)
        rfq.additional_notes = str(payload.get('additional_notes') or rfq.additional_notes).strip()
        rfq.created_by = rfq.created_by or request.auth_user
        if not rfq.category_id:
            rfq.category = group_category
        # Keep the audit designation in sync when the caller restates it, but
        # never silently downgrade a recorded manual override to a category
        # match on an edit that omits the flag.
        if is_manual_selection or 'selection_type' in payload or 'manual_selection' in payload:
            rfq.selection_type = selection_type
        if not rfq.rfq_items.exists():
            _sync_rfq_items(rfq, group_items)
        if request.method == 'PATCH':
            rfq.save(update_fields=['subject', 'message', 'abc', 'additional_notes', 'mode_of_procurement', 'quotation_basis', 'selection_type', 'category', 'created_by', 'updated_at'])

    # Defer the RFQ / Quotation number until the RFQ is actually issued - a
    # preview or a saved draft never consumes a number (task 12/18).
    if should_send and not rfq.rfq_no:
        rfq.rfq_no = _rfq_number(lock=True)
        rfq.save(update_fields=['rfq_no', 'updated_at'])

    if generate_pdf:
        try:
            file_url, _ = generate_rfq_pdf(rfq)
            rfq.pdf_file = file_url.replace('/uploads/', '').lstrip('/')
        except ValueError:
            return json_error('RFQ PDF generation failed. Please verify the PR data and try again.', 500)
        rfq.save(update_fields=['pdf_file', 'updated_at'])

    if should_send:
        if not rfq.subject or not rfq.message:
            return json_error('RFQ subject and message are required.', 400)
        if not supplier.email or '@' not in supplier.email:
            return json_error("RFQ could not be sent. Please verify the supplier's email address and email configuration.", 400)

        email = EmailMessage(
            subject=rfq.subject,
            body=rfq.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[supplier.email],
        )
        if rfq.pdf_file:
            pdf_path = UPLOADS_DIR / rfq.pdf_file
            if pdf_path.is_file():
                email.attach_file(pdf_path, mimetype='application/pdf')
        try:
            email.send(fail_silently=False)
        except Exception:
            return json_error("RFQ could not be sent. Please verify the supplier's email address and email configuration.", 502)

        rfq.status = RFQ.STATUS_SENT
        rfq.sent_at = timezone.now()
        rfq.save(update_fields=['status', 'sent_at', 'subject', 'message', 'mode_of_procurement', 'quotation_basis', 'abc', 'additional_notes', 'selection_type', 'category', 'pdf_file', 'updated_at'])
        Notification.objects.create(
            supplier=supplier,
            notification_type=Notification.TYPE_RFQ_RECEIVED,
            title='New Request for Quotation',
            message=(
                f'RFQ {rfq.rfq_no} for PR {pr.pr_no or pr.id} is ready. Download it, '
                'complete and sign the document, then upload the completed RFQ.'
            ),
            related_pr_id=pr.id,
            related_rfq_id=rfq.id,
        )
    else:
        rfq.save(update_fields=['subject', 'message', 'mode_of_procurement', 'quotation_basis', 'abc', 'additional_notes', 'selection_type', 'category', 'pdf_file', 'updated_at'])

    return JsonResponse(_rfq_payload(rfq, request), status=201 if rfq_created else 200)


# ─── Manual / unregistered supplier RFQs ───────────────────────────────────────
# A BAC Secretariat member issues an RFQ to a supplier that is NOT registered in
# eProcure. No Supplier / SupplierCategory / account is ever created - the name
# is internal metadata only and never reaches the generated PDF. The RFQ number
# (RFQ-YYYY-NNNN, also printed as the Quotation No.) comes from the same shared
# sequence registered-supplier RFQs use, so the two never collide.

def _manual_rfq_defaults(pr, manual_name):
    subject = f"Request for Quotation - PR {pr.pr_no or pr.id}"
    message = (
        "Greetings.\n\n"
        f"The {pr.entity_name} is requesting a quotation for the items/services specified in Purchase "
        f"Request {pr.pr_no or pr.id}. Please provide your quotation based on the specifications and "
        "quantities indicated.\n\nThank you.\n\nRegards,\nBAC Secretariat"
    )
    return subject, message


@csrf_exempt
@require_POST
@require_auth(role='admin')
def manual_rfq_create(request, pr_id):
    """Create (and issue) a manual RFQ for an unregistered supplier.

    ``POST /api/pr/<pr_id>/manual-rfq/``  body:
        { "manual_supplier_name": "Juan's Aircon Services",
          "mode_of_procurement": "...", "quotation_basis": "LOT",
          "subject": "...", "message": "...", "additional_notes": "...",
          "force_new": false }

    Re-posting the same supplier name for the same PR returns the existing RFQ
    (same quotation number) unless ``force_new`` is true.
    """
    try:
        pr = PurchaseRequest.objects.prefetch_related('line_items').get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, json.JSONDecodeError):
        return json_error('Invalid JSON payload', 400)

    manual_name = normalize_text(payload.get('manual_supplier_name') or payload.get('supplier_name') or '')
    if not manual_name:
        return json_error('Enter the supplier / company name.', 400)
    if len(manual_name) > 255:
        return json_error('Supplier / company name is too long.', 400)

    # The manual RFQ serves one procurement category group, exactly like a
    # registered-supplier RFQ, and contains only that group's items.
    group_category, group_items, category_error = _resolve_rfq_group(pr, payload)
    if category_error:
        return category_error

    force_new = bool(payload.get('force_new'))
    if not force_new:
        existing = (
            RFQ.objects.filter(
                purchase_request=pr,
                delivery_method=RFQ.DELIVERY_MANUAL,
                manual_supplier_name__iexact=manual_name,
                category=group_category,
            )
            .order_by('-created_at')
            .first()
        )
        if existing is not None:
            return JsonResponse({**_rfq_payload(existing, request), 'existing': True}, status=200)

    valid_quotation_bases = {choice[0] for choice in RFQ.QUOTATION_BASIS_CHOICES}
    quotation_basis = str(payload.get('quotation_basis') or RFQ.QUOTATION_BASIS_LOT).strip().upper()
    if quotation_basis not in valid_quotation_bases:
        quotation_basis = RFQ.QUOTATION_BASIS_LOT

    mode_of_procurement = normalize_procurement_mode(payload.get('mode_of_procurement'))
    if not mode_of_procurement:
        return json_error('Please enter a mode of procurement.', 400)
    if len(mode_of_procurement) > 200:
        return json_error('Mode of procurement must be 200 characters or fewer.', 400)

    subject_default, message_default = _manual_rfq_defaults(pr, manual_name)
    abc_value = str(payload.get('abc') or _format_peso(sum(float(i.total_cost or 0) for i in group_items))).strip()
    issuer = request.auth_user

    try:
        with transaction.atomic():
            rfq = RFQ.objects.create(
                rfq_no=_rfq_number(lock=True),
                purchase_request=pr,
                supplier=None,
                category=group_category,
                manual_supplier_name=manual_name,
                delivery_method=RFQ.DELIVERY_MANUAL,
                selection_type=RFQ.SELECTION_MANUAL_BAC,
                created_by=issuer,
                subject=str(payload.get('subject') or subject_default).strip(),
                message=str(payload.get('message') or message_default).strip(),
                abc=abc_value,
                additional_notes=str(payload.get('additional_notes') or '').strip(),
                mode_of_procurement=mode_of_procurement,
                quotation_basis=quotation_basis,
                status=RFQ.STATUS_SENT,
                sent_at=timezone.now(),
            )
            _sync_rfq_items(rfq, group_items)
            try:
                file_url, _ = generate_rfq_pdf(rfq)
                rfq.pdf_file = file_url.replace('/uploads/', '').lstrip('/')
                rfq.save(update_fields=['pdf_file', 'updated_at'])
            except ValueError:
                raise RuntimeError('pdf')
    except RuntimeError:
        return json_error('RFQ PDF generation failed. Please verify the PR data and try again.', 500)

    return JsonResponse(_rfq_payload(rfq, request), status=201)


@require_GET
@require_auth(role='admin')
def manual_rfq_list(request):
    """List manual / unregistered-supplier RFQs for the Admin "Manual RFQs" area.

    Search (``?search=``) matches supplier name, PR number and quotation number.
    """
    search = normalize_text(request.GET.get('search') or '')
    rfqs = (
        RFQ.objects.filter(delivery_method=RFQ.DELIVERY_MANUAL)
        .select_related('purchase_request', 'created_by')
        .prefetch_related('purchase_request__line_items')
        .order_by('-created_at')
    )
    if search:
        rfqs = rfqs.filter(
            Q(manual_supplier_name__icontains=search)
            | Q(purchase_request__pr_no__icontains=search)
            | Q(rfq_no__icontains=search)
        )
    return JsonResponse({'rfqs': [_rfq_payload(rfq, request) for rfq in rfqs]})


@require_GET
@require_auth(role='admin')
def manual_rfq_pdf(request, rfq_id):
    """Stream the generated RFQ PDF, regenerating it if the file is missing.

    The quotation number is never changed here - re-downloading or reprinting
    reuses the number assigned when the RFQ was issued.
    """
    rfq = (
        RFQ.objects.filter(id=rfq_id, delivery_method=RFQ.DELIVERY_MANUAL)
        .select_related('purchase_request')
        .prefetch_related('purchase_request__line_items')
        .first()
    )
    if rfq is None:
        return json_error('Manual RFQ not found', 404)

    pdf_path = UPLOADS_DIR / rfq.pdf_file if rfq.pdf_file else None
    if not pdf_path or not pdf_path.is_file():
        try:
            file_url, path = generate_rfq_pdf(rfq)
            rfq.pdf_file = file_url.replace('/uploads/', '').lstrip('/')
            rfq.save(update_fields=['pdf_file', 'updated_at'])
            pdf_path = Path(path)
        except ValueError:
            return json_error('Unable to regenerate the RFQ PDF.', 500)

    from django.http import FileResponse

    download_name = f"{rfq.rfq_no}.pdf".replace(' ', '_')
    return FileResponse(open(pdf_path, 'rb'), as_attachment=True, filename=download_name)


@csrf_exempt
@require_POST
@require_auth(role='admin')
def manual_rfq_completed(request, rfq_id):
    """Admin uploads the completed RFQ a manual supplier returned physically.

    Mirrors ``supplier_rfq_response`` (generated PDF untouched, completed stored
    separately) - quotation number and supplier name are never changed.
    """
    rfq = RFQ.objects.filter(id=rfq_id, delivery_method=RFQ.DELIVERY_MANUAL).select_related('purchase_request').first()
    if rfq is None:
        return json_error('Manual RFQ not found', 404)

    uploaded = request.FILES.get('file')
    if not uploaded:
        return json_error('A completed RFQ PDF file is required.', 400)
    try:
        validate_upload(uploaded, UploadKind.COMPLETED_RFQ)
    except FileValidationError as exc:
        return json_error(exc.message, 400)

    is_replacement = bool(rfq.submitted_pdf)
    rfq.submitted_pdf = _save_supplier_upload(uploaded)
    rfq.submitted_at = timezone.now()
    rfq.status = RFQ.STATUS_QUOTATION_RECEIVED
    rfq.save(update_fields=['submitted_pdf', 'submitted_at', 'status', 'updated_at'])
    return JsonResponse({'success': True, 'replaced': is_replacement, **_rfq_payload(rfq, request)})


@require_GET
@require_auth(role='supplier', owner_param='supplier_id')
def supplier_rfqs(request, supplier_id):
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return json_error('Supplier not found', 404)
    rfqs = RFQ.objects.filter(supplier=supplier).select_related('purchase_request').prefetch_related('purchase_request__line_items')
    return JsonResponse({'rfqs': [_rfq_payload(rfq, request) for rfq in rfqs]})


# Statuses in which a supplier may still upload / replace their completed RFQ.
RFQ_RESPONSE_OPEN_STATUSES = {RFQ.STATUS_SENT, RFQ.STATUS_QUOTATION_RECEIVED}


@csrf_exempt
@require_POST
@require_auth(role='supplier', owner_param='supplier_id')
def supplier_rfq_response(request, supplier_id, rfq_id):
    """Supplier uploads (or replaces) the completed, signed RFQ PDF.

    The generated RFQ (``rfq.pdf_file``) is never touched - the completed
    document is stored separately in ``rfq.submitted_pdf``.
    """
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return json_error('Supplier not found', 404)

    # Authorisation: the RFQ must belong to this supplier.
    rfq = RFQ.objects.filter(id=rfq_id, supplier=supplier).select_related('purchase_request').first()
    if not rfq:
        return json_error('RFQ not found for this supplier.', 404)

    if rfq.status not in RFQ_RESPONSE_OPEN_STATUSES:
        return json_error('This RFQ is no longer open for a response.', 409)

    uploaded = request.FILES.get('file')
    if not uploaded:
        return json_error('A completed RFQ PDF file is required.', 400)
    try:
        validate_upload(uploaded, UploadKind.COMPLETED_RFQ)
    except FileValidationError as exc:
        return json_error(exc.message, 400)

    is_replacement = bool(rfq.submitted_pdf)
    filename = _save_supplier_upload(uploaded)
    rfq.submitted_pdf = filename
    rfq.submitted_at = timezone.now()
    rfq.status = RFQ.STATUS_QUOTATION_RECEIVED
    rfq.save(update_fields=['submitted_pdf', 'submitted_at', 'status', 'updated_at'])

    Notification.objects.create(
        supplier=supplier,
        notification_type=Notification.TYPE_QUOTATION_SUBMITTED,
        title='Completed RFQ uploaded' if not is_replacement else 'Completed RFQ replaced',
        message=(
            f'Your completed RFQ for {rfq.rfq_no} (PR {rfq.purchase_request.pr_no or rfq.purchase_request_id}) '
            'has been received by the BAC Secretariat.'
        ),
        related_pr_id=rfq.purchase_request_id,
        related_rfq_id=rfq.id,
    )

    return JsonResponse({'success': True, 'replaced': is_replacement, **_rfq_payload(rfq, request)})


@require_GET
@require_auth(role='admin')
def admin_rfq_responses(request):
    """All issued RFQs with their generated + submitted documents, for the BAC
    RFQ Management screen. Role-gated like the other admin RFQ endpoints.

    Default response is the flat ``{"rfqs": [...]}`` list. Pass ``group_by=pr`` to
    receive the same RFQs grouped under their Purchase Request with per-PR
    sent / received / awaiting counts, which is what the PR-centered RFQ
    Management interface consumes.
    """
    status_filter = (request.GET.get('status') or '').strip().lower()
    search = (request.GET.get('search') or '').strip()
    group_by = (request.GET.get('group_by') or '').strip().lower()
    sort = (request.GET.get('sort') or '').strip().lower()

    rfqs = (
        RFQ.objects
        .exclude(status=RFQ.STATUS_DRAFT)
        .select_related('purchase_request', 'supplier', 'category')
        .prefetch_related('purchase_request__line_items', 'rfq_items')
        .order_by('-sent_at', '-created_at')
    )
    if status_filter == 'awaiting':
        rfqs = rfqs.filter(status=RFQ.STATUS_SENT)
    elif status_filter == 'received':
        # "Responses Received" covers every RFQ the supplier has answered. The
        # ``completed`` status (post-evaluation, not implemented in this capstone)
        # is included here so it never needs a separate filter.
        rfqs = rfqs.filter(status__in=[RFQ.STATUS_QUOTATION_RECEIVED, RFQ.STATUS_COMPLETED], submitted_pdf__gt='')

    if search:
        rfqs = rfqs.filter(
            Q(rfq_no__icontains=search)
            | Q(purchase_request__pr_no__icontains=search)
            | Q(supplier__company_name__icontains=search)
            | Q(manual_supplier_name__icontains=search)
        )

    rfq_list = list(rfqs)

    if group_by != 'pr':
        return JsonResponse({'rfqs': [_rfq_payload(rfq, request) for rfq in rfq_list]})

    # Group the already-fetched RFQs by Purchase Request. No extra queries: the
    # PR and its line items were select_related / prefetch_related above.
    groups = {}
    order = []
    for rfq in rfq_list:
        pr = rfq.purchase_request
        if pr.id not in groups:
            groups[pr.id] = []
            order.append(pr.id)
        groups[pr.id].append(rfq)

    grouped_payload = []
    for pr_id in order:
        group_rfqs = groups[pr_id]
        pr = group_rfqs[0].purchase_request
        sent = len(group_rfqs)
        received = sum(1 for r in group_rfqs if r.submitted_pdf)
        awaiting = sent - received
        activity_stamps = [r.submitted_at or r.sent_at or r.created_at for r in group_rfqs]
        last_activity = max(activity_stamps) if activity_stamps else None
        rfq_payloads = [_rfq_payload(r, request) for r in group_rfqs]

        # Second grouping level: category group (task 20). Keyed by category name;
        # a legacy RFQ with no category falls under "Uncategorized".
        pr_item_category = {}
        for item in pr.line_items.all():
            pr_item_category.setdefault((item.category or '').strip(), 0)
            pr_item_category[(item.category or '').strip()] += 1
        cat_buckets = {}
        cat_order = []
        for rfq, payload_row in zip(group_rfqs, rfq_payloads):
            key = payload_row['category'] or 'Uncategorized'
            if key not in cat_buckets:
                cat_buckets[key] = []
                cat_order.append(key)
            cat_buckets[key].append(payload_row)
        categories_payload = []
        for key in cat_order:
            rows = cat_buckets[key]
            cat_received = sum(1 for r in rows if r['has_response'])
            categories_payload.append({
                'category': key,
                'category_id': rows[0].get('category_id'),
                'item_count': rows[0].get('item_count', 0) or pr_item_category.get(key, 0),
                'rfq_count': len(rows),
                'response_count': cat_received,
                'awaiting_count': len(rows) - cat_received,
                'rfqs': rows,
            })

        grouped_payload.append({
            'purchase_request': {
                'id': pr.id,
                'pr_no': pr.pr_no or f'PR-{pr.id}',
                'date': pr.date.isoformat() if pr.date else '',
                'category': pr.category or '',
                'purpose': pr.purpose or '',
                'entity_name': pr.entity_name,
                'office_section': pr.office_section or '',
                'status': pr.status,
                'created_at': pr.created_at.isoformat(),
            },
            'rfq_summary': {
                'sent': sent,
                'responses_received': received,
                'awaiting_response': awaiting,
                'category_count': len(categories_payload),
                'status': _pr_rfq_progress_status(sent, received),
                'last_activity': last_activity.isoformat() if last_activity else None,
            },
            'categories': categories_payload,
            'rfqs': rfq_payloads,
        })

    if sort == 'oldest_pr':
        grouped_payload.sort(key=lambda g: g['purchase_request']['created_at'])
    elif sort == 'recent_activity':
        grouped_payload.sort(key=lambda g: g['rfq_summary']['last_activity'] or '', reverse=True)
    elif sort == 'response_status':
        rank = {'awaiting_responses': 0, 'responses_in_progress': 1, 'all_responses_received': 2, 'no_rfqs': 3}
        grouped_payload.sort(key=lambda g: rank.get(g['rfq_summary']['status'], 9))
    else:  # 'newest_pr' (default)
        grouped_payload.sort(key=lambda g: g['purchase_request']['created_at'], reverse=True)

    return JsonResponse({'purchase_requests': grouped_payload})

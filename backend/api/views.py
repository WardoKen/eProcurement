import hashlib
import json
import re
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

from django.http import JsonResponse
from django.core.mail import EmailMessage
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef
from django.conf import settings

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
except ImportError:  # pragma: no cover
    from backend.ocr.ocr_service import TextractOCRService
    from backend.ocr.layout_parser import DocumentLayoutParser
    from backend.ocr.purchase_request_parser import parse_purchase_request
    from backend.ocr.form_autofill import FormAutoFillService
    from backend.ocr.validation import ValidationService
    from backend.ocr.debug_utils import write_debug_json

from .models import Role, Supplier, User, SupplierDocument, Category, SupplierCategory
from .models import PurchaseRequest, PurchaseRequestItem, PRNumberSequence, Quotation, Notification, RFQ
from .supplier_registration import (
    REQUIRED_UPLOAD_KEYS,
    OPTIONAL_UPLOAD_KEYS,
    get_required_business_document_key,
    sanitize_text,
    validate_supplier_payload,
    _save_supplier_upload,
)

UPLOADS_DIR = Path(settings.BASE_DIR) / 'uploads'
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


ocr_service = TextractOCRService(language='en')
layout_parser = DocumentLayoutParser()
auto_fill_service = FormAutoFillService()
validation_service = ValidationService()


def normalize_text(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '')).strip()


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
    if lock:
        PRNumberSequence.objects.select_for_update().get(key='global')

    highest = 0
    valid_number = re.compile(rf'^{re.escape(prefix)}(\d{{3}})$')
    for value in PurchaseRequest.objects.filter(pr_no__startswith=prefix).values_list('pr_no', flat=True):
        match = valid_number.fullmatch(value or '')
        if match:
            highest = max(highest, int(match.group(1)))

    return f'{prefix}{highest + 1:03d}'


def generate_pr_number():
    return next_pr_number(lock=True)


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
def next_pr_number_preview(request):
    return JsonResponse({'pr_no': next_pr_number()})


@csrf_exempt
@require_POST
@csrf_exempt
@require_POST
@csrf_exempt
@require_POST
def upload_file(request):
    file = request.FILES.get('file')
    if not file:
        return json_error('No file uploaded', 400)

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
    auto_filled = auto_fill_service.populate(parsed)
    validation = validation_service.validate(parsed)
    response_payload = {
        'success': True,
        'fields': {**auto_filled, **parsed},
        'rawText': document.get('raw_text', ''),
        'source': source,
        'filename': filename,
        'fileUrl': request.build_absolute_uri(f'/uploads/{filename}'),
        'ocr': document,
        'validation': validation,
    }
    write_debug_json('final_output.json', response_payload)
    return JsonResponse(response_payload)


@csrf_exempt
@require_POST
def pr_scan(request):
    """Accept a single PDF upload, run the extractor and return parsed JSON.

    Returns 422 when no table/items were detected so the frontend can fall back to manual entry.
    """
    f = request.FILES.get('file')
    if not f:
        return json_error('No file uploaded', 400)

    # basic validation
    if not (f.content_type == 'application/pdf' or f.name.lower().endswith('.pdf')):
        return json_error('Only PDF files are accepted', 400)
    if f.size > 10 * 1024 * 1024:
        return json_error('File too large (max 10MB)', 400)

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

    return JsonResponse({'success': True, 'id': pr.id, 'pr_no': pr.pr_no, 'status': pr.status}, status=201)


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


@require_GET
def pr_list(request):
    category = request.GET.get('category', '').strip()
    submitted_by = request.GET.get('submitted_by', '').strip()
    qs = (
        PurchaseRequest.objects.order_by('-created_at')
        .annotate(items_count=Count('line_items'))
        .annotate(has_quotation=Exists(Quotation.objects.filter(purchase_request_id=OuterRef('pk'))))
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
            'requested_by',
            'approved_by',
            'grand_total',
            'created_at',
            'items_count',
            'has_quotation',
        )
    return JsonResponse(list(prs), safe=False)


@csrf_exempt
@require_http_methods(["PATCH"])
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
                pr.status = PurchaseRequest.STATUS_MATCHED
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
def pr_delete(request, pr_id: int):
    deleted, _ = PurchaseRequest.objects.filter(id=pr_id).delete()
    if not deleted:
        return json_error('Purchase Request not found', 404)
    return JsonResponse({'success': True, 'id': pr_id})


@csrf_exempt
@require_POST
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
    supplier_id = data.get('supplier_id')

    if not username or not password:
        return json_error('Username and password are required', 400)

    user = User.objects.filter(username=username, is_active=True).select_related('role').first()
    if not user or not verify_password(password, user.password_hash):
        return json_error('Invalid username or password', 401)

    if role_name and user.role.name != role_name:
        return json_error('Role mismatch', 403)

    supplier_payload = None
    if user.role.name == 'supplier':
        supplier = None
        if supplier_id:
            try:
                supplier = Supplier.objects.get(id=supplier_id)
            except Supplier.DoesNotExist:
                supplier = None
        if supplier is None:
            supplier = Supplier.objects.filter(email__icontains=username).order_by('-created_at').first()
        if supplier is None:
            supplier = Supplier.objects.order_by('-created_at').first()
        if supplier is not None:
            supplier_payload = {
                'supplier_id': supplier.id,
                'supplier_status': supplier.status,
            }

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

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
def supplier_list_create(request):
    if request.method == 'GET':
        suppliers = list(
            Supplier.objects.order_by('-created_at').values(
                'id',
                'company_name',
                'email',
                'status',
                'business_type',
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
def admin_dashboard_summary(request):
    """Return live summary counts for the BAC administrator dashboard."""
    return JsonResponse({
        'pending_suppliers': Supplier.objects.filter(status__in=['Pending', 'Pending Review']).count(),
        'under_review_suppliers': Supplier.objects.filter(status='In Review').count(),
        'action_required_suppliers': Supplier.objects.filter(status='For Compliance').count(),
        'total_suppliers': Supplier.objects.count(),
        'total_purchase_requests': PurchaseRequest.objects.count(),
        'pending_purchase_requests': PurchaseRequest.objects.filter(status__in=['uploaded', 'in_review', 'matched']).count(),
        'approved_purchase_requests': PurchaseRequest.objects.filter(status='approved').count(),
    })


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
                try:
                    User.objects.create(
                        username=username,
                        password_hash=hash_password(password),
                        full_name=sanitize_text(payload.get('contactPerson', '')),
                        role=role,
                        is_active=True,
                    )
                except IntegrityError:
                    raise IntegrityError('Username already exists')
    except IntegrityError:
        return JsonResponse({'success': False, 'message': 'Username already exists.'}, status=409)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': 'Failed to save supplier registration.', 'error': str(exc)}, status=500)

    return JsonResponse({'success': True, 'id': supplier.id, 'message': 'Supplier registration submitted successfully. It is now pending review.'}, status=201)


@csrf_exempt
@require_http_methods(["PATCH"])
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

    if status == 'Approved':
        Notification.objects.create(
            supplier=supplier,
            notification_type=Notification.TYPE_PROFILE_APPROVED,
            title='Supplier Profile Approved',
            message='Your supplier profile has been approved by the BAC admin.',
        )

    return JsonResponse({'success': True, 'id': supplier.id, 'status': supplier.status, 'remarks': supplier.review_remarks})


# ─── SUPPLIER PORTAL ENDPOINTS ──────────────────────────────────────────────────

@require_GET
def supplier_matching_opportunities(request, supplier_id):
    """Get all Purchase Requests matching supplier's registered categories."""
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return JsonResponse({'error': 'Supplier not found'}, status=404)

    if supplier.status != 'Approved':
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


@require_http_methods(['GET', 'POST'])
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
def supplier_mark_notification_read(request, notification_id):
    """Mark a notification as read."""
    try:
        notification = Notification.objects.get(id=notification_id)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'error': 'Notification not found'}, status=404)


@require_http_methods(['GET', 'PATCH'])
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
                'company_name', 'business_address', 'contact_person',
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


@require_GET
def purchase_request_details(request, pr_id):
    """Get detailed information about a Purchase Request."""
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
    })


@csrf_exempt
@require_POST
def verify_recaptcha(request):
    return JsonResponse({'success': True})


# ─── PR Item Category Assignment ─────────────────────────────────────────────

@require_GET
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
def pr_items_assign_categories(request, pr_id):
    """Save the selected category for each Purchase Request item."""
    try:
        PurchaseRequest.objects.get(id=pr_id)
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

    return JsonResponse({'success': True})


@require_GET
def pr_supplier_match(request, pr_id):
    """Return suppliers matched by the item categories assigned to a PR."""
    try:
        pr = PurchaseRequest.objects.get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)

    item_categories = list(
        PurchaseRequestItem.objects
        .filter(purchase_request_id=pr_id)
        .exclude(category__isnull=True).exclude(category='')
        .values_list('category', flat=True)
        .distinct()
    )
    categories = list(dict.fromkeys(([pr.category] if pr.category else []) + item_categories))

    matching_supplier_ids = set(
        SupplierCategory.objects
        .filter(category__name__in=categories)
        .values_list('supplier_id', flat=True)
    )
    all_suppliers = list(Supplier.objects.filter(id__in=matching_supplier_ids).values(
        'id', 'company_name', 'email', 'contact_person', 'contact_phone',
        'business_address', 'goods_services', 'nature_of_business', 'status',
    ))

    results = []
    for cat in categories:
        category_supplier_ids = set(
            SupplierCategory.objects
            .filter(category__name=cat)
            .values_list('supplier_id', flat=True)
        )
        matched = [{**supplier, 'match_score': 1} for supplier in all_suppliers if supplier['id'] in category_supplier_ids]

        results.append({'category': cat, 'suppliers': matched})

    return JsonResponse(results, safe=False)


@require_GET
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


def _rfq_payload(rfq, request):
    pr = rfq.purchase_request
    items = [{
        'id': item.id,
        'item_description': item.item_description,
        'quantity': float(item.quantity),
        'unit': item.unit or '',
        'category': item.category or '',
    } for item in pr.line_items.all()]
    return {
        'id': rfq.id,
        'rfq_no': rfq.rfq_no,
        'status': rfq.status,
        'subject': rfq.subject,
        'message': rfq.message,
        'created_at': rfq.created_at.isoformat(),
        'sent_at': rfq.sent_at.isoformat() if rfq.sent_at else None,
        'purchase_request': {
            'id': pr.id,
            'pr_no': pr.pr_no,
            'date': pr.date.isoformat() if pr.date else '',
            'entity_name': pr.entity_name,
            'office_section': pr.office_section or '',
            'purpose': pr.purpose or '',
            'category': pr.category or '',
            'source_filename': pr.source_filename,
            'source_file_url': request.build_absolute_uri(f'/uploads/{pr.source_filename}') if pr.source_filename else '',
            'items': items,
        },
        'supplier': {
            'id': rfq.supplier.id,
            'company_name': rfq.supplier.company_name,
            'contact_person': rfq.supplier.contact_person,
            'email': rfq.supplier.email,
        },
    }


def _rfq_number():
    return f"RFQ-{timezone.now().year}-{RFQ.objects.filter(created_at__year=timezone.now().year).count() + 1:04d}"


@csrf_exempt
@require_http_methods(['GET', 'POST', 'PATCH'])
def admin_rfq(request, pr_id):
    try:
        pr = PurchaseRequest.objects.prefetch_related('line_items').get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)

    if request.method == 'GET':
        rfqs = RFQ.objects.filter(purchase_request=pr).select_related('supplier')
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

    if supplier.status != 'Approved':
        return json_error('Supplier is not eligible because the supplier is not approved.', 400)

    pr_category_names = {item.category for item in pr.line_items.all() if item.category}
    if pr.category:
        pr_category_names.add(pr.category)
    supplier_category_names = set(SupplierCategory.objects.filter(
        supplier=supplier, category__is_active=True
    ).values_list('category__name', flat=True))
    requested_category = str(payload.get('category') or '').strip()
    eligible_categories = pr_category_names.intersection(supplier_category_names)
    if requested_category and requested_category not in eligible_categories:
        return json_error('Supplier is no longer eligible for the selected PR category.', 400)
    if not eligible_categories:
        return json_error('Supplier is no longer eligible for this Purchase Request.', 400)

    rfq_id = payload.get('rfq_id')
    rfq = RFQ.objects.filter(id=rfq_id, purchase_request=pr).first() if rfq_id else None
    if rfq and rfq.supplier_id != supplier.id:
        return json_error('RFQ does not belong to the selected supplier.', 400)
    default_subject = f"Request for Quotation - PR {pr.pr_no or pr.id}"
    default_message = (
        f"Dear {supplier.contact_person or supplier.company_name},\n\n"
        "Greetings.\n\n"
        f"The {pr.entity_name} is requesting a quotation for the items/services specified in Purchase Request "
        f"{pr.pr_no or pr.id}. Please provide your quotation based on the specifications and quantities indicated.\n\n"
        "Kindly submit your quotation through the eProcure system or through the designated submission process.\n\n"
        "Thank you.\n\nRegards,\nBAC Secretariat"
    )

    if not rfq:
        rfq = RFQ.objects.create(
            rfq_no=_rfq_number(),
            purchase_request=pr,
            supplier=supplier,
            subject=str(payload.get('subject') or default_subject).strip(),
            message=str(payload.get('message') or default_message).strip(),
        )
    elif request.method == 'PATCH':
        rfq.subject = str(payload.get('subject') or rfq.subject).strip()
        rfq.message = str(payload.get('message') or rfq.message).strip()

    should_send = bool(payload.get('send'))
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
        if pr.source_filename:
            attachment_path = UPLOADS_DIR / Path(pr.source_filename).name
            if attachment_path.is_file():
                email.attach_file(attachment_path)
        try:
            email.send(fail_silently=False)
        except Exception:
            return json_error("RFQ could not be sent. Please verify the supplier's email address and email configuration.", 502)

        rfq.status = RFQ.STATUS_SENT
        rfq.sent_at = timezone.now()
        rfq.save(update_fields=['status', 'sent_at', 'subject', 'message', 'updated_at'])
        Notification.objects.create(
            supplier=supplier,
            notification_type=Notification.TYPE_RFQ_RECEIVED,
            title='New Request for Quotation',
            message=f'RFQ {rfq.rfq_no} for PR {pr.pr_no or pr.id} is ready for your quotation.',
            related_pr_id=pr.id,
        )
    else:
        rfq.save(update_fields=['subject', 'message', 'updated_at'])

    return JsonResponse(_rfq_payload(rfq, request), status=201 if request.method == 'POST' and not rfq_id else 200)


@require_GET
def supplier_rfqs(request, supplier_id):
    try:
        supplier = Supplier.objects.get(id=supplier_id)
    except Supplier.DoesNotExist:
        return json_error('Supplier not found', 404)
    rfqs = RFQ.objects.filter(supplier=supplier).select_related('purchase_request').prefetch_related('purchase_request__line_items')
    return JsonResponse({'rfqs': [_rfq_payload(rfq, request) for rfq in rfqs]})

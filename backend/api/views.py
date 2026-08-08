import hashlib
import json
import re
import secrets
import sys
import time
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.db.models import Count
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
from .models import PurchaseRequest, PurchaseRequestItem, Quotation, Notification
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
    try:
        with transaction.atomic():
            pr = PurchaseRequest.objects.create(
                entity_name=entity,
                fund_cluster=normalize_text(fields.get('fundCluster') or fields.get('fund_cluster') or ''),
                office_section=normalize_text(fields.get('officeSection') or fields.get('office_section') or ''),
                pr_no=normalize_text(fields.get('prNumber') or fields.get('pr_no') or ''),
                responsibility_center_code=normalize_text(fields.get('responsibilityCenterCode') or fields.get('responsibility_center_code') or ''),
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
    except Exception as exc:
        return json_error('Failed to save Purchase Request', 500)

    return JsonResponse({'success': True, 'id': pr.id}, status=201)


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
    for name in OPPORTUNITY_CATEGORIES:
        Category.objects.get_or_create(
            name=name,
            defaults={'description': name}
        )

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
    qs = (
        PurchaseRequest.objects.order_by('-created_at')
        .annotate(items_count=Count('line_items'))
    )
    if category:
        qs = qs.filter(category=category)
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


@csrf_exempt
def supplier_register(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

    payload = {
        'companyName': request.POST.get('companyName', ''),
        'businessType': request.POST.get('businessType', '') or 'Sole Proprietorship',
        'businessAddress': request.POST.get('businessAddress', ''),
        'tin': request.POST.get('tin', ''),
        'contactPerson': request.POST.get('contactPerson', ''),
        'contactNumber': request.POST.get('contactNumber', ''),
        'email': request.POST.get('email', ''),
        'productsServices': request.POST.get('productsServices', ''),
        'categories': request.POST.getlist('categories') or request.POST.getlist('category') or [],
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

            for category_name in selected_category_names:
                category_obj, _ = Category.objects.get_or_create(name=category_name, defaults={'description': category_name})
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

    # Extract supplier's keywords from goods_services and nature_of_business
    supplier_keywords = (supplier.goods_services or '') + ' ' + (supplier.nature_of_business or '')
    supplier_keywords = supplier_keywords.lower().strip()

    if not supplier_keywords:
        return JsonResponse({'opportunities': []})

    # Get all approved/matched PRs with assigned categories
    prs = PurchaseRequest.objects.filter(
        status__in=['matched', 'approved']
    ).prefetch_related('line_items', 'quotations')

    matching_opportunities = []

    for pr in prs:
        # Check if any of the PR's item categories match supplier's goods/services
        pr_categories = set()
        for item in pr.line_items.all():
            if item.category:
                pr_categories.add(item.category.lower())

        if not pr_categories:
            continue

        # Simple keyword matching - check if any supplier keyword overlaps
        supplier_words = set(supplier_keywords.split())
        match_score = 0
        for category in pr_categories:
            category_words = set(category.split())
            # Calculate match percentage
            common = len(supplier_words & category_words)
            if common > 0:
                match_score += common

        if match_score > 0 or any(
            keyword in supplier_keywords
            for category in pr_categories
            for keyword in category.split()
        ):
            # Check if supplier already submitted quotation
            existing_quotation = pr.quotations.filter(supplier=supplier).first()
            quotation_status = None
            if existing_quotation:
                quotation_status = existing_quotation.status

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

    # Count matching opportunities
    supplier_keywords = (supplier.goods_services or '') + ' ' + (supplier.nature_of_business or '')
    supplier_keywords_set = set(supplier_keywords.lower().split())

    prs = PurchaseRequest.objects.filter(
        status__in=['matched', 'approved']
    ).prefetch_related('line_items', 'quotations')

    matching_count = 0
    for pr in prs:
        pr_categories = set()
        for item in pr.line_items.all():
            if item.category:
                pr_categories.add(item.category.lower())

        # Check if any supplier keyword overlaps with categories
        if pr_categories and any(
            keyword in supplier_keywords
            for category in pr_categories
            for keyword in category.split()
        ):
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
                existing.status = 'submitted'
                existing.save()
                quotation = existing
            else:
                # Create new quotation
                quotation = Quotation.objects.create(
                    supplier=supplier,
                    purchase_request=pr,
                    quoted_amount=quoted_amount,
                    estimated_delivery_days=estimated_delivery_days,
                    warranty_months=warranty_months,
                    remarks=remarks,
                    status='submitted'
                )

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
            'created_at': supplier.created_at.isoformat(),
            'documents': documents,
        })

    elif request.method == 'PATCH':
        try:
            data = json.loads(request.body)

            # Only allow updating specific fields
            allowed_fields = [
                'company_name', 'business_address', 'contact_person',
                'contact_phone', 'email', 'nature_of_business', 'goods_services', 'business_type'
            ]

            for field in allowed_fields:
                if field in data:
                    setattr(supplier, field, data[field])

            supplier.save()
            return JsonResponse({'success': True, 'supplier': {
                'id': supplier.id,
                'company_name': supplier.company_name,
                'business_address': supplier.business_address,
                'contact_person': supplier.contact_person,
                'contact_phone': supplier.contact_phone,
                'nature_of_business': supplier.nature_of_business,
                'goods_services': supplier.goods_services,
                'email': supplier.email,
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
        'entity_name': pr.entity_name,
        'office_section': pr.office_section,
        'purpose': pr.purpose,
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
        PurchaseRequest.objects.get(id=pr_id)
    except PurchaseRequest.DoesNotExist:
        return json_error('Purchase Request not found', 404)

    categories = list(
        PurchaseRequestItem.objects
        .filter(purchase_request_id=pr_id)
        .exclude(category__isnull=True).exclude(category='')
        .values_list('category', flat=True)
        .distinct()
    )

    all_suppliers = list(Supplier.objects.values(
        'id', 'company_name', 'email', 'contact_person', 'contact_phone',
        'business_address', 'goods_services', 'nature_of_business', 'status',
    ))

    results = []
    for cat in categories:
        cat_lower = cat.lower()
        keywords = [w for w in cat_lower.split() if len(w) > 3]

        scored = []
        for s in all_suppliers:
            combined = (
                (s.get('goods_services') or '').lower() + ' ' +
                (s.get('nature_of_business') or '').lower()
            )
            score = sum(2 for kw in keywords if kw in combined)
            if score > 0:
                scored.append({**s, 'match_score': score})

        scored.sort(key=lambda x: x['match_score'], reverse=True)
        matched = scored[:5]

        # Fallback: include first 3 suppliers even with zero score
        if not matched:
            matched = [{**s, 'match_score': 0} for s in all_suppliers[:3]]

        results.append({'category': cat, 'suppliers': matched})

    return JsonResponse(results, safe=False)

import os
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from django.conf import settings

REQUIRED_DOCUMENTS = {
    'mayor_permit': "Mayor's Permit",
    'business_permit': 'Business Permit',
    'philgeps_registration': 'PhilGEPS Registration',
    'bir_registration': 'BIR Registration',
    'tax_clearance': 'Tax Clearance',
    'dti_registration': 'DTI Registration',
    'sec_registration': 'SEC Registration',
    'cda_registration': 'CDA Registration',
}

REQUIRED_UPLOAD_KEYS = [
    'mayor_permit',
    'business_permit',
    'philgeps_registration',
    'bir_registration',
    'tax_clearance',
]

OPTIONAL_UPLOAD_KEYS = ['other_eligibility']
BUSINESS_DOCUMENT_KEYS = {
    'Sole Proprietorship': 'dti_registration',
    'Corporation': 'sec_registration',
    'Partnership': 'sec_registration',
    'Cooperative': 'cda_registration',
    'Others': None,
}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
ALLOWED_MIME_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}


def sanitize_text(value: object) -> str:
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def get_required_business_document_key(business_type: str) -> Optional[str]:
    return BUSINESS_DOCUMENT_KEYS.get(sanitize_text(business_type), None)


def is_supported_file(file_obj) -> bool:
    if not file_obj:
        return False
    name = (getattr(file_obj, 'name', '') or '').lower()
    extension = Path(name).suffix.lower()
    mime_type = getattr(file_obj, 'content_type', '') or ''
    return extension in ALLOWED_EXTENSIONS and (mime_type in ALLOWED_MIME_TYPES or extension == '.pdf')


def validate_supplier_payload(payload: Dict[str, object], files: Dict[str, object], categories: List[str]) -> List[str]:
    errors: List[str] = []
    company_name = sanitize_text(payload.get('companyName'))
    business_type = sanitize_text(payload.get('businessType')) or 'Sole Proprietorship'
    business_address = sanitize_text(payload.get('businessAddress'))
    contact_person = sanitize_text(payload.get('contactPerson'))
    contact_number = sanitize_text(payload.get('contactNumber'))
    email = sanitize_text(payload.get('email'))
    products_services = sanitize_text(payload.get('productsServices'))
    category_values = [sanitize_text(item) for item in (payload.get('categories') or []) if sanitize_text(item)]

    if not company_name:
        errors.append('Company Name is required')
    if not business_address:
        errors.append('Business Address is required')
    if not contact_person:
        errors.append('Contact Person is required')
    if not contact_number or not re.fullmatch(r'^(\+63|63|0)?[0-9\s\-]{7,15}$', contact_number):
        errors.append('Phone number must be valid')
    if not email or not re.fullmatch(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        errors.append('Email address must be valid')
    if not products_services:
        errors.append('Products or services description is required')
    if not category_values:
        errors.append('At least one category must be selected')

    business_document_key = get_required_business_document_key(business_type)
    if business_document_key and not files.get(business_document_key):
        errors.append(f'{REQUIRED_DOCUMENTS.get(business_document_key, "Required document")} is required')

    for key in REQUIRED_UPLOAD_KEYS:
        if not files.get(key):
            errors.append(f'{REQUIRED_DOCUMENTS.get(key, key)} is required')

    for key, file_obj in files.items():
        if isinstance(file_obj, list):
            for item in file_obj:
                if item is None:
                    continue
                if item.size > MAX_UPLOAD_SIZE:
                    errors.append(f'{getattr(item, "name", key)} exceeds the 10MB upload limit')
                if not is_supported_file(item):
                    errors.append(f'{getattr(item, "name", key)} has an unsupported file type')
            continue
        if file_obj is None:
            continue
        if getattr(file_obj, 'size', 0) > MAX_UPLOAD_SIZE:
            errors.append(f'{getattr(file_obj, "name", key)} exceeds the 10MB upload limit')
        if not is_supported_file(file_obj):
            errors.append(f'{getattr(file_obj, "name", key)} has an unsupported file type')

    return errors


def _save_supplier_upload(uploaded_file) -> str:
    upload_dir = Path(settings.BASE_DIR) / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_name = Path(getattr(uploaded_file, 'name', 'upload.bin') or 'upload.bin').name
    safe_name = f"{uuid.uuid4().hex}_{original_name}"
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', safe_name)
    destination = upload_dir / safe_name

    with destination.open('wb') as handle:
        for chunk in uploaded_file.chunks():
            handle.write(chunk)

    return safe_name


def build_supplier_registration_context() -> Dict[str, object]:
    return {
        'required_documents': REQUIRED_DOCUMENTS,
        'required_upload_keys': REQUIRED_UPLOAD_KEYS,
        'business_document_keys': BUSINESS_DOCUMENT_KEYS,
        'max_upload_size': MAX_UPLOAD_SIZE,
        'allowed_extensions': sorted(ALLOWED_EXTENSIONS),
    }

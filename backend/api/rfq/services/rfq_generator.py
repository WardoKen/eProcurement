from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from api.rfq.procurement_modes import normalize_procurement_mode


def _format_quantity(value) -> str:
    """Render a PR item quantity without noise trailing zeros (1.00 -> "1")."""
    if value is None:
        return ''
    text = f'{value:.2f}'.rstrip('0').rstrip('.')
    return text or '0'


def _resolve_rfq_dir() -> Path:
    target_dir = Path(settings.BASE_DIR) / 'uploads' / 'rfq'
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


# Scanned signature of the BAC Secretariat signatory. Drop a PNG (transparent or
# white background, signature strokes only) at this path to have it embedded in
# the generated RFQ; if the file is absent the template falls back to a blank
# signature line.
SIGNATURE_FILE = Path(settings.BASE_DIR) / 'api' / 'rfq' / 'assets' / 'signature.png'
SIGNATORY_NAME = 'LURIZA L. PRESBITERO'
SIGNATORY_ROLE = 'Member, BAC Secretariat'


def generate_rfq_pdf(rfq) -> tuple[str, str]:
    """Render a printable RFQ PDF and return the public file URL and filesystem path."""
    pr = rfq.purchase_request
    supplier = rfq.supplier

    abc_value = rfq.abc or (f"Php{float(pr.grand_total or 0):,.2f}" if pr.grand_total else 'Php0.00')
    # xhtml2pdf's built-in fonts have no peso glyph, so normalise it to "Php".
    abc_value = abc_value.replace('₱', 'Php ').strip()

    # Authoritative source for the RFQ item table: the structured
    # PurchaseRequestItem rows saved by the PR workflow. Each database item maps
    # to exactly one RFQ row - the raw OCR / PR text is never used here.
    #
    # A category-group RFQ lists ONLY its own items (recorded in ``rfq_items``).
    # Legacy RFQs created before category grouping have no ``rfq_items`` rows and
    # fall back to every item on the PR.
    linked = list(
        rfq.rfq_items.select_related('purchase_request_item')
        .order_by('purchase_request_item_id')
    )
    source_items = (
        [li.purchase_request_item for li in linked] if linked
        else list(pr.line_items.all())
    )
    items = []
    for idx, item in enumerate(source_items, start=1):
        items.append({
            'index': idx,
            'item_description': (item.item_description or 'N/A').strip(),
            'quantity': item.quantity,
            'quantity_display': _format_quantity(item.quantity),
            'unit': (item.unit or '').strip(),
            'stock_property_no': (item.stock_property_no or '').strip(),
        })

    context = {
        'rfq_no': rfq.rfq_no or 'RFQ',
        'pr_no': pr.pr_no or f'PR-{pr.id}',
        'pr_date': (pr.date.isoformat() if pr.date else ''),
        # The RFQ number doubles as the Quotation No. on the printed form - a
        # single RFQ-YYYY-NNNN sequence shared by registered and manual RFQs. A
        # draft preview has no number yet.
        'quotation_no': rfq.rfq_no or 'To be assigned',
        # Admin-selected value; never defaulted here so a blank never slips into
        # a generated document. The RFQ API enforces a valid selection before
        # a PDF is produced.
        'mode_of_procurement': normalize_procurement_mode(rfq.mode_of_procurement),
        'quotation_basis': (rfq.quotation_basis or 'LOT').upper(),
        # Company Name, Address and TIN are deliberately left blank on the
        # generated RFQ - the supplier writes them in by hand on the printed
        # copy they download. A manual / unregistered supplier has no Supplier
        # record at all; its name is internal metadata and never reaches the PDF.
        'supplier': {
            'company_name': '',
            'business_address': '',
            'tin': '',
            'contact_person': getattr(supplier, 'contact_person', '') or '',
            'email': getattr(supplier, 'email', '') or '',
        },
        'abc': abc_value,
        'additional_notes': rfq.additional_notes or '',
        'items': items,
        'signatory_name': SIGNATORY_NAME,
        'signatory_role': SIGNATORY_ROLE,
        'signature_url': str(SIGNATURE_FILE) if SIGNATURE_FILE.is_file() else '',
    }

    html = render_to_string('rfq/rfq.html', context)
    output_dir = _resolve_rfq_dir()
    safe_name = f"{rfq.rfq_no or 'rfq'}-{rfq.id}.pdf"
    safe_name = safe_name.replace(' ', '_')
    output_path = output_dir / safe_name

    with open(output_path, 'wb') as pdf_file:
        pisa_status = pisa.CreatePDF(html, dest=pdf_file)

    if pisa_status.err:
        raise ValueError('PDF generation failed.')

    public_path = f'/uploads/rfq/{safe_name}'
    return public_path, str(output_path)

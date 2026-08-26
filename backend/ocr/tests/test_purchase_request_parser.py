import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ocr.purchase_request_parser import parse_purchase_request
from ocr.textract_purchase_request_parser import parse_ctu_purchase_request, parse_item_row, reconstruct_item_rows

SAMPLE_PDF_PATH = BACKEND_ROOT / 'uploads' / '1783518303882_Purchase-Requests-MIS-aircon2026.pdf'
purchase_request_parser = sys.modules['ocr.purchase_request_parser']


def test_parse_purchase_request_sections():
    raw_text = '''Purchase Request
Entity Name: State University
Fund Cluster: 01
Office/Section: BAC Office
PR No: 2026-01-010
Date: 2026-07-08
Responsibility Center Code: RCC-001

Item Description
Stock/Property No.
Unit
Item Description
Quantity
Unit Cost
Total Cost
Supply and Delivery of 4.0HP FLOOR STANDING,
INVERTER TYPE AIR CONDITIONING
UNIT including labor charges for the installation, testing
and commissioning:
Capacity: 3 Tons of Refrigeration (3TR) / 4.0 HP
Cooling Capacity: Approx. 36,000 BTU/h (4,200 watts)
Refrigerant: R32 (Eco-friendly)
Power Supply: 220–240V / 60Hz / 1 Phase
Energy Efficiency: DC Inverter with high EER
Corrosion Protection: Hyper Grapfins (12.5x more resistant
than standard blue fins)
Airflow: Automatic Swing (Motorized Louver)
At least Five (5) Years warranty for COMPRESSOR.
At least One (1) Year warranty for PARTS.
1
145,000
145,000.00
145,000.00

Purpose
Supply and delivery of air-conditioning unit for the BAC office.

Requested by
Printed Name : ENGR. NOEL T. DERECHO
Designation :
TWG-ELECTRICAL & MECHANICAL

Funds Available
Printed Name : JUAN D. DELA CRUZ
Designation : Budget Officer

Approved by
Printed Name : MARIA S. SANTOS
Designation : Campus Director

Specifications verified by Technical Working Group
Printed Name : ENGR. NOEL T. DERECHO
Designation : TWG-ELECTRICAL & MECHANICAL
'''

    result = parse_purchase_request(raw_text)

    assert result['entityName'] == 'State University'
    assert result['fundCluster'] == '01'
    assert result['officeSection'] == 'BAC Office'
    assert result['prNumber'] == '2026-01-010'
    assert result['date'] == '2026-07-08'
    assert result['responsibilityCenterCode'] == 'RCC-001'
    assert result['purpose'] == 'Supply and delivery of air-conditioning unit for the BAC office.'
    assert result['requested_items'][0]['description'].startswith('Supply and Delivery of 4.0HP FLOOR STANDING,')
    assert result['requested_items'][0]['quantity'] == '1'
    assert result['requested_items'][0]['unit_cost'] == '145,000'
    assert result['requested_items'][0]['total_cost'] == '145,000.00'
    assert result['requested_by_name'] == 'ENGR. NOEL T. DERECHO'
    assert result['requested_by_designation'] == 'TWG-ELECTRICAL & MECHANICAL'
    assert result['funds_available_name'] == 'JUAN D. DELA CRUZ'
    assert result['funds_available_designation'] == 'Budget Officer'
    assert result['approved_by_name'] == 'MARIA S. SANTOS'
    assert result['approved_by_designation'] == 'Campus Director'
    assert result['twg_name'] == 'ENGR. NOEL T. DERECHO'
    assert result['twg_designation'] == 'TWG-ELECTRICAL & MECHANICAL'


def test_parse_purchase_request_structured_output():
    raw_text = '''Purchase Request
Entity Name: State University
Fund Cluster: 01
Office/Section: BAC Office
PR No: 2026-01-010
Date: 2026-07-08
Responsibility Center Code: RCC-001

Item Description
Unit
Quantity
Unit Cost
Total Cost
Air Conditioning Unit
1
145,000
145,000.00

Purpose
Supply and delivery of air-conditioning unit for the BAC office.

Requested by
Printed Name : ENGR. NOEL T. DERECHO
Designation : TWG-ELECTRICAL & MECHANICAL

Approved by
Printed Name : MARIA S. SANTOS
Designation : Campus Director
'''

    result = parse_purchase_request(raw_text)

    assert result['header']['entityName'] == 'State University'
    assert result['header']['fundCluster'] == '01'
    assert result['header']['office'] == 'BAC Office'
    assert result['header']['prNumber'] == '2026-01-010'
    assert result['items'][0]['description'] == 'Air Conditioning Unit'
    assert result['items'][0]['quantity'] == '1'
    assert result['items'][0]['unitCost'] == '145,000'
    assert result['items'][0]['totalCost'] == '145,000.00'
    assert result['requestedBy']['name'] == 'ENGR. NOEL T. DERECHO'
    assert result['approvedBy']['name'] == 'MARIA S. SANTOS'
    assert result['validation']['fields']['entityName']['confidence'] >= 0.8


def test_parse_purchase_request_uses_layout_sections_and_footer():
    layout = {
        'blocks': [
            {'text': 'Entity Name', 'confidence': 0.95, 'bbox': [[0.0, 0.0], [0.2, 0.0], [0.2, 0.03], [0.0, 0.03]], 'page': 1},
            {'text': 'State University', 'confidence': 0.91, 'bbox': [[0.25, 0.0], [0.5, 0.0], [0.5, 0.03], [0.25, 0.03]], 'page': 1},
            {'text': 'Item Description', 'confidence': 0.97, 'bbox': [[0.0, 0.08], [0.2, 0.08], [0.2, 0.11], [0.0, 0.11]], 'page': 1},
            {'text': 'Air Conditioning Unit', 'confidence': 0.9, 'bbox': [[0.0, 0.12], [0.45, 0.12], [0.45, 0.15], [0.0, 0.15]], 'page': 1},
            {'text': '1', 'confidence': 0.92, 'bbox': [[0.45, 0.12], [0.55, 0.12], [0.55, 0.15], [0.45, 0.15]], 'page': 1},
            {'text': '145,000', 'confidence': 0.91, 'bbox': [[0.55, 0.12], [0.7, 0.12], [0.7, 0.15], [0.55, 0.15]], 'page': 1},
            {'text': '145,000.00', 'confidence': 0.9, 'bbox': [[0.7, 0.12], [0.85, 0.12], [0.85, 0.15], [0.7, 0.15]], 'page': 1},
            {'text': 'Purpose', 'confidence': 0.96, 'bbox': [[0.0, 0.2], [0.12, 0.2], [0.12, 0.23], [0.0, 0.23]], 'page': 1},
            {'text': 'Supply and delivery of air-conditioning unit for the BAC office.', 'confidence': 0.88, 'bbox': [[0.0, 0.24], [0.9, 0.24], [0.9, 0.27], [0.0, 0.27]], 'page': 1},
            {'text': 'Requested by', 'confidence': 0.95, 'bbox': [[0.0, 0.3], [0.18, 0.3], [0.18, 0.33], [0.0, 0.33]], 'page': 1},
            {'text': 'Printed Name : ENGR. NOEL T. DERECHO', 'confidence': 0.92, 'bbox': [[0.0, 0.34], [0.45, 0.34], [0.45, 0.37], [0.0, 0.37]], 'page': 1},
        ],
        'sections': {
            'header': [
                {'text': 'Entity Name', 'confidence': 0.95, 'bbox': [[0.0, 0.0], [0.2, 0.0], [0.2, 0.03], [0.0, 0.03]], 'page': 1},
                {'text': 'State University', 'confidence': 0.91, 'bbox': [[0.25, 0.0], [0.5, 0.0], [0.5, 0.03], [0.25, 0.03]], 'page': 1},
            ],
            'items': [
                {'text': 'Item Description', 'confidence': 0.97, 'bbox': [[0.0, 0.08], [0.2, 0.08], [0.2, 0.11], [0.0, 0.11]], 'page': 1},
                {'text': 'Air Conditioning Unit', 'confidence': 0.9, 'bbox': [[0.0, 0.12], [0.45, 0.12], [0.45, 0.15], [0.0, 0.15]], 'page': 1},
                {'text': '1', 'confidence': 0.92, 'bbox': [[0.45, 0.12], [0.55, 0.12], [0.55, 0.15], [0.45, 0.15]], 'page': 1},
                {'text': '145,000', 'confidence': 0.91, 'bbox': [[0.55, 0.12], [0.7, 0.12], [0.7, 0.15], [0.55, 0.15]], 'page': 1},
                {'text': '145,000.00', 'confidence': 0.9, 'bbox': [[0.7, 0.12], [0.85, 0.12], [0.85, 0.15], [0.7, 0.15]], 'page': 1},
            ],
            'footer': [
                {'text': 'Purpose', 'confidence': 0.96, 'bbox': [[0.0, 0.2], [0.12, 0.2], [0.12, 0.23], [0.0, 0.23]], 'page': 1},
                {'text': 'Supply and delivery of air-conditioning unit for the BAC office.', 'confidence': 0.88, 'bbox': [[0.0, 0.24], [0.9, 0.24], [0.9, 0.27], [0.0, 0.27]], 'page': 1},
                {'text': 'Requested by', 'confidence': 0.95, 'bbox': [[0.0, 0.3], [0.18, 0.3], [0.18, 0.33], [0.0, 0.33]], 'page': 1},
                {'text': 'Printed Name : ENGR. NOEL T. DERECHO', 'confidence': 0.92, 'bbox': [[0.0, 0.34], [0.45, 0.34], [0.45, 0.37], [0.0, 0.37]], 'page': 1},
            ],
        },
    }

    result = parse_purchase_request('', layout)

    assert result['header']['entityName'] == 'State University'
    assert result['items'][0]['description'] == 'Air Conditioning Unit'
    assert result['items'][0]['quantity'] == '1'
    assert result['footer']['purpose'] == 'Supply and delivery of air-conditioning unit for the BAC office.'
    assert result['requestedBy']['name'] == 'ENGR. NOEL T. DERECHO'


def test_pdf_service_returns_text_document_when_pdf_conversion_is_unavailable():
    if not SAMPLE_PDF_PATH.exists():
        return

    from ocr.ocr_service import PaddleOCRService

    service = PaddleOCRService(language='en')
    document = service.process_file(SAMPLE_PDF_PATH, SAMPLE_PDF_PATH.name)

    assert document.source == 'pdf'
    assert document.filename == SAMPLE_PDF_PATH.name
    assert document.pages == []
    assert 'PURCHASE REQUEST' in document.raw_text
    assert 'Entity Name:' in document.raw_text


def test_parse_purchase_request_does_not_restore_colon_placeholders(monkeypatch):
    structured = {
        "entity_name": "CTU-Tuburan Campus",
        "fund_cluster": "",
        "office": "MIS",
        "pr_number": "",
        "date": "",
        "responsibility_center_code": "",
        "purpose": "Replacement of unit",
        "requested_by": "",
        "budget_officer": "",
        "approved_by": "",
        "twg": "",
        "signatory_designations": {
            "requested_by": "",
            "budget_officer": "",
            "approved_by": "",
            "twg": "",
        },
        "signatory_names": {
            "requested_by": "",
            "budget_officer": "",
            "approved_by": "",
            "twg": "",
        },
        "items": [],
        "fields_confidence": {},
    }

    def fake_parse_ctu_purchase_request(_blocks):
        return structured

    monkeypatch.setattr(purchase_request_parser, "parse_ctu_purchase_request", fake_parse_ctu_purchase_request)

    raw_text = """Purchase Request
Entity Name: CTU-Tuburan Campus
Fund Cluster:
Office/Section : MIS
PR No.:
Date:
Responsibility Center Code :
Purpose: Replacement of unit
"""

    result = parse_purchase_request(raw_text, layout={}, textract_blocks=[{"BlockType": "LINE", "Text": "dummy"}])

    assert result["fundCluster"] == ""
    assert result["prNumber"] == ""
    assert result["date"] == ""
    assert result["responsibilityCenterCode"] == ""


def test_parse_ctu_purchase_request_maps_grouped_signatories_to_correct_fields():
    def line(text: str, top: float) -> dict:
        return {
            "BlockType": "LINE",
            "Text": text,
            "Confidence": 99.0,
            "Page": 1,
            "Geometry": {"BoundingBox": {"Top": top, "Left": 0.1}},
        }

    blocks = [
        line("Entity Name: CTU-Tuburan Campus", 0.05),
        line("Office/Section: MIS", 0.08),
        line("Purpose:", 0.55),
        line("Replacement of irreparable unit", 0.58),
        line("Requested by:", 0.62),
        line("Funds Available:", 0.64),
        line("Approved by:", 0.66),
        line("Signature :", 0.68),
        line("Printed Name : ENGR. NAOMI A. BAJAO", 0.70),
        line("MRS. JANVENETH T. SASUTANA", 0.72),
        line("DR. MA CARLA Y. ABAQUITA", 0.74),
        line("Designation :", 0.76),
        line("MIS Chair", 0.78),
        line("AO IV / Budget Officer 2", 0.80),
        line("Campus Director", 0.82),
        line("Specifications verified by Technical Working Group:", 0.86),
        line("Printed Name : ENGR. NOEL T. DERECHO", 0.88),
        line("Designation : TWG-ELECTRICAL & MECHANICAL", 0.90),
    ]

    result = parse_ctu_purchase_request(blocks)

    assert result["requested_by"] == "ENGR. NAOMI A. BAJAO"
    assert result["budget_officer"] == "MRS. JANVENETH T. SASUTANA"
    assert result["approved_by"] == "DR. MA CARLA Y. ABAQUITA"
    assert result["signatory_designations"]["requested_by"] == "MIS Chair"
    assert result["signatory_designations"]["budget_officer"] == "AO IV / Budget Officer 2"
    assert result["signatory_designations"]["approved_by"] == "Campus Director"


def test_textract_reconstructs_wrapped_description_until_numeric_row():
    def row(row_index, description='', unit='', quantity='', unit_cost='', total_cost=''):
        values = {
            3: description,
            4: unit,
            5: quantity,
            6: unit_cost,
            7: total_cost,
        }
        return {
            'row_index': row_index,
            'confidence': 90.0,
            'cells': [
                {'column_index': column, 'text': value, 'confidence': 90.0}
                for column, value in values.items()
                if value
            ],
        }

    header_map = {'description': 3, 'unit': 4, 'quantity': 5, 'unit_cost': 6, 'total_cost': 7}
    rows = [
        row(3, 'Supply and Delivery of 4.0HP FLOOR STANDING,'),
        row(4, 'Capacity: 3 Tons of Refrigeration'),
        row(5, 'Airflow: Automatic Swing (Motorized Louver)', 'unit', '1', '145,000', '145,000.00'),
        row(6, 'nothing follows', total_cost='-'),
    ]

    reconstructed = reconstruct_item_rows(rows, header_map)
    item = parse_item_row(reconstructed[0], header_map)

    assert len(reconstructed) == 1
    assert item.description == 'Supply and Delivery of 4.0HP FLOOR STANDING,\nCapacity: 3 Tons of Refrigeration\nAirflow: Automatic Swing (Motorized Louver)'
    assert item.unit == 'unit'
    assert item.quantity == 1
    assert item.unit_cost == 145000
    assert item.total_cost == 145000

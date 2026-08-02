import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ocr.purchase_request_parser import parse_purchase_request
from backend.ocr.ocr_service import TextractOCRService

# Try optional libs
ocr_service = TextractOCRService(language='en')


def extract_text_from_upload(path: Path, filename: str) -> tuple[str, str]:
    lower_name = filename.lower()
    if lower_name.endswith('.pdf') or lower_name.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff', '.tif')):
        document = ocr_service.process_file(path, filename)
        return document.raw_text, document.source
    return '', 'none'


UPLOAD_DIR = ROOT / 'backend' / 'uploads'

for f in sorted(UPLOAD_DIR.iterdir()):
    if f.suffix.lower() not in ('.pdf', '.png', '.jpg', '.jpeg'):
        continue
    print('---', f.name)
    text, source = extract_text_from_upload(f, f.name)
    print('source:', source)
    if not text:
        print('No text extracted\n')
        continue
    parsed = parse_purchase_request(text)
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    print()

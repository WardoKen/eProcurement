import json
import sys
from pathlib import Path

# Ensure workspace root is on sys.path so we can import backend modules
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ocr.purchase_request_parser import parse_purchase_request

p = ROOT / 'uploads' / 'sample_pr.txt'
text = p.read_text(encoding='utf-8')
result = parse_purchase_request(text)
print(json.dumps(result, indent=2, ensure_ascii=False))

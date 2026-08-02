import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.ocr.purchase_request_parser import parse_purchase_request

search_paths = [ROOT / 'uploads', ROOT / 'backend' / 'uploads']

for p in search_paths:
    if not p.exists():
        continue
    for f in sorted(p.iterdir()):
        if f.suffix.lower() != '.txt':
            continue
        print('---', f.relative_to(ROOT))
        text = f.read_text(encoding='utf-8')
        out = parse_purchase_request(text)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        print()

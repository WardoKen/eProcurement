import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ocr.textract_purchase_request_parser import parse_ctu_purchase_request


KEYWORDS = [
    "requested by",
    "funds available",
    "approved by",
    "technical working group",
    "specifications verified",
    "printed name",
    "designation",
    "signature",
]


def normalize(value: str) -> str:
    return " ".join((value or "").split()).strip()


def is_signatory_line(text: str) -> bool:
    low = normalize(text).lower()
    return any(keyword in low for keyword in KEYWORDS)


def read_textract_blocks(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "Blocks" in payload:
        return payload.get("Blocks") or []
    if isinstance(payload, list):
        return payload
    return []


def line_rows(blocks: list[dict]) -> list[dict]:
    rows = []
    for block in blocks:
        if block.get("BlockType") != "LINE":
            continue
        text = normalize(str(block.get("Text") or ""))
        if not text:
            continue
        bbox = ((block.get("Geometry") or {}).get("BoundingBox") or {})
        rows.append(
            {
                "page": int(block.get("Page", 1) or 1),
                "top": float(bbox.get("Top") or 0.0),
                "left": float(bbox.get("Left") or 0.0),
                "text": text,
            }
        )

    rows.sort(key=lambda row: (row["page"], row["top"], row["left"]))
    return rows


def signatory_window(rows: list[dict]) -> list[dict]:
    start = None
    end = None
    for idx, row in enumerate(rows):
        low = row["text"].lower()
        if start is None and "requested by" in low:
            start = idx
        if "specifications verified by technical working group" in low:
            end = idx
            break

    if start is None:
        return []
    if end is None:
        end = min(len(rows) - 1, start + 30)
    return rows[start : end + 1]


def main() -> int:
    default_path = ROOT / "debug" / "textract_response.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    if not path.exists():
        print(f"Input not found: {path}")
        return 1

    blocks = read_textract_blocks(path)
    if not blocks:
        print("No Textract blocks found in input JSON.")
        return 1

    parsed = parse_ctu_purchase_request(blocks)

    print("=== Signatory Lines (ordered) ===")
    for row in line_rows(blocks):
        if is_signatory_line(row["text"]):
            print(
                f"page={row['page']} top={row['top']:.4f} left={row['left']:.4f} | {row['text']}"
            )

    rows = line_rows(blocks)
    window = signatory_window(rows)
    if window:
        print("\n=== Footer Window (Requested by -> TWG heading) ===")
        for row in window:
            print(
                f"page={row['page']} top={row['top']:.4f} left={row['left']:.4f} | {row['text']}"
            )

    print("\n=== Structured Extraction (roles) ===")
    print(json.dumps({
        "requested_by": parsed.get("requested_by", ""),
        "budget_officer": parsed.get("budget_officer", ""),
        "approved_by": parsed.get("approved_by", ""),
        "twg": parsed.get("twg", ""),
    }, indent=2))

    print("\n=== Signatory Names ===")
    print(json.dumps(parsed.get("signatory_names", {}), indent=2))

    print("\n=== Signatory Designations ===")
    print(json.dumps(parsed.get("signatory_designations", {}), indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

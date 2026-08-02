from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

try:
    from .ocr_service import OCRDocument, OCRPage, OCRToken
except ImportError:  # pragma: no cover
    from backend.ocr.ocr_service import OCRDocument, OCRPage, OCRToken


class DocumentLayoutParser:
    def __init__(self) -> None:
        self._label_patterns = {
            "entityName": [r"entity\s+name", r"name\s+of\s+entity"],
            "fundCluster": [r"fund\s+cluster"],
            "office": [r"office\s*/\s*section", r"office\s*/\s*department", r"office"],
            "prNumber": [r"pr\s*(no|number)?", r"pr\s*no"],
            "date": [r"date"],
            "responsibilityCenterCode": [r"responsibility\s+center\s+code", r"responsibility\s+center"],
            "purpose": [r"purpose"],
            "requestedBy": [r"requested\s+by"],
            "approvedBy": [r"approved\s+by"],
        }

    def parse(self, document: OCRDocument) -> dict[str, Any]:
        blocks: List[dict[str, Any]] = []
        for page in document.pages:
            for line in page.lines:
                if not line.text or not line.text.strip():
                    continue
                blocks.append({
                    "text": line.text.strip(),
                    "confidence": line.confidence,
                    "bbox": line.bbox,
                    "page": page.page_number,
                })

        blocks.sort(key=lambda item: (item["page"], item["bbox"][0][0] if item.get("bbox") else 0))
        return {
            "blocks": blocks,
            "text": document.raw_text,
            "line_count": len(blocks),
        }

    def find_value(self, blocks: List[dict[str, Any]], labels: List[str]) -> str:
        label_pattern = re.compile(r"|".join(re.escape(label) for label in labels), re.I)
        for block in blocks:
            text = block.get("text", "")
            match = re.match(rf"^(?:{label_pattern.pattern})\s*[:\-]?\s*(.+)$", text, re.I)
            if match:
                return self._clean(match.group(1))
        return ""

    def _clean(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

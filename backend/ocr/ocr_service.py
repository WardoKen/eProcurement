from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
from PIL import Image as PILImage

try:
    from pdfminer.high_level import extract_text as extract_pdf_text
except ImportError:  # pragma: no cover
    extract_pdf_text = None

@dataclass
class OCRToken:
    text: str
    confidence: float
    bbox: Optional[List[Tuple[float, float, float, float]]] = None
    page: int = 0


@dataclass
class OCRPage:
    page_number: int
    lines: List[OCRToken] = field(default_factory=list)
    tables: List[Any] = field(default_factory=list)  # List of Table objects
    width: int = 0
    height: int = 0


@dataclass
class OCRDocument:
    pages: List[OCRPage] = field(default_factory=list)
    raw_text: str = ""
    source: str = ""
    filename: str = ""
    textract_response: Dict[str, Any] = field(default_factory=dict)
    textract_blocks: List[Dict[str, Any]] = field(default_factory=list)
    all_tables: List[Any] = field(default_factory=list)  # All tables across all pages

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "filename": self.filename,
            "raw_text": self.raw_text,
            "pages": [
                {
                    "page_number": page.page_number,
                    "width": page.width,
                    "height": page.height,
                    "lines": [
                        {
                            "text": line.text,
                            "confidence": line.confidence,
                            "bbox": line.bbox,
                            "page": line.page,
                        }
                        for line in page.lines
                    ],
                    "tables": [
                        table.to_dict() if hasattr(table, "to_dict") else table
                        for table in page.tables
                    ],
                }
                for page in self.pages
            ],
            "all_tables": [
                table.to_dict() if hasattr(table, "to_dict") else table
                for table in self.all_tables
            ],
        }


class TextractOCRService:
    def __init__(self, language: str = "en") -> None:
        self.language = language
        self._client = boto3.client(
            "textract",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or None,
            region_name=os.getenv("AWS_REGION") or None,
        )

    def process_file(self, path: Path, filename: str) -> OCRDocument:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            source = "pdf"
        elif suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}:
            source = "image"
        else:
            pages: List[OCRPage] = []
            source = "unsupported"
            return OCRDocument(pages=pages, raw_text="", source=source, filename=filename)

        document = self._process_with_textract(path, filename, source)
        if document.textract_blocks:
            return document

        # Use plain PDF text only as fallback when Textract blocks are unavailable.
        if suffix == ".pdf" and extract_pdf_text is not None:
            try:
                raw_text = extract_pdf_text(str(path))
            except Exception:
                raw_text = ""
            if raw_text:
                return OCRDocument(
                    pages=[],
                    raw_text=raw_text.strip(),
                    source="pdf-text",
                    filename=filename,
                    textract_blocks=[],
                    all_tables=[],
                )
        return document

    def _process_with_textract(self, path: Path, filename: str, source: str) -> OCRDocument:
        response = self._analyze_document(path)
        if response is None:
            return OCRDocument(pages=[], raw_text="", source=source, filename=filename)

        blocks = response.get("Blocks", [])
        line_blocks = [block for block in blocks if block.get("BlockType") == "LINE"]
        table_blocks = [block for block in blocks if block.get("BlockType") == "TABLE"]
        page_map: dict[int, OCRPage] = {}
        page_texts: dict[int, List[str]] = {}

        for block in line_blocks:
            page_number = int(block.get("Page", 1) or 1)
            text_value = str(block.get("Text") or "").strip()
            if not text_value:
                continue

            page = page_map.setdefault(page_number, OCRPage(page_number=page_number))
            bbox = self._normalize_textract_bbox(block)
            confidence = float(block.get("Confidence") or 0.0)
            page.lines.append(OCRToken(text=text_value, confidence=confidence, bbox=bbox, page=page_number))
            page_texts.setdefault(page_number, []).append(text_value)

        if source == "image":
            width, height = self._load_image_size(path)
            for page in page_map.values():
                page.width = width
                page.height = height

        ordered_pages = [page_map[key] for key in sorted(page_map.keys())]
        raw_text = "\n\n".join("\n".join(page_texts[key]) for key in sorted(page_texts.keys())).strip()
        table_summaries = [
            {
                "id": block.get("Id"),
                "page": int(block.get("Page", 1) or 1),
                "confidence": float(block.get("Confidence") or 0.0),
            }
            for block in table_blocks
        ]

        return OCRDocument(
            pages=ordered_pages,
            raw_text=raw_text,
            source="textract",
            filename=filename,
            textract_response=response,
            textract_blocks=blocks,
            all_tables=table_summaries,
        )

    def _analyze_document(self, path: Path) -> Optional[dict[str, Any]]:
        try:
            with open(path, "rb") as file_handle:
                payload = file_handle.read()
        except Exception:
            return None

        try:
            return self._client.analyze_document(
                Document={"Bytes": payload},
                FeatureTypes=["TABLES", "FORMS"],
            )
        except Exception:
            try:
                return self._client.detect_document_text(Document={"Bytes": payload})
            except Exception:
                return None

    def _load_image_size(self, path: Path) -> Tuple[int, int]:
        try:
            with PILImage.open(path) as image:
                return image.width, image.height
        except Exception:
            return 0, 0

    def _normalize_textract_bbox(
        self,
        block: dict[str, Any],
    ) -> Optional[List[Tuple[float, float, float, float]]]:
        geometry = block.get("Geometry") or {}
        polygon = geometry.get("Polygon") or []
        if not isinstance(polygon, list) or not polygon:
            return None

        normalized: List[Tuple[float, float, float, float]] = []
        for point in polygon:
            if not isinstance(point, dict):
                continue
            x = float(point.get("X") or 0.0)
            y = float(point.get("Y") or 0.0)
            normalized.append((x, y, x, y))
        return normalized or None

class PaddleOCRService(TextractOCRService):
    """Backward-compatible alias for older imports."""

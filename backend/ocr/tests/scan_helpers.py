"""Turn a clean synthetic PR PDF into a realistic scanned copy for tests.

A real scan has no text layer, so the detector depends on OCR geometry. These
helpers produce both halves deterministically, without AWS:

* ``degrade_to_scan`` - rasterise the page and make it look scanned: gray
  paper, sensor noise, dust speckle and a slight rotation; saved as an
  image-only PDF.
* ``textract_blocks_for`` - Textract-shaped LINE and WORD blocks for the same
  page, built from the clean PDF's exact text layout and rotated the same way
  as the scan, so the boxes line up with the scanned image.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from ocr.signature_detection import _lines_from_pdf_layout

SCAN_DPI = 200
PAPER_LEVEL = 226  # gray recycled / scanner-tinted paper, not 255 white


def _render_gray(pdf_path: Path, dpi: int) -> np.ndarray:
    import pymupdf

    doc = pymupdf.open(str(pdf_path))
    try:
        page = doc[0]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)[:, : pix.width].copy()
    finally:
        doc.close()


def degrade_to_scan(clean_pdf: Path, out_pdf: Path, *, angle_deg: float = 1.0, seed: int = 7) -> Tuple[int, int]:
    """Write an image-only "scanned" copy of ``clean_pdf``; returns (w, h) px."""
    rng = np.random.default_rng(seed)
    gray = _render_gray(clean_pdf, SCAN_DPI).astype("float32")
    # Paper turns gray; ink keeps its darkness relative to it.
    gray = gray * (PAPER_LEVEL / 255.0)
    gray += rng.normal(0.0, 4.0, gray.shape)
    # Dust: isolated dark pixels and a few 2x2 specks.
    h, w = gray.shape
    for _ in range(int(0.0004 * h * w)):
        y, x = rng.integers(0, h - 2), rng.integers(0, w - 2)
        size = 2 if rng.random() < 0.2 else 1
        gray[y:y + size, x:x + size] = rng.integers(40, 120)
    image = Image.fromarray(np.clip(gray, 0, 255).astype("uint8"))
    image = image.rotate(angle_deg, resample=Image.BICUBIC, fillcolor=PAPER_LEVEL)
    image.save(out_pdf, "PDF", resolution=SCAN_DPI)
    return image.size


def _rotate_box(box, angle_deg: float, w: int, h: int):
    """Rotate a normalized box the way ``Image.rotate`` rotates the page."""
    x0, y0, x1, y1 = box
    theta = math.radians(angle_deg)
    cx, cy = w / 2.0, h / 2.0
    pts = []
    for nx, ny in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        dx, dy = nx * w - cx, ny * h - cy
        rx = cx + dx * math.cos(theta) + dy * math.sin(theta)
        ry = cy - dx * math.sin(theta) + dy * math.cos(theta)
        pts.append((rx / w, ry / h))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _block(block_type: str, text: str, box, text_type: Optional[str] = None) -> Dict:
    x0, y0, x1, y1 = box
    block = {
        "BlockType": block_type,
        "Text": text,
        "Page": 1,
        "Confidence": 99.0,
        "Geometry": {"BoundingBox": {"Left": x0, "Top": y0, "Width": x1 - x0, "Height": y1 - y0}},
    }
    if text_type:
        block["TextType"] = text_type
    return block


def textract_blocks_for(
    clean_pdf: Path,
    *,
    angle_deg: float = 0.0,
    size: Tuple[int, int] = (1, 1),
    extra_words: Optional[List[Tuple[str, Tuple[float, float, float, float], str]]] = None,
) -> List[Dict]:
    """LINE + WORD blocks for the clean page, rotated to match the scan.

    ``extra_words`` adds words such as a signature Textract read as text:
    ``(text, (x0, y0, x1, y1) in the clean page, "HANDWRITING"|"PRINTED")``.
    """
    w, h = size
    blocks: List[Dict] = []
    for line in _lines_from_pdf_layout(clean_pdf):
        blocks.append(_block("LINE", line.text, _rotate_box((line.x0, line.y0, line.x1, line.y1), angle_deg, w, h)))
        word, start, end = "", None, None
        for ch, cx0, cx1 in (line.char_boxes or []) + [(" ", None, None)]:
            if ch.isspace():
                if word:
                    box = _rotate_box((start, line.y0, end, line.y1), angle_deg, w, h)
                    blocks.append(_block("WORD", word, box, "PRINTED"))
                word, start, end = "", None, None
                continue
            word += ch
            start = cx0 if start is None else start
            end = cx1
    for text, box, text_type in extra_words or []:
        rotated = _rotate_box(box, angle_deg, w, h)
        blocks.append(_block("LINE", text, rotated))
        blocks.append(_block("WORD", text, rotated, text_type))
    return blocks

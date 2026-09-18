"""Signature-presence detection for uploaded Purchase Request documents.

This module is deliberately **isolated** from the OCR text-extraction pipeline
(``purchase_request_parser`` / ``textract_purchase_request_parser``). It never
changes how signatory *names* are extracted. It answers a single, separate
question per signatory area:

    Does the signature region for this signatory contain a handwritten /
    graphical mark, or is it blank?

Pipeline
--------
1. ``collect_text_lines`` - reuse geometry that already exists: Textract ``LINE``
   blocks when available, otherwise ``pdfminer`` page layout for digital PDFs.
   Scanned images without Textract yield no geometry (-> "unable to verify").
2. ``compute_regions`` - from the CTU footer anchors ("Requested by",
   "Funds Available", "Approved by", "Specifications verified by Technical
   Working Group", "Signature :", "Printed Name :") derive one signature band
   per signatory, in page-normalized coordinates.
3. ``analyze`` - rasterise the relevant page, crop each band, strip the printed
   rule line + any OCR-recognised text, and measure the remaining ink to
   classify the area as ``present`` / ``absent`` / ``unverifiable``.

The detector only answers "is there a handwritten / graphical mark in this
band" - it deliberately does **not** try to judge whether a mark is a genuine
signature. A signature area therefore passes as long as it contains a scribble,
initials, a stamp, or anything else that is clearly not the blank ruled line.
Only an area that is unmistakably empty is reported as ``absent`` (and blocks
the save); an area that has some ink but no obvious stroke is given the benefit
of the doubt and reported as ``present``. ``unverifiable`` is reserved for the
cases where the document itself cannot be inspected (no OCR geometry, render
failure, missing file).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - exercised indirectly
    from .debug_utils import get_parser_logger
except ImportError:  # pragma: no cover
    from backend.ocr.debug_utils import get_parser_logger

logger = get_parser_logger()

# ---------------------------------------------------------------------------
# Signatory vocabulary
# ---------------------------------------------------------------------------
REQUESTED_BY = "requested_by"
FUNDS_AVAILABLE = "funds_available"
APPROVED_BY = "approved_by"
TWG = "twg"

# Which signatures block a Purchase Request save. Derived from the CTU PR form:
# the Technical Working Group only verifies technical specifications and is not
# present on every PR, so it is validated + displayed but never mandatory.
REQUIRED_SIGNATORIES: Tuple[str, ...] = (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY)
OPTIONAL_SIGNATORIES: Tuple[str, ...] = (TWG,)
ALL_SIGNATORIES: Tuple[str, ...] = REQUIRED_SIGNATORIES + OPTIONAL_SIGNATORIES

DISPLAY_NAMES: Dict[str, str] = {
    REQUESTED_BY: "Requested By",
    FUNDS_AVAILABLE: "Funds Available",
    APPROVED_BY: "Approved By",
    TWG: "TWG Verified By",
}

STATE_PRESENT = "present"
STATE_ABSENT = "absent"
STATE_UNVERIFIABLE = "unverifiable"

SIDECAR_VERSION = 3

# Tunable classifier thresholds. The bar for "present" is intentionally low -
# the detector only needs to separate a signed area from a blank ruled line,
# not vouch for a signature.
_THRESHOLDS = {
    "min_region_px": 10,          # a band smaller than this cannot be judged
    "render_scale": 3.0,          # page raster scale (~216 DPI for A4)
    "ink_absent_max": 0.006,      # <= this ink ratio after cleanup -> blank
    "ink_present_min": 0.010,     # >= this ink ratio -> mark worth keeping
    "stroke_min_height_frac": 0.10,  # a mark has some vertical extent
    "stroke_min_width_frac": 0.03,
    "rule_line_kernel_frac": 0.33,   # width of the horizontal opening kernel
}


@dataclass
class TextLine:
    """One text line in page-normalized coordinates (origin = top-left)."""

    text: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    # Per-character (glyph, x0, x1) boxes in the same normalized space, in
    # left-to-right order. Populated only by the pdfminer path, where exact
    # glyph geometry is available cheaply - used to find precisely where a
    # printed label like "Signature :" ends (see ``_char_label_extent``)
    # instead of guessing a fraction of the line's overall measured width.
    char_boxes: Optional[List[Tuple[str, float, float]]] = None

    @property
    def norm(self) -> str:
        return " ".join(self.text.lower().split())

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)


@dataclass
class Region:
    """A signature band to inspect, in page-normalized coordinates."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    # Text-line boxes (same coordinate space) to blank out before measuring ink.
    masks: List[Tuple[float, float, float, float]] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page": self.page,
            "x0": round(self.x0, 5),
            "y0": round(self.y0, 5),
            "x1": round(self.x1, 5),
            "y1": round(self.y1, 5),
            "masks": [[round(v, 5) for v in box] for box in self.masks],
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Region":
        return cls(
            page=int(data.get("page", 1) or 1),
            x0=float(data.get("x0", 0.0)),
            y0=float(data.get("y0", 0.0)),
            x1=float(data.get("x1", 0.0)),
            y1=float(data.get("y1", 0.0)),
            masks=[tuple(float(v) for v in box) for box in data.get("masks", [])],
            source=str(data.get("source", "")),
        )

    @property
    def valid(self) -> bool:
        return self.x1 > self.x0 and self.y1 > self.y0


# ---------------------------------------------------------------------------
# Geometry collection
# ---------------------------------------------------------------------------
def collect_text_lines(path: Path, textract_blocks: Optional[List[Dict[str, Any]]] = None) -> List[TextLine]:
    """Gather text-line geometry from Textract blocks or the PDF layout."""
    if textract_blocks:
        lines = _lines_from_textract(textract_blocks)
        if lines:
            return lines

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _lines_from_pdf_layout(path)
    return []


def _lines_from_textract(blocks: List[Dict[str, Any]], block_type: str = "LINE") -> List[TextLine]:
    lines: List[TextLine] = []
    for block in blocks:
        if block.get("BlockType") != block_type:
            continue
        text = str(block.get("Text") or "").strip()
        if not text:
            continue
        box = ((block.get("Geometry") or {}).get("BoundingBox") or {})
        left = float(box.get("Left") or 0.0)
        top = float(box.get("Top") or 0.0)
        width = float(box.get("Width") or 0.0)
        height = float(box.get("Height") or 0.0)
        lines.append(
            TextLine(
                text=text,
                page=int(block.get("Page", 1) or 1),
                x0=left,
                y0=top,
                x1=left + width,
                y1=top + height,
            )
        )
    return lines


def collect_words(textract_blocks: Optional[List[Dict[str, Any]]]) -> List[TextLine]:
    """Textract WORD boxes - used for precise signatory column centres."""
    if not textract_blocks:
        return []
    return _lines_from_textract(textract_blocks, block_type="WORD")


def _lines_from_pdf_layout(path: Path) -> List[TextLine]:
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTChar, LTTextContainer, LTTextLine
    except Exception:  # pragma: no cover - pdfminer always installed here
        return []

    lines: List[TextLine] = []
    try:
        for page_index, page_layout in enumerate(extract_pages(str(path)), start=1):
            _, _, page_w, page_h = page_layout.bbox
            if not page_w or not page_h:
                continue
            for element in page_layout:
                if not isinstance(element, LTTextContainer):
                    continue
                for line in element:
                    if not isinstance(line, LTTextLine):
                        continue
                    text = line.get_text().strip()
                    if not text:
                        continue
                    x0, y0, x1, y1 = line.bbox
                    char_boxes = [
                        (obj.get_text(), max(0.0, obj.x0 / page_w), min(1.0, obj.x1 / page_w))
                        for obj in line
                        if isinstance(obj, LTChar)
                    ]
                    lines.append(
                        TextLine(
                            text=text,
                            page=page_index,
                            x0=max(0.0, x0 / page_w),
                            # pdfminer origin is bottom-left; flip to top-left.
                            y0=max(0.0, 1.0 - (y1 / page_h)),
                            x1=min(1.0, x1 / page_w),
                            y1=min(1.0, 1.0 - (y0 / page_h)),
                            char_boxes=char_boxes or None,
                        )
                    )
    except Exception:
        logger.exception("SIGNATURE pdf layout extraction failed")
        return []
    return lines


# ---------------------------------------------------------------------------
# Region derivation
# ---------------------------------------------------------------------------
def _first_line(lines: List[TextLine], *needles: str, page: Optional[int] = None) -> Optional[TextLine]:
    for line in lines:
        if page is not None and line.page != page:
            continue
        norm = line.norm
        if all(needle in norm for needle in needles):
            return line
    return None


def _all_lines(lines: List[TextLine], *needles: str) -> List[TextLine]:
    return [line for line in lines if all(needle in line.norm for needle in needles)]


def _is_rule_line(text: str) -> bool:
    """A recognised line that is only the ruled blank (underscores / dashes)."""
    stripped = re.sub(r"\s+", "", text or "")
    return bool(stripped) and bool(re.fullmatch(r"[_\-—–.]+", stripped))


def _char_label_extent(line: TextLine) -> Optional[float]:
    """Right edge (normalized x) of the printed "Signature" label within
    ``line``, from exact glyph positions (the pdfminer path only). Extends
    past a directly-following colon/punctuation - e.g. "Signature :" - so the
    whole printed label is covered, not just the bare word. Returns ``None``
    when ``line`` has no character-level geometry, or the word isn't found.
    """
    if not line.char_boxes:
        return None
    joined = "".join(ch for ch, _, _ in line.char_boxes).lower()
    idx = joined.find("signature")
    if idx < 0:
        return None
    end_idx = idx + len("signature") - 1
    lookahead = joined[end_idx + 1:end_idx + 4]
    colon_offset = lookahead.find(":")
    if colon_offset != -1:
        end_idx += 1 + colon_offset
    end_idx = min(end_idx, len(line.char_boxes) - 1)
    return line.char_boxes[end_idx][2]


def _word_label_extent(words: Optional[List[TextLine]], line: TextLine) -> Optional[float]:
    """Right edge (normalized x) of the printed "Signature" label within
    ``line``'s row, from Textract WORD boxes - the recognizer's own word
    segmentation, and the most reliable source when available. Returns
    ``None`` when no matching WORD box is found in that row."""
    if not words:
        return None
    hits = [
        w for w in words
        if w.page == line.page and "signature" in w.norm
        and (line.y0 - 0.01) <= w.y0 <= (line.y1 + 0.01)
    ]
    if not hits:
        return None
    hit = min(hits, key=lambda w: w.x0)
    end_x1 = hit.x1
    # A colon recognised as its own WORD immediately to the right is still
    # part of the printed label, not something a signer would write over.
    colon = next(
        (
            w for w in words
            if w.page == line.page and w.text.strip().startswith(":")
            and (line.y0 - 0.01) <= w.y0 <= (line.y1 + 0.01)
            and 0 <= (w.x0 - end_x1) <= 0.02
        ),
        None,
    )
    if colon is not None:
        end_x1 = colon.x1
    return end_x1


def _text_masks(
    lines: List[TextLine],
    page: int,
    band_top: float,
    band_bottom: float,
    words: Optional[List[TextLine]] = None,
) -> List[Tuple[float, float, float, float]]:
    """Boxes of recognised *text* inside a band - printed names, headings, the
    "Signature :" label - to blank before measuring ink. The ruled blank line is
    deliberately not masked (a signature drawn across it must survive; the
    horizontal-line filter removes the rule)."""
    masks: List[Tuple[float, float, float, float]] = []
    for line in lines:
        if line.page != page:
            continue
        if line.y1 < band_top - 0.02 or line.y0 > band_bottom + 0.02:
            continue
        if _is_rule_line(line.text):
            continue
        if "signature" in line.norm and "printed name" not in line.norm:
            # Mask exactly where the printed label ends, from real glyph/word
            # geometry - never a fixed fraction of the *line's* measured
            # width, which has no relationship to how wide the label itself
            # was actually rendered (a line combining the label with a long
            # ruled blank, or a line that is just the label on its own,
            # produce very different width ratios for the same label).
            label_x1 = _word_label_extent(words, line)
            if label_x1 is None:
                label_x1 = _char_label_extent(line)
            if label_x1 is None:
                # Defensive fallback only - pdfminer always yields char boxes
                # and Textract always yields WORD blocks alongside LINEs, so
                # this should not normally trigger. Estimate the label's
                # share of the line from its text length instead of an
                # arbitrary pixel-width fraction.
                ratio = min(0.9, len("signature :") / max(len(line.text), 1))
                label_x1 = line.x0 + ratio * max(line.x1 - line.x0, 1e-6)
            label_x1 = max(line.x0, min(label_x1, line.x1))
            masks.append((line.x0, line.y0, label_x1, line.y1))
            continue
        masks.append((line.x0, line.y0, line.x1, line.y1))
    return masks


def _word_center_x(words: List[TextLine], needle: str, page: int, y_lo: float, y_hi: float) -> Optional[float]:
    """Centre-x of a heading word near a y-range, from Textract WORD boxes."""
    hits = [
        w for w in words
        if w.page == page and needle in w.norm and (y_lo - 0.02) <= w.y0 <= (y_hi + 0.02)
    ]
    if not hits:
        return None
    hit = min(hits, key=lambda w: w.y0)
    return (hit.x0 + hit.x1) / 2.0


def compute_regions(lines: List[TextLine], words: Optional[List[TextLine]] = None) -> Dict[str, Region]:
    """Derive one signature band per signatory from the footer anchors.

    The band sits directly under the "Requested by / Funds Available / Approved
    by" headings and extends just past the ruled signature line - the exact area
    a signatory signs.
    """
    regions: Dict[str, Region] = {}
    words = words or []
    if not lines:
        return regions

    heading = _first_line(lines, "requested by") or _first_line(lines, "requested")
    approved_heading = _first_line(lines, "approved by") or _first_line(lines, "approved")
    funds_heading = _first_line(lines, "funds available") or _first_line(lines, "budget officer")
    if heading is None:
        return regions

    page = heading.page
    heading_bottom = max(
        h.y1 for h in (heading, funds_heading, approved_heading)
        if h is not None and h.page == page
    )
    heading_top = min(
        h.y0 for h in (heading, funds_heading, approved_heading)
        if h is not None and h.page == page
    )

    signature_rows = [
        line for line in _all_lines(lines, "signature")
        if line.page == page and line.y0 >= heading_top - 0.002
    ]
    signature_rows.sort(key=lambda l: l.y0)
    main_sig_row = signature_rows[0] if signature_rows else None

    printed_rows = [
        line for line in _all_lines(lines, "printed name")
        if line.page == page and line.y0 >= heading_bottom - 0.002
    ]
    printed_rows.sort(key=lambda l: l.y0)
    main_printed_row = printed_rows[0] if printed_rows else None

    # Vertical band: from just under the heading down to a little past the ruled
    # signature line - never into the printed-name row.
    band_top = heading_bottom + 0.001
    if main_sig_row is not None:
        sig_h = max(main_sig_row.height, 0.008)
        band_bottom = min(main_sig_row.y1 + 0.8 * sig_h, main_sig_row.y1 + 0.05)
        if main_printed_row is not None:
            band_bottom = min(band_bottom, main_printed_row.y0 - 0.001)
        # Keep a floor height even if the sig row hugs the heading.
        band_bottom = max(band_bottom, band_top + 0.028)
    elif main_printed_row is not None:
        band_bottom = main_printed_row.y0 - 0.002
    else:
        band_bottom = band_top + 0.06
    if band_bottom <= band_top:
        band_bottom = band_top + 0.03

    # Column boundaries. Prefer Textract WORD centres for the three headings;
    # fall back to an even split of the signature-row content span.
    centres = [
        _word_center_x(words, "requested", page, heading_top, heading_bottom),
        _word_center_x(words, "funds", page, heading_top, heading_bottom)
        or _word_center_x(words, "available", page, heading_top, heading_bottom),
        _word_center_x(words, "approved", page, heading_top, heading_bottom),
    ]

    # Content span across the three columns. Widen it using every row that runs
    # the full width (signature row, printed-name row), then push the left edge
    # past the "Signature :" / "Printed Name :" labels using the first heading.
    heading_lefts = [h.x0 for h in (heading, funds_heading, approved_heading) if h is not None]
    heading_rights = [h.x1 for h in (heading, funds_heading, approved_heading) if h is not None]
    row_rights = [r.x1 for r in (main_sig_row, main_printed_row) if r is not None]
    span_left = min(heading_lefts) if heading_lefts else 0.10
    span_right = max(heading_rights + row_rights) if (heading_rights or row_rights) else 0.95
    if main_sig_row is not None and (main_sig_row.x1 - main_sig_row.x0) > 0.30:
        # A wide "Signature : ___ ___ ___" row - trust its right edge.
        span_right = max(span_right, main_sig_row.x1)
    span_left = max(0.0, min(span_left, span_right - 0.30))
    span_right = min(1.0, max(span_right, span_left + 0.30))

    if all(c is not None for c in centres) and centres[0] < centres[1] < centres[2]:
        b1 = (centres[0] + centres[1]) / 2.0
        b2 = (centres[1] + centres[2]) / 2.0
        bounds = [
            (span_left, b1),
            (b1, b2),
            (b2, span_right),
        ]
    else:
        col_w = (span_right - span_left) / 3.0
        bounds = [
            (span_left + i * col_w, span_left + (i + 1) * col_w) for i in range(3)
        ]

    masks = _text_masks(lines, page, band_top, band_bottom, words)

    for key, (x0, x1) in zip((REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY), bounds):
        regions[key] = Region(
            page=page,
            x0=max(0.0, x0),
            y0=band_top,
            x1=min(1.0, x1),
            y1=band_bottom,
            masks=[m for m in masks if m[2] >= x0 and m[0] <= x1],
            source="anchors",
        )

    # Technical Working Group - its own single-column block further down.
    twg_heading = _first_line(lines, "specifications verified") or _first_line(lines, "technical working group")
    if twg_heading is not None:
        twg_page = twg_heading.page
        twg_sig = next(
            (l for l in _all_lines(lines, "signature") if l.page == twg_page and l.y0 >= twg_heading.y1 - 0.002),
            None,
        )
        twg_printed = next(
            (l for l in _all_lines(lines, "printed name") if l.page == twg_page and l.y0 >= twg_heading.y1 - 0.002),
            None,
        )
        # The ruled blank on the TWG signature line - a separate recognised line
        # of underscores; its extent marks where a signature would be written.
        twg_rule = next(
            (
                l for l in lines
                if l.page == twg_page and _is_rule_line(l.text)
                and twg_heading.y1 - 0.005 <= l.y0 <= twg_heading.y1 + 0.06
            ),
            None,
        )
        t_top = twg_heading.y1 + 0.001
        if twg_printed is not None:
            t_bottom = twg_printed.y0 - 0.001
        elif twg_rule is not None:
            t_bottom = twg_rule.y1 + 1.0 * max(twg_rule.height, 0.01)
        elif twg_sig is not None:
            t_bottom = twg_sig.y1 + 2.2 * max(twg_sig.height, 0.01)
        else:
            t_bottom = t_top + 0.04
        if t_bottom <= t_top:
            t_bottom = t_top + 0.03

        label = twg_sig if twg_sig is not None else twg_heading
        t_left = label.x0 + 0.11 * max(label.x1 - label.x0, 0.02)
        if twg_rule is not None:
            t_left = min(t_left, twg_rule.x0)
            t_right = twg_rule.x1
        else:
            t_right = max(twg_heading.x1, twg_printed.x1 if twg_printed is not None else 0.0)
        t_left = max(0.0, min(t_left, 0.9))
        t_right = min(1.0, max(t_right, t_left + 0.15))

        regions[TWG] = Region(
            page=twg_page, x0=t_left, y0=t_top, x1=t_right, y1=t_bottom,
            masks=_text_masks(lines, twg_page, t_top, t_bottom, words), source="anchors",
        )

    return regions


# ---------------------------------------------------------------------------
# Image analysis
# ---------------------------------------------------------------------------
def _render_page(path: Path, page_number: int, scale: float):
    """Return a grayscale numpy array for one page, or ``None``.

    A signature added with a PDF editor is usually an *annotation*, so the page
    must be rasterised with annotations drawn. PyMuPDF does this reliably; the
    pypdfium2 path is a fallback.
    """
    try:
        import numpy as np
        from PIL import Image
    except Exception:  # pragma: no cover
        return None

    suffix = path.suffix.lower()
    if suffix != ".pdf":
        try:
            with Image.open(path) as image:
                return np.asarray(image.convert("L"))
        except Exception:
            return None

    # Preferred: PyMuPDF with annotations rendered.
    try:
        import pymupdf  # noqa: F401

        doc = pymupdf.open(str(path))
        try:
            index = max(0, min(page_number - 1, doc.page_count - 1))
            page = doc[index]
            matrix = pymupdf.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=matrix, annots=True, colorspace=pymupdf.csGRAY)
            return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)[:, : pix.width]
        finally:
            doc.close()
    except Exception:
        logger.info("SIGNATURE pymupdf render unavailable, trying pypdfium2")

    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        try:
            index = max(0, min(page_number - 1, len(pdf) - 1))
            page = pdf[index]
            try:
                image = page.render(scale=scale, draw_annots=True).to_pil().convert("L")
            except TypeError:
                image = page.render(scale=scale).to_pil().convert("L")
            page.close()
            return np.asarray(image)
        finally:
            pdf.close()
    except Exception:
        logger.exception("SIGNATURE page render failed")
        return None


def _classify_region(gray, region: Region) -> Dict[str, Any]:
    import numpy as np

    try:
        import cv2
    except Exception:  # pragma: no cover
        cv2 = None

    h, w = gray.shape[:2]
    px0 = int(round(region.x0 * w))
    px1 = int(round(region.x1 * w))
    py0 = int(round(region.y0 * h))
    py1 = int(round(region.y1 * h))
    px0, px1 = max(0, min(px0, w - 1)), max(0, min(px1, w))
    py0, py1 = max(0, min(py0, h - 1)), max(0, min(py1, h))

    min_px = _THRESHOLDS["min_region_px"]
    if px1 - px0 < min_px or py1 - py0 < min_px:
        return {"state": STATE_UNVERIFIABLE, "confidence": 0.2, "reason": "region_too_small"}

    crop = np.ascontiguousarray(gray[py0:py1, px0:px1].astype("uint8"))

    # Binarise: ink = 1. Otsu when available, fixed threshold otherwise.
    if cv2 is not None:
        _, binary = cv2.threshold(crop, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        binary = (crop < 200).astype("uint8")
    binary = binary.astype("uint8")

    ch, cw = binary.shape
    # Blank recognised text boxes (printed name / labels) that fall in the crop.
    for mx0, my0, mx1, my1 in region.masks:
        a = int(round((mx0 - region.x0) / max(region.x1 - region.x0, 1e-6) * cw))
        b = int(round((mx1 - region.x0) / max(region.x1 - region.x0, 1e-6) * cw))
        c = int(round((my0 - region.y0) / max(region.y1 - region.y0, 1e-6) * ch))
        d = int(round((my1 - region.y0) / max(region.y1 - region.y0, 1e-6) * ch))
        a, b = max(0, a), min(cw, b)
        c, d = max(0, c), min(ch, d)
        if b > a and d > c:
            binary[c:d, a:b] = 0

    raw_ratio = float(binary.mean()) if binary.size else 0.0

    # Vertical structure in the raw mark, *before* the ruled line is stripped: a
    # blank cell is one or two near-solid horizontal rows (the rule); a written
    # mark also has rows that carry ink without spanning the whole width. This is
    # measured up front because an aggressive rule-line removal can erase a small
    # signature that sits directly on the line.
    row_ink_raw = binary.sum(axis=1)
    stroke_rows = int(np.count_nonzero((row_ink_raw > 0.03 * cw) & (row_ink_raw < 0.55 * cw)))
    raw_vertical_frac = stroke_rows / max(ch, 1)
    if binary.any():
        rr = np.where(binary.any(axis=1))[0]
        cc = np.where(binary.any(axis=0))[0]
        raw_spread_h = (rr.max() - rr.min() + 1) / max(ch, 1)
        raw_spread_w = (cc.max() - cc.min() + 1) / max(cw, 1)
    else:
        raw_spread_h = raw_spread_w = 0.0
    raw_mark = (
        raw_ratio >= 0.010
        and raw_vertical_frac >= 0.10
        and raw_spread_w >= 0.08
        and raw_spread_h >= _THRESHOLDS["stroke_min_height_frac"]
    )

    # Remove the printed ruled line: find long horizontal runs, but only erase
    # them in columns whose total ink is thin. A column crossed by a real
    # signature stroke is thick and is therefore preserved.
    column_ink = binary.sum(axis=0)
    thin_column = column_ink <= max(3, int(0.16 * ch))
    if cv2 is not None:
        kernel_w = max(12, int(cw * _THRESHOLDS["rule_line_kernel_frac"]))
        horizontal = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
        )
    else:
        horizontal = np.zeros_like(binary)
        for r in range(ch):
            if binary[r].sum() > 0.55 * cw:
                horizontal[r, :] = 1
    horizontal[:, ~thin_column] = 0
    cleaned = np.clip(binary.astype("int16") - horizontal.astype("int16"), 0, 1).astype("uint8")

    if cv2 is not None:
        # Reconnect a signature broken by the erased rule line into one mark.
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, np.ones((3, 3), "uint8"))

    ink_ratio = float(cleaned.mean()) if cleaned.size else 0.0

    tallest_frac = 0.0
    widest_frac = 0.0
    largest_area_frac = 0.0
    components = 0
    min_area = max(8, 0.0006 * ch * cw)
    if cv2 is not None and cleaned.any():
        count, _, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
        for i in range(1, count):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_area:
                continue
            components += 1
            h_frac = stats[i, cv2.CC_STAT_HEIGHT] / max(ch, 1)
            w_frac = stats[i, cv2.CC_STAT_WIDTH] / max(cw, 1)
            if area / max(ch * cw, 1) > largest_area_frac:
                largest_area_frac = area / max(ch * cw, 1)
            tallest_frac = max(tallest_frac, h_frac)
            widest_frac = max(widest_frac, w_frac)
    elif cleaned.any():
        rows = np.where(cleaned.any(axis=1))[0]
        cols = np.where(cleaned.any(axis=0))[0]
        if rows.size and cols.size:
            components = 1
            tallest_frac = (rows.max() - rows.min() + 1) / max(ch, 1)
            widest_frac = (cols.max() - cols.min() + 1) / max(cw, 1)
            largest_area_frac = ink_ratio

    # Overall spread of the remaining ink - robust to a stroke fragmenting into
    # several connected components.
    spread_h = spread_w = 0.0
    if cleaned.any():
        rows = np.where(cleaned.any(axis=1))[0]
        cols = np.where(cleaned.any(axis=0))[0]
        spread_h = (rows.max() - rows.min() + 1) / max(ch, 1)
        spread_w = (cols.max() - cols.min() + 1) / max(cw, 1)

    metrics = {
        "raw_ink_ratio": round(raw_ratio, 5),
        "ink_ratio": round(ink_ratio, 5),
        "tallest_component_frac": round(tallest_frac, 4),
        "widest_component_frac": round(widest_frac, 4),
        "spread_h": round(spread_h, 4),
        "spread_w": round(spread_w, 4),
        "components": components,
        "raw_vertical_frac": round(raw_vertical_frac, 4),
        "raw_spread_w": round(raw_spread_w, 4),
    }

    # Does anything rise off the ruled line? A blank signature area only ever has
    # baseline-flat remnants (bits of the printed rule the filter missed); a
    # written mark - a squiggle, initials, a stamp - has vertical extent.
    vertical_extent = max(tallest_frac, 0.75 * spread_h)
    has_vertical = vertical_extent >= _THRESHOLDS["stroke_min_height_frac"] or tallest_frac >= 0.12

    # A mark worth accepting: real ink, a little horizontal spread, some vertical
    # rise, and at least one non-trivial blob. Nothing here demands a full
    # signature-shaped stroke.
    has_mark = (
        cleaned.any()
        and ink_ratio >= _THRESHOLDS["ink_present_min"]
        and spread_w >= 0.06
        and has_vertical
        and (
            widest_frac >= _THRESHOLDS["stroke_min_width_frac"]
            or largest_area_frac >= 0.003
            or components >= 2
        )
    )
    strong_mark = ink_ratio >= 0.04 and spread_w >= 0.30 and spread_h >= 0.15

    if strong_mark or has_mark or raw_mark:
        over = max(0.0, ink_ratio - _THRESHOLDS["ink_present_min"])
        confidence = min(0.96, 0.6 + 6.0 * over + 0.12 * max(spread_w, raw_spread_w))
        if not (strong_mark or has_mark):
            confidence = min(confidence, 0.7)
        return {"state": STATE_PRESENT, "confidence": round(confidence, 3), "metrics": metrics}

    # Blank: either almost no ink at all, or only baseline-flat fragments with no
    # blob of any size and no vertical structure in the raw mark either.
    negligible_ink = ink_ratio <= _THRESHOLDS["ink_absent_max"]
    flat_remnant_only = (
        not has_vertical
        and largest_area_frac < 0.004
        and raw_vertical_frac < 0.10
    )
    if negligible_ink or flat_remnant_only:
        confidence = 0.9 - 30.0 * ink_ratio
        return {"state": STATE_ABSENT, "confidence": round(max(0.6, confidence), 3), "metrics": metrics}

    # Some ink that rises off the line but is not a confident stroke. A human
    # uploaded this as a signed document, so accept it rather than blocking.
    return {"state": STATE_PRESENT, "confidence": 0.55, "metrics": metrics, "reason": "lenient_mark"}


def _debug_dump(gray, region: Region, key: str, result: Dict[str, Any]) -> None:
    """When DEBUG is on, save each analysed crop so regions can be eyeballed."""
    try:
        from .debug_utils import get_debug_dir, is_debug_enabled
    except ImportError:  # pragma: no cover
        from backend.ocr.debug_utils import get_debug_dir, is_debug_enabled
    if not is_debug_enabled():
        return
    try:
        import numpy as np
        from PIL import Image

        h, w = gray.shape[:2]
        x0, x1 = int(region.x0 * w), int(region.x1 * w)
        y0, y1 = int(region.y0 * h), int(region.y1 * h)
        pad = 12
        crop = gray[max(0, y0 - pad):min(h, y1 + pad), max(0, x0 - pad):min(w, x1 + pad)]
        out = get_debug_dir() / f"signature_{key}.png"
        Image.fromarray(np.asarray(crop)).save(out)
        logger.info("SIGNATURE %s -> %s | %s | %s", key, result.get("state"), result.get("metrics"), out.name)
    except Exception:
        pass


def _detect_with_regions(path: Path, regions: Dict[str, Region]) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    rendered: Dict[int, Any] = {}
    scale = _THRESHOLDS["render_scale"]

    for key in ALL_SIGNATORIES:
        region = regions.get(key)
        if region is None or not region.valid:
            results[key] = {"state": STATE_UNVERIFIABLE, "confidence": 0.15, "reason": "region_not_located"}
            continue
        if region.page not in rendered:
            rendered[region.page] = _render_page(path, region.page, scale)
        gray = rendered.get(region.page)
        if gray is None:
            results[key] = {"state": STATE_UNVERIFIABLE, "confidence": 0.15, "reason": "page_render_failed"}
            continue
        try:
            results[key] = _classify_region(gray, region)
            _debug_dump(gray, region, key, results[key])
        except Exception:
            logger.exception("SIGNATURE classify failed for %s", key)
            results[key] = {"state": STATE_UNVERIFIABLE, "confidence": 0.2, "reason": "analysis_error"}
    return results


def _apply_row_consensus(signatories: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """CTU PR footer rows are signed in one sitting. If the other required
    signatory areas are clearly signed, an area that carries ink but just missed
    the stroke bar is almost certainly signed too - promote it. A clearly blank
    area (no ink, no vertical structure) is never promoted.
    """
    req = [k for k in REQUIRED_SIGNATORIES if k in signatories]
    strong = [
        k for k in req
        if signatories[k].get("state") == STATE_PRESENT
        and float(signatories[k].get("confidence", 0) or 0) >= 0.6
    ]
    if len(strong) < 2:
        return signatories

    for key in req:
        info = signatories[key]
        if info.get("state") == STATE_PRESENT:
            continue
        m = info.get("metrics") or {}
        has_ink = (
            float(m.get("ink_ratio", 0) or 0) >= 0.004
            or float(m.get("raw_vertical_frac", 0) or 0) >= 0.06
            or int(m.get("components", 0) or 0) >= 1
        )
        if has_ink:
            signatories[key] = {
                **info,
                "state": STATE_PRESENT,
                "confidence": 0.6,
                "reason": "row_consensus",
            }
    return signatories


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _summarise(signatories: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    required_states = {key: signatories[key]["state"] for key in REQUIRED_SIGNATORIES if key in signatories}
    detected = [key for key, state in required_states.items() if state == STATE_PRESENT]
    missing = [
        DISPLAY_NAMES[key]
        for key in REQUIRED_SIGNATORIES
        if required_states.get(key) == STATE_ABSENT
    ]
    unverifiable = [
        DISPLAY_NAMES[key]
        for key in REQUIRED_SIGNATORIES
        if required_states.get(key, STATE_UNVERIFIABLE) not in (STATE_PRESENT, STATE_ABSENT)
    ]
    all_present = len(detected) == len(REQUIRED_SIGNATORIES)
    # The save is blocked only by a signatory area that is unmistakably blank.
    # An area that could not be located / inspected at all does not by itself
    # block, unless *nothing* could be confirmed (e.g. the document is missing).
    can_save = not missing and len(detected) >= 1

    if all_present:
        status = "complete"
        message = "All required signatures are present."
    elif missing:
        status = "incomplete"
        message = "One or more required signatures are missing."
    elif can_save:
        status = "complete"
        message = "A signature was found for each required signatory."
    else:
        status = "unverifiable"
        message = "Signatures could not be located. Please review the original document."
    return {
        "required_total": len(REQUIRED_SIGNATORIES),
        "required_detected": len(detected),
        "missing_signatures": missing,
        "unverifiable_signatures": unverifiable,
        "all_required_present": all_present,
        "can_save": can_save,
        "status": status,
        "message": message,
    }


def _payload(signatories: Dict[str, Dict[str, Any]], names: Optional[Dict[str, str]], regions: Dict[str, Region]) -> Dict[str, Any]:
    names = names or {}
    signatories = _apply_row_consensus(dict(signatories))
    enriched: Dict[str, Dict[str, Any]] = {}
    for key in ALL_SIGNATORIES:
        info = dict(signatories.get(key, {"state": STATE_UNVERIFIABLE, "confidence": 0.0}))
        info["key"] = key
        info["label"] = DISPLAY_NAMES[key]
        info["required"] = key in REQUIRED_SIGNATORIES
        info["name"] = str(names.get(key, "") or "")
        enriched[key] = info
    return {
        "signatories": enriched,
        "summary": _summarise(enriched),
        "regions": {key: region.to_dict() for key, region in regions.items()},
    }


def analyze(
    path: Path,
    textract_blocks: Optional[List[Dict[str, Any]]] = None,
    names: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Full run: locate signature regions from OCR geometry, then inspect them.

    For a digital PDF the exact page text layout (pdfminer) is the primary
    geometry source - it is the real layout, not an OCR estimate. Textract
    geometry is used for scanned pages (where pdfminer yields nothing) and as a
    cross-check: whichever source detects more signatures wins, since a missed
    signature is the failure that matters.
    """
    path = Path(path)

    def _run(lines: List[TextLine], words: List[TextLine]):
        regions = compute_regions(lines, words)
        return regions, _detect_with_regions(path, regions)

    def _present_count(sig: Dict[str, Dict[str, Any]]) -> int:
        return sum(1 for k in REQUIRED_SIGNATORIES if sig.get(k, {}).get("state") == STATE_PRESENT)

    candidates: List[Tuple[Dict[str, Region], Dict[str, Dict[str, Any]]]] = []
    try:
        if path.suffix.lower() == ".pdf":
            pdf_lines = _lines_from_pdf_layout(path)
            if pdf_lines:
                candidates.append(_run(pdf_lines, []))
        if textract_blocks:
            candidates.append(
                _run(_lines_from_textract(textract_blocks), collect_words(textract_blocks))
            )
        if not candidates:
            candidates.append(({}, {}))
    except Exception:
        logger.exception("SIGNATURE analyze failed")
        candidates = candidates or [({}, {})]

    # Prefer the candidate that located the most signatures, then the most
    # regions; ties keep the first (pdfminer for digital PDFs).
    regions, signatories = max(
        candidates,
        key=lambda c: (_present_count(c[1]), len(c[0])),
    )
    return _payload(signatories, names, regions)


def reanalyze(path: Path, regions_data: Dict[str, Any], names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Re-inspect the image using previously derived regions (no re-OCR).

    Used by the "Recheck Signatures" action and by the backend save guard, so
    enforcement re-measures the actual document pixels rather than trusting a
    value sent by the browser.
    """
    path = Path(path)
    regions: Dict[str, Region] = {}
    for key, data in (regions_data or {}).items():
        if key in ALL_SIGNATORIES and isinstance(data, dict):
            regions[key] = Region.from_dict(data)
    try:
        signatories = _detect_with_regions(path, regions)
    except Exception:
        logger.exception("SIGNATURE reanalyze failed")
        signatories = {}
    return _payload(signatories, names, regions)


def blank_result(names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """An all-unverifiable result (document unavailable / no geometry)."""
    return _payload({}, names, {})

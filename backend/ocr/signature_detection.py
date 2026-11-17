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
   A scan without Textract output has no geometry; every box is then
   "uncertain" (reason ``no_ocr_geometry``) for the reviewer to confirm.
2. ``compute_regions`` - from the CTU footer anchors ("Requested by",
   "Funds Available", "Approved by", "Specifications verified by Technical
   Working Group", "Signature :", "Printed Name :") derive one signature band
   per signatory, in page-normalized coordinates.
3. ``analyze`` - rasterise the relevant page, crop each band, strip the printed
   rule line + any OCR-recognised text, and measure the remaining ink to
   classify the area as ``present`` / ``absent`` / ``unverifiable``.

The detector only answers "is there a handwritten / graphical mark in this
band" - it deliberately does **not** try to judge whether a mark is a genuine
signature. There are no silent passes:

* ``present``   - clear handwritten ink in the box.
* ``absent``    - the box is clearly empty (blocks the save).
* ``uncertain`` - there is something in the box but not enough to be sure, or
  the box could not be located (e.g. no OCR geometry). The reviewer must look
  at the document and confirm it before the save is allowed.
* ``unverifiable`` - the document itself could not be read (missing file,
  render failure). Blocks the save; there is nothing for a reviewer to confirm.
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
STATE_UNCERTAIN = "uncertain"

# v4: masks are built from expected printed words only, regions carry
# handwriting boxes, and states include "uncertain". Older sidecars hold masks
# that erased Textract-recognised signatures, so they are re-derived.
SIDECAR_VERSION = 4

# Printed words the CTU form itself places in or beside a signature band. Only
# these (plus the extracted printed names) are ever masked out of a band when
# OCR word boxes are available; any other word - whatever OCR thinks it is -
# may be the signature and is left in.
PRINTED_LABEL_WORDS = frozenset({
    "requested", "by", "funds", "available", "approved", "signature",
    "printed", "name", "designation", "specifications", "verified",
    "technical", "working", "group",
})

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
    # Page-width fraction a signature may start left of its own label and
    # still belong to that column.
    "column_core_margin": 0.02,
    # Gray level below which a pixel counts as ink (0-255).
    "ink_gray_ceiling": 215,
    # A pixel is ink only when it is this much darker than the band's paper
    # (scans have gray or tinted paper, so an absolute level is not enough).
    "ink_below_paper": 40,
    # Connected blobs of at most this many pixels are scan speckle, not ink.
    "speckle_max_px": 6,
    # Straighten a band whose ruled line is tilted by more than this (degrees).
    "deskew_min_deg": 0.5,
    "deskew_max_deg": 5.0,
    # A punctuation-only OCR word (":", ".") narrower than this page fraction is
    # treated as part of the printed labels.
    "punct_mask_max_w": 0.012,
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
    # Textract WORD TextType ("PRINTED" / "HANDWRITING"); None for LINEs and
    # pdfminer text.
    text_type: Optional[str] = None

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
    # Left edge of this signatory's own column (its label, minus a small
    # margin). Ink to the left of it is a neighbour's signature overhanging
    # the column boundary and must not count toward this signatory.
    core_x0: Optional[float] = None
    # Left edge of the NEXT column's core. Ink at or beyond it belongs to the
    # neighbour on the right.
    core_x1: Optional[float] = None
    # Boxes of OCR words tagged HANDWRITING inside the band. Supporting
    # evidence only: they are never masked, and never enough on their own.
    handwriting: List[Tuple[float, float, float, float]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page": self.page,
            "x0": round(self.x0, 5),
            "y0": round(self.y0, 5),
            "x1": round(self.x1, 5),
            "y1": round(self.y1, 5),
            "masks": [[round(v, 5) for v in box] for box in self.masks],
            "source": self.source,
            "core_x0": None if self.core_x0 is None else round(self.core_x0, 5),
            "core_x1": None if self.core_x1 is None else round(self.core_x1, 5),
            "handwriting": [[round(v, 5) for v in box] for box in self.handwriting],
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
            core_x0=None if data.get("core_x0") is None else float(data["core_x0"]),
            core_x1=None if data.get("core_x1") is None else float(data["core_x1"]),
            handwriting=[tuple(float(v) for v in box) for box in data.get("handwriting", [])],
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
                text_type=block.get("TextType"),
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


def _word_key(text: str) -> str:
    """Lower-case letters and digits only - "by:" -> "by", "ENGR." -> "engr"."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def printed_name_terms(names: Optional[Dict[str, str]]) -> frozenset:
    """Words of the extracted printed names (every signatory), for masking.

    A neighbour's printed name can sit inside a band too, so all of them count
    as expected printed text, not only the band's own signatory.
    """
    terms = set()
    for value in (names or {}).values():
        for token in str(value or "").split():
            key = _word_key(token)
            if len(key) >= 2:
                terms.add(key)
    return frozenset(terms)


@dataclass
class _Tilt:
    """Page tilt of a scan, as a straight-line slope in normalized units.

    OCR boxes are axis-aligned, so on a scan rotated by a degree or two a row
    of printed text drifts up or down across the page and a long line's box is
    taller than the text itself. ``straight`` maps a box back onto the level
    reference frame (the x of the "Requested by" heading); ``offset`` gives how
    far a level row has drifted at a given x. A digital PDF has slope 0, which
    makes every mapping the identity.
    """

    slope: float = 0.0
    ref_x: float = 0.0

    def offset(self, x: float) -> float:
        return self.slope * (x - self.ref_x)

    def straight(self, line: TextLine) -> Tuple[float, float]:
        if not self.slope:
            return line.y0, line.y1
        cx = (line.x0 + line.x1) / 2.0
        cy = (line.y0 + line.y1) / 2.0 - self.offset(cx)
        true_h = max(line.height - abs(self.slope) * (line.x1 - line.x0), min(line.height, 0.006))
        return cy - true_h / 2.0, cy + true_h / 2.0


_LEVEL = _Tilt()


def _estimate_tilt(words: List[TextLine], heading: TextLine) -> _Tilt:
    """Slope of the signatory heading row from its three label words."""
    ref_x = (heading.x0 + heading.x1) / 2.0
    if not words:
        return _Tilt(0.0, ref_x)
    points = []
    for needle in ("requested", "funds", "approved"):
        hits = [
            w for w in words
            if w.page == heading.page and needle in w.norm
            and abs((w.y0 + w.y1) / 2.0 - (heading.y0 + heading.y1) / 2.0) <= 0.04
        ]
        if hits:
            hit = min(hits, key=lambda w: abs(w.y0 - heading.y0))
            points.append(((hit.x0 + hit.x1) / 2.0, (hit.y0 + hit.y1) / 2.0))
    if len(points) < 2 or (max(p[0] for p in points) - min(p[0] for p in points)) < 0.2:
        return _Tilt(0.0, ref_x)
    mean_x = sum(p[0] for p in points) / len(points)
    mean_y = sum(p[1] for p in points) / len(points)
    var_x = sum((p[0] - mean_x) ** 2 for p in points)
    slope = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points) / var_x
    if abs(slope) < 0.002:  # level enough: well under half a degree
        slope = 0.0
    slope = max(-0.1, min(0.1, slope))
    return _Tilt(slope, ref_x)


def _printed_rows(lines: List[TextLine], page: int, tilt: _Tilt = _LEVEL) -> List[Tuple[float, float]]:
    """Vertical extent of each "Printed Name :" / "Designation :" row, in the
    level reference frame."""
    return [
        tilt.straight(line) for line in lines
        if line.page == page and ("printed name" in line.norm or line.norm.startswith("designation"))
    ]


def _word_masks(
    words: List[TextLine],
    lines: List[TextLine],
    page: int,
    band_top: float,
    band_bottom: float,
    printed_terms: frozenset = frozenset(),
    tilt: _Tilt = _LEVEL,
) -> Tuple[List[Tuple[float, float, float, float]], List[Tuple[float, float, float, float]]]:
    """Masks built from OCR WORD boxes, by what the form is expected to print.

    Textract reads a handwritten signature as a word ("fl", "ft"), and may tag
    it PRINTED or HANDWRITING, so masking every recognised word erases the very
    signature being looked for. A word in the band is masked only when it is
    known printed text:

    * one of the form's own label words (``PRINTED_LABEL_WORDS``) or a short
      punctuation mark such as the ":" after a label;
    * a word of an extracted printed name (``printed_terms``);
    * a non-handwriting word whose centre lies on a "Printed Name :" or
      "Designation :" row - those rows only ever hold printed names and
      designations, which covers a name the extractor did not return.

    Every other word is left in, whatever its TextType. Words tagged
    HANDWRITING are returned separately as supporting evidence.
    """
    masks: List[Tuple[float, float, float, float]] = []
    handwriting: List[Tuple[float, float, float, float]] = []
    rows = _printed_rows(lines, page, tilt)
    for word in words:
        if word.page != page:
            continue
        top, bottom = tilt.straight(word)
        if bottom < band_top - 0.02 or top > band_bottom + 0.02:
            continue
        box = (word.x0, word.y0, word.x1, word.y1)
        key = _word_key(word.text)
        centre_y = (top + bottom) / 2.0
        on_printed_row = word.text_type != "HANDWRITING" and any(
            (top - 0.002) <= centre_y <= (bottom + 0.002) for top, bottom in rows
        )
        expected = (
            key in PRINTED_LABEL_WORDS
            or key in printed_terms
            or (not key and (word.x1 - word.x0) <= _THRESHOLDS["punct_mask_max_w"])
            or on_printed_row
        )
        if expected:
            masks.append(box)
        elif word.text_type == "HANDWRITING":
            handwriting.append(box)
    return masks, handwriting


def _band_masks(
    lines: List[TextLine],
    words: List[TextLine],
    page: int,
    band_top: float,
    band_bottom: float,
    printed_terms: frozenset,
    tilt: _Tilt = _LEVEL,
):
    """(masks, handwriting boxes) for one band.

    With OCR word boxes (Textract), masks come from the expected-printed-text
    rules in ``_word_masks``. Without them (a digital PDF read by pdfminer) every
    text line is genuinely printed - a signature is never part of the text
    layer - so the line boxes are masked as before.
    """
    if words:
        return _word_masks(words, lines, page, band_top, band_bottom, printed_terms, tilt)
    return _text_masks(lines, page, band_top, band_bottom), []


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


def _label_start_x(
    lines: List[TextLine],
    words: List[TextLine],
    needle: str,
    line: Optional[TextLine],
) -> Optional[float]:
    """Left edge of one label (e.g. "funds") inside a heading line.

    On this form "Requested by:", "Funds Available:" and "Approved by:" share one
    text line, so the line's own x0 belongs to the first label only. Prefer
    Textract WORD boxes; otherwise use the pdfminer character boxes of the line.
    """
    if line is None:
        return None
    hits = [
        w for w in words
        if w.page == line.page and needle in w.norm
        and (line.y0 - 0.01) <= w.y0 <= (line.y1 + 0.01)
    ]
    if hits:
        return min(hits, key=lambda w: w.x0).x0
    if line.char_boxes:
        joined = "".join(ch for ch, _, _ in line.char_boxes).lower()
        idx = joined.find(needle)
        if idx >= 0:
            return line.char_boxes[idx][1]
    if needle in line.norm:
        return line.x0
    return None


def compute_regions(
    lines: List[TextLine],
    words: Optional[List[TextLine]] = None,
    printed_terms: frozenset = frozenset(),
) -> Dict[str, Region]:
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
    # Scans are often tilted a degree or two. Work in a level frame (see
    # _Tilt) and shift each column's band by the tilt at that column.
    tilt = _estimate_tilt(words, heading)
    headings = [h for h in (heading, funds_heading, approved_heading) if h is not None and h.page == page]
    heading_bottom = max(tilt.straight(h)[1] for h in headings)
    heading_top = min(tilt.straight(h)[0] for h in headings)

    signature_rows = [
        line for line in _all_lines(lines, "signature")
        if line.page == page and tilt.straight(line)[0] >= heading_top - 0.002
    ]
    signature_rows.sort(key=lambda l: tilt.straight(l)[0])
    main_sig_row = signature_rows[0] if signature_rows else None

    printed_rows = [
        line for line in _all_lines(lines, "printed name")
        if line.page == page and tilt.straight(line)[0] >= heading_bottom - 0.002
    ]
    printed_rows.sort(key=lambda l: tilt.straight(l)[0])
    main_printed_row = printed_rows[0] if printed_rows else None

    # Vertical band: from just under the heading down to a little past the ruled
    # signature line - never into the printed-name row.
    band_top = heading_bottom + 0.001
    if main_sig_row is not None:
        sig_y0, sig_y1 = tilt.straight(main_sig_row)
        sig_h = max(sig_y1 - sig_y0, 0.008)
        band_bottom = min(sig_y1 + 0.8 * sig_h, sig_y1 + 0.05)
        if main_printed_row is not None:
            band_bottom = min(band_bottom, tilt.straight(main_printed_row)[0] - 0.001)
        # Keep a floor height even if the sig row hugs the heading.
        band_bottom = max(band_bottom, band_top + 0.028)
    elif main_printed_row is not None:
        band_bottom = tilt.straight(main_printed_row)[0] - 0.002
    else:
        band_bottom = band_top + 0.06
    if band_bottom <= band_top:
        band_bottom = band_top + 0.03

    # Column boundaries. Prefer Textract WORD centres for the three headings;
    # fall back to an even split of the signature-row content span.
    # Heading words drift with the tilt; widen the search by the full drift.
    drift = abs(tilt.slope)
    centres = [
        _word_center_x(words, "requested", page, heading_top - drift, heading_bottom + drift),
        _word_center_x(words, "funds", page, heading_top - drift, heading_bottom + drift)
        or _word_center_x(words, "available", page, heading_top - drift, heading_bottom + drift),
        _word_center_x(words, "approved", page, heading_top - drift, heading_bottom + drift),
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

    masks, handwriting = _band_masks(lines, words, page, band_top, band_bottom, printed_terms, tilt)

    column_headings = (heading, funds_heading, approved_heading)
    label_x0 = [
        _label_start_x(lines, words, needle, head)
        for needle, head in zip(("requested", "funds", "approved"), column_headings)
    ]
    cores = [
        None if x is None else max(0.0, x - _THRESHOLDS["column_core_margin"])
        for x in label_x0
    ]
    # Typical column width, from the spacing of the heading labels. Signatures
    # often run past the printed rule's right end (the right-most column's rule
    # is the one most often cut short), so each band is widened to a full column
    # from its own label rather than trusting the rule's measured extent.
    label_x0s = [x for x in label_x0 if x is not None]
    gaps = [b - a for a, b in zip(label_x0s, label_x0s[1:]) if b > a]
    column_w = sorted(gaps)[len(gaps) // 2] if gaps else None
    for i, (key, (x0, x1), head) in enumerate(zip(
        (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY), bounds, column_headings
    )):
        core_x0 = cores[i]
        core_x1 = cores[i + 1] if i + 1 < len(cores) else None
        if core_x0 is not None and column_w is not None:
            x1 = max(x1, min(0.98, core_x0 + column_w))
        # The level band, moved to where this column's row actually sits.
        shift = tilt.offset((x0 + x1) / 2.0)
        regions[key] = Region(
            page=page,
            x0=max(0.0, x0),
            y0=max(0.0, band_top + shift),
            x1=min(1.0, x1),
            y1=min(1.0, band_bottom + shift),
            masks=[m for m in masks if m[2] >= x0 and m[0] <= x1],
            source="anchors",
            core_x0=core_x0,
            core_x1=core_x1,
            handwriting=[b for b in handwriting if b[2] >= x0 and b[0] <= x1],
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

        twg_masks, twg_hand = _band_masks(lines, words, twg_page, t_top, t_bottom, printed_terms)
        regions[TWG] = Region(
            page=twg_page, x0=t_left, y0=t_top, x1=t_right, y1=t_bottom,
            masks=twg_masks, source="anchors",
            handwriting=[b for b in twg_hand if b[2] >= t_left and b[0] <= t_right],
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


def _ink_threshold(crop) -> Tuple[float, float]:
    """(gray cutoff below which a pixel is ink, estimated paper level)."""
    import numpy as np

    paper = float(np.percentile(crop, 95)) if crop.size else 255.0
    threshold = min(float(_THRESHOLDS["ink_gray_ceiling"]), paper - _THRESHOLDS["ink_below_paper"])
    return max(threshold, 1.0), paper


def _remove_speckle(binary, cv2):
    """Drop connected blobs too small to be pen strokes (scan dust/noise)."""
    if cv2 is None or not binary.any():
        return binary
    import numpy as np

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    small = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] <= _THRESHOLDS["speckle_max_px"]]
    if small:
        binary = binary.copy()
        binary[np.isin(labels, small)] = 0
    return binary


def _estimate_skew(binary, cv2) -> Optional[float]:
    """Tilt (degrees) of the band's ruled line, or None when it is level.

    Scans are rarely perfectly straight; a ruled line tilted by a degree drifts
    a few pixels across the band, which the horizontal rule filter cannot
    remove. Long, nearly-horizontal segments are the ruled line(s).
    """
    if cv2 is None or not binary.any():
        return None
    import numpy as np

    ch, cw = binary.shape
    segments = cv2.HoughLinesP(
        binary * 255, 1, np.pi / 720, threshold=max(20, int(0.2 * cw)),
        minLineLength=max(20, int(0.25 * cw)), maxLineGap=max(3, int(0.01 * cw)),
    )
    if segments is None:
        return None
    angles = []
    for x1, y1, x2, y2 in segments[:, 0]:
        if x2 == x1:
            continue
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if abs(angle) <= _THRESHOLDS["deskew_max_deg"]:
            angles.append(angle)
    if not angles:
        return None
    angle = float(np.median(angles))
    return angle if abs(angle) > _THRESHOLDS["deskew_min_deg"] else None


def _rotate_binary(binary, angle_deg: float, cv2):
    """Rotate a binary band about its centre so a tilted rule becomes level."""
    ch, cw = binary.shape
    matrix = cv2.getRotationMatrix2D((cw / 2.0, ch / 2.0), angle_deg, 1.0)
    return cv2.warpAffine(
        binary, matrix, (cw, ch), flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )


def _row_ownership(gray, regions: Dict[str, Region]) -> Dict[str, Any]:
    """Which signature column each stroke in the main row belongs to.

    The three main boxes share one row. A long signature can run under the
    next column's label, and a signature can start left of its own label, so
    cutting at fixed x positions still leaves a neighbour's stroke inside a
    blank box. Here the whole row is analysed once: the printed rule is
    removed, each connected stroke is assigned to the column whose core holds
    its centre, and for every column a mask of the ink owned by the OTHER
    columns is returned as ``(mask, row_y0_px, row_x0_px)`` in page pixels.
    """
    import numpy as np

    try:
        import cv2
    except Exception:  # pragma: no cover
        return {}

    keys = [
        key for key in REQUIRED_SIGNATORIES
        if regions.get(key) is not None and regions[key].valid and regions[key].core_x0 is not None
    ]
    if len(keys) < 2:
        return {}
    rows = [regions[key] for key in keys]
    if len({r.page for r in rows}) != 1:
        return {}

    h, w = gray.shape[:2]
    # On a tilted scan each column's band sits a little higher or lower; the
    # row crop covers all of them.
    py0 = max(0, int(round(min(r.y0 for r in rows) * h)))
    py1 = min(h, int(round(max(r.y1 for r in rows) * h)))
    rx0 = max(0, int(round(min(r.x0 for r in rows) * w)))
    rx1 = min(w, int(round(max(r.x1 for r in rows) * w)))
    if py1 - py0 < _THRESHOLDS["min_region_px"] or rx1 - rx0 < _THRESHOLDS["min_region_px"]:
        return {}
    crop = np.ascontiguousarray(gray[py0:py1, rx0:rx1].astype("uint8"))
    threshold, _ = _ink_threshold(crop)
    binary = (crop < threshold).astype("uint8")
    ch, cw = binary.shape
    for region in rows:
        for mx0, my0, mx1, my1 in region.masks:
            a, b = int(round(mx0 * w)) - rx0, int(round(mx1 * w)) - rx0
            c, d = int(round(my0 * h)) - py0, int(round(my1 * h)) - py0
            a, b, c, d = max(0, a), min(cw, b), max(0, c), min(ch, d)
            if b > a and d > c:
                binary[c:d, a:b] = 0
    binary = _remove_speckle(binary, cv2)

    angle = _estimate_skew(binary, cv2)
    work = _rotate_binary(binary, angle, cv2) if angle else binary

    cores = []
    for region in rows:
        right = region.core_x1 if region.core_x1 is not None else 1.0
        cores.append((region.core_x0, right))
    column_px = max(12, int(min(b - a for a, b in cores) * w))
    horizontal = cv2.morphologyEx(
        work, cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, int(0.33 * column_px)), 1)),
    )
    horizontal = cv2.dilate(horizontal, np.ones((3, 1), "uint8"))
    horizontal[:, work.sum(axis=0) > max(3, int(0.16 * ch))] = 0
    cleaned = np.clip(work.astype("int16") - horizontal.astype("int16"), 0, 1).astype("uint8")

    # Erasing the rule cuts a signature into pieces wherever it crosses the
    # line. Bridge those small vertical gaps so each signature is judged as one
    # stroke, then measure each stroke on its real (unbridged) pixels.
    bridged = cv2.dilate(cleaned, np.ones((9, 3), "uint8"))
    count, bridged_labels, stats, _ = cv2.connectedComponentsWithStats(bridged, connectivity=8)
    labels = bridged_labels * cleaned
    flat = labels.ravel()
    area = np.bincount(flat, minlength=count)
    x_sum = np.bincount(flat, weights=np.tile(np.arange(cw), ch).astype("float64"), minlength=count)
    owner = np.full(count, -1)
    for i in range(1, count):
        if area[i] < 8:
            continue
        if stats[i, cv2.CC_STAT_WIDTH] > 1.5 * column_px:
            continue  # spans several columns (a rule remnant) - not attributable
        centre = (rx0 + x_sum[i] / area[i]) / w
        for j, (left, right) in enumerate(cores):
            if left <= centre < right:
                owner[i] = j
                break

    result: Dict[str, Any] = {}
    for j, key in enumerate(keys):
        others = [i for i in range(1, count) if owner[i] not in (-1, j)]
        foreign = np.isin(bridged_labels, others).astype("uint8") if others else np.zeros_like(cleaned)
        if angle and foreign.any():
            foreign = _rotate_binary(foreign, -angle, cv2)
        if foreign.any():
            foreign = cv2.dilate(foreign, np.ones((3, 3), "uint8"))
        result[key] = (foreign.astype(bool), py0, rx0)
    return result


def _handwriting_in_core(region: Region) -> List[Tuple[float, float, float, float]]:
    """HANDWRITING word boxes whose centre falls inside this column's core."""
    left = region.core_x0 if region.core_x0 is not None else region.x0
    right = region.core_x1 if region.core_x1 is not None else region.x1
    hits = []
    for box in region.handwriting:
        cx = (box[0] + box[2]) / 2.0
        cy = (box[1] + box[3]) / 2.0
        if left <= cx <= right and region.x0 <= cx <= region.x1 and (region.y0 - 0.01) <= cy <= (region.y1 + 0.01):
            hits.append(box)
    return hits


def _classify_region(gray, region: Region, foreign=None) -> Dict[str, Any]:
    """Classify one band. ``foreign`` (from ``_row_ownership``) marks ink that
    belongs to a neighbouring column's signature and must not count here."""
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
        return {"state": STATE_UNCERTAIN, "confidence": 0.2, "reason": "region_too_small"}

    crop = np.ascontiguousarray(gray[py0:py1, px0:px1].astype("uint8"))

    # Binarise: ink = 1. Not Otsu: Otsu on a band with a dark mark picks a
    # cutoff that drops light pencil and faint pen strokes, which is the
    # variation between writers. Instead the cutoff is set relative to the
    # band's own paper (a high percentile, since ink covers only a few percent
    # of a band), capped at the fixed ceiling: white paper gives the ceiling,
    # gray or tinted scanner paper gives a proportionally lower cutoff.
    threshold, paper_level = _ink_threshold(crop)
    binary = (crop < threshold).astype("uint8")
    if foreign is not None:
        owned_elsewhere, row_y0, row_x0 = foreign
        a, b = px0 - row_x0, px1 - row_x0
        r0 = py0 - row_y0
        r1 = r0 + binary.shape[0]
        if r0 >= 0 and r1 <= owned_elsewhere.shape[0] and a >= 0 and b <= owned_elsewhere.shape[1]:
            binary[owned_elsewhere[r0:r1, a:b]] = 0

    ch, cw = binary.shape
    # Columns of the crop still in play after the core cut-offs; the rule filter
    # is sized from this, not from the whole band.
    live_x0, live_x1 = 0, cw
    # Ink left of this column's core is a neighbouring signature overhanging the
    # boundary. Drop it so the blank box next to a signed one is not "signed".
    if region.core_x0 is not None and region.x1 > region.x0:
        cut = int(round((region.core_x0 - region.x0) / (region.x1 - region.x0) * cw))
        if cut > 0:
            binary[:, : min(cut, cw)] = 0
            live_x0 = min(cut, cw)
    if region.core_x1 is not None and region.x1 > region.x0:
        cut = int(round((region.core_x1 - region.x0) / (region.x1 - region.x0) * cw))
        if cut < cw:
            binary[:, max(0, cut):] = 0
            live_x1 = max(0, cut)
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

    # Scan clean-up: drop speckle, then straighten a tilted ruled line so the
    # horizontal rule filter below can remove it.
    binary = _remove_speckle(binary, cv2)
    skew_deg = _estimate_skew(binary, cv2)
    if skew_deg is not None:
        binary = _rotate_binary(binary, skew_deg, cv2)
    ch, cw = binary.shape

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
        live_w = max(1, live_x1 - live_x0)
        kernel_w = max(12, int(live_w * _THRESHOLDS["rule_line_kernel_frac"]))
        horizontal = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
        )
    else:
        horizontal = np.zeros_like(binary)
        for r in range(ch):
            if binary[r].sum() > 0.55 * cw:
                horizontal[r, :] = 1
    if cv2 is not None and horizontal.any():
        # A scanned rule has ragged edges; take the row above and below too.
        horizontal = cv2.dilate(horizontal, np.ones((3, 1), "uint8"))
    # Rows the printed rule occupies (with a little slack), for telling a
    # leftover piece of the rule from a pen stroke below.
    rule_rows = horizontal.any(axis=1)
    if rule_rows.any():
        idx = np.where(rule_rows)[0]
        rule_rows = np.zeros(ch, dtype=bool)
        rule_rows[max(0, idx.min() - 3): min(ch, idx.max() + 4)] = True
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
    # several connected components. Measured over blobs of real size only, so
    # scattered scan dust cannot make a flat remnant look tall.
    spread_h = spread_w = 0.0
    significant = cleaned
    if cv2 is not None and cleaned.any():
        count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
        keep = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= min_area]
        significant = np.isin(labels, keep) if keep else np.zeros_like(cleaned, dtype=bool)
    on_rule_only = False
    if significant.any():
        rows = np.where(significant.any(axis=1))[0]
        cols = np.where(significant.any(axis=0))[0]
        spread_h = (rows.max() - rows.min() + 1) / max(ch, 1)
        spread_w = (cols.max() - cols.min() + 1) / max(cw, 1)
        # Everything left is a thin sliver lying on the printed rule's rows: a
        # piece of the rule the filter could not take (it was cut short, e.g.
        # by a neighbour's masked stroke), not something written.
        on_rule_only = bool(
            rule_rows.any()
            and rule_rows[rows].all()
            and (rows.max() - rows.min() + 1) <= max(5, 0.08 * ch)
        )

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
        "paper_level": round(paper_level, 1),
        "ink_threshold": round(threshold, 1),
        "skew_deg": round(skew_deg or 0.0, 2),
        "handwriting_words": len(_handwriting_in_core(region)),
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

    # OCR reading a handwritten word in this column supports "present" but is
    # never enough on its own: the ink must agree.
    handwriting_seen = metrics["handwriting_words"] > 0

    if strong_mark or has_mark:
        over = max(0.0, ink_ratio - _THRESHOLDS["ink_present_min"])
        confidence = min(0.96, 0.6 + 6.0 * over + 0.12 * max(spread_w, raw_spread_w))
        if handwriting_seen:
            confidence = min(0.98, confidence + 0.05)
        return {"state": STATE_PRESENT, "confidence": round(confidence, 3), "metrics": metrics}

    if raw_mark:
        # The mark only shows before the ruled line is stripped - something
        # sits on the line, but it may be a thickened rule or a smudge.
        return {"state": STATE_UNCERTAIN, "confidence": 0.5, "metrics": metrics, "reason": "weak_mark"}

    # Blank: either almost no ink at all, or only baseline-flat fragments with no
    # blob of any size and no vertical structure in the raw mark either.
    negligible_ink = ink_ratio <= _THRESHOLDS["ink_absent_max"]
    flat_remnant_only = (
        not has_vertical
        and (largest_area_frac < 0.004 or on_rule_only)
        and raw_vertical_frac < 0.10
    )
    if negligible_ink or flat_remnant_only:
        if handwriting_seen:
            # OCR read handwriting here but the ink is too weak to confirm it.
            return {"state": STATE_UNCERTAIN, "confidence": 0.45, "metrics": metrics, "reason": "handwriting_weak_ink"}
        confidence = 0.9 - 30.0 * ink_ratio
        return {"state": STATE_ABSENT, "confidence": round(max(0.6, confidence), 3), "metrics": metrics}

    # Some ink that rises off the line but is not a confident stroke: never a
    # silent pass - the reviewer has to look at the document.
    return {"state": STATE_UNCERTAIN, "confidence": 0.5, "metrics": metrics, "reason": "ambiguous_ink"}


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
    ownership: Dict[int, Dict[str, Any]] = {}
    scale = _THRESHOLDS["render_scale"]

    for key in ALL_SIGNATORIES:
        region = regions.get(key)
        if region is None or not region.valid:
            # The page was read but this box could not be found: the reviewer
            # has to look at the document.
            results[key] = {"state": STATE_UNCERTAIN, "confidence": 0.15, "reason": "region_not_located"}
            continue
        if region.page not in rendered:
            rendered[region.page] = _render_page(path, region.page, scale)
        gray = rendered.get(region.page)
        if gray is None:
            results[key] = {"state": STATE_UNVERIFIABLE, "confidence": 0.15, "reason": "page_render_failed"}
            continue
        if region.page not in ownership:
            try:
                ownership[region.page] = _row_ownership(gray, regions)
            except Exception:
                logger.exception("SIGNATURE row ownership failed")
                ownership[region.page] = {}
        try:
            results[key] = _classify_region(gray, region, ownership[region.page].get(key))
            _debug_dump(gray, region, key, results[key])
        except Exception:
            logger.exception("SIGNATURE classify failed for %s", key)
            results[key] = {"state": STATE_UNVERIFIABLE, "confidence": 0.2, "reason": "analysis_error"}
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _summarise(signatories: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    states = {
        key: (signatories.get(key) or {}).get("state", STATE_UNVERIFIABLE)
        for key in REQUIRED_SIGNATORIES
    }
    detected = [key for key, state in states.items() if state == STATE_PRESENT]
    missing = [DISPLAY_NAMES[key] for key, state in states.items() if state == STATE_ABSENT]
    uncertain_keys = [key for key, state in states.items() if state == STATE_UNCERTAIN]
    unverifiable = [
        DISPLAY_NAMES[key] for key, state in states.items()
        if state not in (STATE_PRESENT, STATE_ABSENT, STATE_UNCERTAIN)
    ]
    all_present = len(detected) == len(REQUIRED_SIGNATORIES)
    # No silent passes: the save is allowed only when every required box has
    # clear ink. Uncertain boxes can be released by a reviewer confirming them
    # (``needs_confirmation``); a blank or unreadable box cannot.
    can_save = all_present
    needs_confirmation = bool(uncertain_keys) and not missing and not unverifiable

    if all_present:
        status = "complete"
        message = "All required signatures are present."
    elif missing:
        status = "incomplete"
        message = "One or more required signatures are missing."
    elif needs_confirmation:
        status = "needs_confirmation"
        message = "Please confirm the signatures marked for review against the original document."
    else:
        status = "unverifiable"
        message = "Signatures could not be checked. Please review the original document."
    return {
        "required_total": len(REQUIRED_SIGNATORIES),
        "required_detected": len(detected),
        "missing_signatures": missing,
        "uncertain_signatures": [DISPLAY_NAMES[key] for key in uncertain_keys],
        "uncertain_keys": uncertain_keys,
        "unverifiable_signatures": unverifiable,
        "all_required_present": all_present,
        "needs_confirmation": needs_confirmation,
        "can_save": can_save,
        "status": status,
        "message": message,
    }


def _payload(signatories: Dict[str, Dict[str, Any]], names: Optional[Dict[str, str]], regions: Dict[str, Region]) -> Dict[str, Any]:
    names = names or {}
    # Each signatory is judged on its own ink. (A former "row consensus" step
    # promoted a blank box to signed when its neighbours were signed; it was
    # removed because it passed blank boxes carrying a neighbour's stroke.)
    signatories = dict(signatories)
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
    if not path.is_file():
        return _payload(
            {key: {"state": STATE_UNVERIFIABLE, "confidence": 0.0, "reason": "document_missing"} for key in ALL_SIGNATORIES},
            names, {},
        )
    printed_terms = printed_name_terms(names)

    def _run(lines: List[TextLine], words: List[TextLine]):
        regions = compute_regions(lines, words, printed_terms)
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

    if not any(regions for regions, _ in candidates):
        # No OCR geometry at all (an image-only scan without Textract output):
        # the boxes cannot be found, so nothing is guessed - the reviewer
        # confirms each signature against the document.
        return _payload(
            {key: {"state": STATE_UNCERTAIN, "confidence": 0.0, "reason": "no_ocr_geometry"} for key in ALL_SIGNATORIES},
            names, {},
        )

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
    """An all-unverifiable result (the document itself is unavailable)."""
    return _payload(
        {key: {"state": STATE_UNVERIFIABLE, "confidence": 0.0, "reason": "document_missing"} for key in ALL_SIGNATORIES},
        names, {},
    )

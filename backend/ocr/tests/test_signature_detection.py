"""Tests for the isolated signature-presence detector.

Synthetic CTU-style Purchase Request PDFs are built with reportlab so both the
"signed" and "unsigned" states can be exercised without a real scanned corpus.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ocr.signature_detection import (  # noqa: E402
    APPROVED_BY,
    FUNDS_AVAILABLE,
    REQUESTED_BY,
    STATE_ABSENT,
    STATE_PRESENT,
    TWG,
    Region,
    analyze,
    compute_regions,
    reanalyze,
)

reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")


PAGE_W, PAGE_H = 612.0, 792.0


def _build_pr_pdf(path: Path, signed: dict | None = None) -> None:
    """Draw a minimal CTU PR footer; ``signed`` maps signatory key -> bool."""
    signed = signed or {}
    c = reportlab_canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
    c.setFont("Helvetica", 10)

    # Some body text up top so the footer is not mistaken for the header.
    c.drawString(72, 720, "PURCHASE REQUEST")
    c.drawString(72, 700, "Entity Name: CTU-Tuburan Campus")
    c.drawString(72, 680, "Item Description  Quantity  Unit Cost  Total Cost")
    c.drawString(72, 660, "Supply and delivery of demo goods  1  100.00  100.00")
    c.drawString(72, 620, "Purpose: demonstration purchase request")

    # Footer signatory block - column-aligned, mirroring the real template.
    col_x = {REQUESTED_BY: 80, FUNDS_AVAILABLE: 250, APPROVED_BY: 420}
    c.drawString(col_x[REQUESTED_BY], 200, "Requested by:")
    c.drawString(col_x[FUNDS_AVAILABLE], 200, "Funds Available:")
    c.drawString(col_x[APPROVED_BY], 200, "Approved by:")
    c.drawString(72, 176, "Signature :   ________________   ________________   ________________")
    c.drawString(72, 150, "Printed Name :")
    for cx, nm in zip(col_x.values(), ("JUAN CRUZ", "MARIA SANTOS", "PEDRO REYES")):
        c.drawString(cx, 150, nm)
    c.drawString(72, 132, "Designation :")
    c.drawString(72, 108, "Specifications verified by Technical Working Group:")
    c.drawString(72, 92, "Signature :   ________________")
    c.drawString(72, 66, "Printed Name : ANA DELA CRUZ")
    c.drawString(72, 48, "Designation : TWG Member")

    def scribble(cx: float, baseline: float, *, width: float = 1.6, span: float = 96.0, amp: float = 16.0) -> None:
        c.setLineWidth(width)
        path_obj = c.beginPath()
        path_obj.moveTo(cx, baseline)
        for i in range(1, 28):
            t = i / 27.0
            x = cx + t * span
            y = baseline + (amp if i % 2 else -(amp * 0.75)) * (0.35 + t)
            path_obj.lineTo(x, y)
        c.drawPath(path_obj, stroke=1, fill=0)
        c.setLineWidth(1)

    def mark(key: str, cx: float, baseline: float) -> None:
        spec = signed.get(key)
        if not spec:
            return
        if spec == "faint":
            scribble(cx, baseline, width=0.4, span=42.0, amp=7.0)
        elif spec == "initials":
            scribble(cx, baseline, width=1.2, span=22.0, amp=12.0)
        else:
            scribble(cx, baseline)

    mark(REQUESTED_BY, col_x[REQUESTED_BY] + 4, 181)
    mark(FUNDS_AVAILABLE, col_x[FUNDS_AVAILABLE] + 4, 181)
    mark(APPROVED_BY, col_x[APPROVED_BY] + 4, 181)
    mark(TWG, 154, 97)

    c.showPage()
    c.save()


def _build_pr_pdf_isolated_labels(path: Path, signed: dict | None = None) -> None:
    """Appendix-60-style layout where every "Signature :" label is printed as
    its own short, isolated text run and the ruled blank is a drawn line
    (e.g. a table-cell border), never a run of underscore characters sharing
    the same recognised text line as the label.

    ``_build_pr_pdf`` above instead draws "Signature :   ____" as one single
    line, so the label is only a small fraction of that line's measured
    width - which is what let the old label-masking formula (a fixed
    fraction of the *line's* width) happen to cover the label well enough by
    coincidence. When the label is recognised on its own - as it is on the
    real form this bug was found on - that formula masks only a fraction of
    the label itself, leaving printed letters exposed as "ink" for the
    classifier to mistake for a handwritten mark. This layout reproduces
    that shape for all four signatories, not just TWG, since the bug is in
    the masking formula, not particular to any one signatory block.
    """
    signed = signed or {}
    c = reportlab_canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
    c.setFont("Helvetica", 10)

    c.drawString(72, 720, "PURCHASE REQUEST")
    c.drawString(72, 700, "Entity Name: CTU-Tuburan Campus")
    c.drawString(72, 680, "Item Description  Quantity  Unit Cost  Total Cost")
    c.drawString(72, 660, "Supply and delivery of demo goods  1  100.00  100.00")
    c.drawString(72, 620, "Purpose: demonstration purchase request")

    col_x = {REQUESTED_BY: 80, FUNDS_AVAILABLE: 250, APPROVED_BY: 420}
    c.drawString(col_x[REQUESTED_BY], 200, "Requested by:")
    c.drawString(col_x[FUNDS_AVAILABLE], 200, "Funds Available:")
    c.drawString(col_x[APPROVED_BY], 200, "Approved by:")
    for cx in col_x.values():
        # The label stands alone - the ruled blank itself is unprinted space
        # (e.g. a table-cell border in the real document, not text), so
        # nothing dilutes the label's share of this line's measured width.
        c.drawString(cx, 176, "Signature :")
    c.drawString(72, 150, "Printed Name :")
    for cx, nm in zip(col_x.values(), ("JUAN CRUZ", "MARIA SANTOS", "PEDRO REYES")):
        c.drawString(cx, 150, nm)
    c.drawString(72, 132, "Designation :")
    c.drawString(72, 108, "Specifications verified by Technical Working Group:")
    c.drawString(72, 92, "Signature :")
    c.drawString(72, 66, "Printed Name : ANA DELA CRUZ")
    c.drawString(72, 48, "Designation : TWG Member")

    def scribble(cx: float, baseline: float) -> None:
        c.setLineWidth(1.6)
        path_obj = c.beginPath()
        path_obj.moveTo(cx, baseline)
        for i in range(1, 28):
            t = i / 27.0
            x = cx + t * 96.0
            y = baseline + (16.0 if i % 2 else -12.0) * (0.35 + t)
            path_obj.lineTo(x, y)
        c.drawPath(path_obj, stroke=1, fill=0)
        c.setLineWidth(1)

    if signed.get(REQUESTED_BY):
        scribble(col_x[REQUESTED_BY] + 4, 181)
    if signed.get(FUNDS_AVAILABLE):
        scribble(col_x[FUNDS_AVAILABLE] + 4, 181)
    if signed.get(APPROVED_BY):
        scribble(col_x[APPROVED_BY] + 4, 181)
    if signed.get(TWG):
        scribble(154, 97)

    c.showPage()
    c.save()


# ---------------------------------------------------------------------------
# Region derivation
# ---------------------------------------------------------------------------
def test_regions_locate_all_four_signatories(tmp_path):
    pdf = tmp_path / "pr.pdf"
    _build_pr_pdf(pdf)
    from ocr.signature_detection import collect_text_lines

    regions = compute_regions(collect_text_lines(pdf))
    assert set(regions) >= {REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY, TWG}
    # The three main columns are ordered left-to-right and do not overlap.
    xs = [regions[k].x0 for k in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY)]
    assert xs == sorted(xs)
    for region in regions.values():
        assert region.valid


def test_regions_empty_without_geometry(tmp_path):
    # An image with no OCR text geometry yields no regions (-> unverifiable).
    assert compute_regions([]) == {}


# ---------------------------------------------------------------------------
# End-to-end classification
# ---------------------------------------------------------------------------
def test_unsigned_pr_reports_every_required_signature_missing(tmp_path):
    pdf = tmp_path / "unsigned.pdf"
    _build_pr_pdf(pdf, signed={})
    result = analyze(pdf)

    for key in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY):
        assert result["signatories"][key]["state"] == STATE_ABSENT, key
    summary = result["summary"]
    assert summary["can_save"] is False
    assert summary["status"] == "incomplete"
    assert set(summary["missing_signatures"]) == {"Requested By", "Funds Available", "Approved By"}


def test_name_present_but_no_signature_is_still_absent(tmp_path):
    # The PDF always prints the names; only the strokes differ. Critical case.
    pdf = tmp_path / "names_only.pdf"
    _build_pr_pdf(pdf, signed={})
    result = analyze(pdf, names={REQUESTED_BY: "JUAN CRUZ"})
    assert result["signatories"][REQUESTED_BY]["state"] == STATE_ABSENT
    assert result["signatories"][REQUESTED_BY]["name"] == "JUAN CRUZ"


def test_fully_signed_pr_can_save(tmp_path):
    pdf = tmp_path / "signed.pdf"
    _build_pr_pdf(pdf, signed={REQUESTED_BY: True, FUNDS_AVAILABLE: True, APPROVED_BY: True})
    result = analyze(pdf)

    for key in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY):
        assert result["signatories"][key]["state"] == STATE_PRESENT, key
    assert result["summary"]["can_save"] is True
    assert result["summary"]["status"] == "complete"


def test_partially_signed_pr_names_the_missing_one(tmp_path):
    pdf = tmp_path / "partial.pdf"
    _build_pr_pdf(pdf, signed={REQUESTED_BY: True, APPROVED_BY: True})
    result = analyze(pdf)

    assert result["signatories"][REQUESTED_BY]["state"] == STATE_PRESENT
    assert result["signatories"][APPROVED_BY]["state"] == STATE_PRESENT
    assert result["signatories"][FUNDS_AVAILABLE]["state"] == STATE_ABSENT
    assert result["summary"]["can_save"] is False
    assert result["summary"]["missing_signatures"] == ["Funds Available"]


def test_twg_missing_signature_does_not_block_save(tmp_path):
    pdf = tmp_path / "no_twg.pdf"
    _build_pr_pdf(pdf, signed={REQUESTED_BY: True, FUNDS_AVAILABLE: True, APPROVED_BY: True})
    result = analyze(pdf)
    assert result["signatories"][TWG]["state"] == STATE_ABSENT
    assert result["signatories"][TWG]["required"] is False
    assert result["summary"]["can_save"] is True


def test_faint_or_small_marks_still_count_as_signed(tmp_path):
    # The detector only cares that *something* was written, not that it looks
    # like a full signature - a faint squiggle and short initials both pass.
    pdf = tmp_path / "light.pdf"
    _build_pr_pdf(
        pdf,
        signed={REQUESTED_BY: "faint", FUNDS_AVAILABLE: "initials", APPROVED_BY: True},
    )
    result = analyze(pdf)

    for key in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY):
        assert result["signatories"][key]["state"] == STATE_PRESENT, key
    assert result["summary"]["can_save"] is True
    assert result["summary"]["missing_signatures"] == []


def test_identical_small_marks_in_every_slot_all_pass(tmp_path):
    # Mirrors a real CTU PR: the same short cursive mark drawn on every ruled
    # line. All required areas (and the TWG one) must read as signed.
    pdf = tmp_path / "all_small.pdf"
    _build_pr_pdf(
        pdf,
        signed={
            REQUESTED_BY: "initials",
            FUNDS_AVAILABLE: "initials",
            APPROVED_BY: "initials",
            TWG: "initials",
        },
    )
    result = analyze(pdf)

    for key in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY, TWG):
        assert result["signatories"][key]["state"] == STATE_PRESENT, key
    assert result["summary"]["can_save"] is True
    assert result["summary"]["required_detected"] == 3


def test_reanalyze_uses_stored_regions_without_reocr(tmp_path):
    pdf = tmp_path / "signed.pdf"
    _build_pr_pdf(pdf, signed={REQUESTED_BY: True, FUNDS_AVAILABLE: True, APPROVED_BY: True})
    first = analyze(pdf)
    again = reanalyze(pdf, first["regions"])
    assert again["summary"]["can_save"] is True
    assert again["signatories"][REQUESTED_BY]["state"] == STATE_PRESENT


def test_missing_document_is_unverifiable_not_signed(tmp_path):
    result = analyze(tmp_path / "does-not-exist.pdf")
    assert result["summary"]["can_save"] is False
    for key in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY):
        assert result["signatories"][key]["state"] != STATE_PRESENT


# ---------------------------------------------------------------------------
# Regression: printed "Signature :" label leaking past the mask
# ---------------------------------------------------------------------------
# _text_masks() used to blank a printed label like "Signature :" by taking a
# fixed fraction (30%, capped at 11% of the page) of the *recognised line's*
# own measured width. That coincidentally covered the label when the line
# also carried a long run of underscore characters (the label is then a small
# share of a wide line), but drastically under-masked a line that is only the
# label itself - real printed letters were left with genuine ink density,
# vertical stroke structure and multiple connected components, which is
# exactly what the ink classifier accepts as a handwritten mark. See
# `_build_pr_pdf_isolated_labels` above for the layout shape that exposes it.
def test_isolated_narrow_signature_label_is_not_mistaken_for_a_mark(tmp_path):
    pdf = tmp_path / "isolated_unsigned.pdf"
    _build_pr_pdf_isolated_labels(pdf, signed={})
    result = analyze(pdf)

    for key in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY, TWG):
        assert result["signatories"][key]["state"] == STATE_ABSENT, key
    assert result["summary"]["can_save"] is False
    assert set(result["summary"]["missing_signatures"]) == {
        "Requested By", "Funds Available", "Approved By",
    }


def test_isolated_narrow_signature_label_still_detects_real_marks(tmp_path):
    # The fix must not make the classifier blind in the other direction -
    # a genuine mark next to an isolated label must still read as signed.
    pdf = tmp_path / "isolated_signed.pdf"
    _build_pr_pdf_isolated_labels(
        pdf,
        signed={REQUESTED_BY: True, FUNDS_AVAILABLE: True, APPROVED_BY: True, TWG: True},
    )
    result = analyze(pdf)

    for key in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY, TWG):
        assert result["signatories"][key]["state"] == STATE_PRESENT, key
    assert result["summary"]["can_save"] is True


def test_isolated_narrow_signature_label_partial_signing_still_precise(tmp_path):
    # Only TWG is blank (mirrors the exact bug report: the three required
    # signatories were signed and correctly read; TWG was blank and
    # misread). Confirms the fix is precise, not just "always absent".
    pdf = tmp_path / "isolated_partial.pdf"
    _build_pr_pdf_isolated_labels(
        pdf,
        signed={REQUESTED_BY: True, FUNDS_AVAILABLE: True, APPROVED_BY: True},
    )
    result = analyze(pdf)

    for key in (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY):
        assert result["signatories"][key]["state"] == STATE_PRESENT, key
    assert result["signatories"][TWG]["state"] == STATE_ABSENT
    assert result["summary"]["can_save"] is True


# ---------------------------------------------------------------------------
# Regression: unit-level coverage of the mask geometry itself
# ---------------------------------------------------------------------------
def test_char_label_extent_covers_the_whole_printed_label():
    from ocr.signature_detection import TextLine, _char_label_extent

    # "Signature :" as its own isolated line - each tuple is (char, x0, x1)
    # in normalized page coordinates, evenly spaced for simplicity.
    label = "Signature :"
    step = 0.01
    char_boxes = [(ch, i * step, (i + 1) * step) for i, ch in enumerate(label)]
    line = TextLine(text=label, page=1, x0=0.0, y0=0.0, x1=len(label) * step, y1=0.02, char_boxes=char_boxes)

    end_x1 = _char_label_extent(line)
    # Must reach (at least) the end of "Signature", and cover the colon too.
    assert end_x1 == char_boxes[label.index(":")][2]
    assert end_x1 >= char_boxes[len("Signature") - 1][2]


def test_char_label_extent_handles_label_without_colon():
    from ocr.signature_detection import TextLine, _char_label_extent

    label = "Signature"
    step = 0.01
    char_boxes = [(ch, i * step, (i + 1) * step) for i, ch in enumerate(label)]
    line = TextLine(text=label, page=1, x0=0.0, y0=0.0, x1=len(label) * step, y1=0.02, char_boxes=char_boxes)

    end_x1 = _char_label_extent(line)
    assert end_x1 == char_boxes[-1][2]


def test_char_label_extent_returns_none_without_char_geometry():
    from ocr.signature_detection import TextLine, _char_label_extent

    line = TextLine(text="Signature :", page=1, x0=0.0, y0=0.0, x1=0.1, y1=0.02)
    assert _char_label_extent(line) is None


def test_word_label_extent_prefers_textract_word_boxes():
    from ocr.signature_detection import TextLine, _word_label_extent

    line = TextLine(text="Signature :", page=1, x0=0.10, y0=0.20, x1=0.30, y1=0.22)
    words = [
        TextLine(text="Signature", page=1, x0=0.10, y0=0.20, x1=0.16, y1=0.22),
        TextLine(text=":", page=1, x0=0.165, y0=0.20, x1=0.17, y1=0.22),
    ]
    assert _word_label_extent(words, line) == 0.17


def test_text_masks_do_not_under_mask_a_narrow_label_line():
    from ocr.signature_detection import TextLine, _text_masks

    label = "Signature :"
    step = 0.01
    char_boxes = [(ch, i * step, (i + 1) * step) for i, ch in enumerate(label)]
    line = TextLine(
        text=label, page=1, x0=0.0, y0=0.10, x1=len(label) * step, y1=0.12, char_boxes=char_boxes,
    )

    masks = _text_masks([line], page=1, band_top=0.09, band_bottom=0.13)
    assert len(masks) == 1
    mask_x0, _, mask_x1, _ = masks[0]
    # The old fixed-fraction formula would stop at 30% of the line's own
    # width (~0.033 here) - well short of the label. The fix must cover it.
    assert mask_x1 >= char_boxes[label.index(":")][2]
    assert mask_x1 > 0.30 * line.x1  # sanity: meaningfully more than the old cap

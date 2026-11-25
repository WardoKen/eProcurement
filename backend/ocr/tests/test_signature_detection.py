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

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from ocr.signature_detection import (  # noqa: E402
    APPROVED_BY,
    FUNDS_AVAILABLE,
    REQUESTED_BY,
    STATE_ABSENT,
    STATE_PRESENT,
    STATE_UNCERTAIN,
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

    def tall_loop(cx: float, baseline: float) -> None:
        # A big looped capital rising well above the rule, then a short tail.
        c.setLineWidth(1.4)
        p = c.beginPath()
        p.moveTo(cx, baseline - 2)
        p.curveTo(cx + 26, baseline + 6, cx + 30, baseline + 30, cx + 16, baseline + 30)
        p.curveTo(cx + 2, baseline + 30, cx + 6, baseline + 4, cx + 22, baseline - 3)
        p.lineTo(cx + 60, baseline + 2)
        c.drawPath(p, stroke=1, fill=0)
        c.setLineWidth(1)

    def crossing(cx: float, baseline: float) -> None:
        # Steep strokes that cross the ruled line several times.
        c.setLineWidth(1.3)
        p = c.beginPath()
        p.moveTo(cx, baseline + 12)
        for i in range(1, 9):
            p.lineTo(cx + i * 8.0, baseline + (12 if i % 2 == 0 else -14))
        c.drawPath(p, stroke=1, fill=0)
        c.setLineWidth(1)

    def mark(key: str, cx: float, baseline: float) -> None:
        spec = signed.get(key)
        if not spec:
            return
        if spec == "faint":
            scribble(cx, baseline, width=0.4, span=42.0, amp=7.0)
        elif spec == "initials":
            scribble(cx, baseline, width=1.2, span=22.0, amp=12.0)
        elif spec == "pencil":
            c.setStrokeGray(0.62)  # light graphite, well short of black
            scribble(cx, baseline, width=0.6, span=70.0, amp=10.0)
            c.setStrokeGray(0)
        elif spec == "marker":
            scribble(cx, baseline, width=4.0, span=80.0, amp=12.0)
        elif spec == "loop":
            tall_loop(cx, baseline)
        elif spec == "crossing":
            crossing(cx, baseline)
        elif spec == "long":
            # Runs 230pt from its own label - past the next column's label.
            scribble(cx, baseline, span=230.0, amp=12.0)
        elif spec == "leaning":
            # Starts 30pt left of its own label, over the neighbour's column.
            scribble(cx - 30.0, baseline, span=110.0, amp=12.0)
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


# ===========================================================================
# Real CTU Purchase Request fixtures (Appendix 60 layout)
# ===========================================================================
# Purchase-Requests-TETETETTEST-2026.pdf is a digital PR with a text layer.
# "Scanned Purchase Request.pdf" is a scan of the same signed form - image
# only, so the detector depends on OCR geometry. scan_textract.json is the
# Textract response the app received for that scan (the production path),
# kept so this test needs neither AWS nor Tesseract and always runs.
import itertools  # noqa: E402
import json  # noqa: E402

from scan_helpers import degrade_to_scan, textract_blocks_for  # noqa: E402

FIXTURES = TESTS_DIR / "fixtures"
DIGITAL_PR = FIXTURES / "Purchase-Requests-TETETETTEST-2026.pdf"
SCANNED_PR = FIXTURES / "Scanned Purchase Request.pdf"
SCANNED_TEXTRACT = FIXTURES / "scan_textract.json"
REQUIRED = (REQUESTED_BY, FUNDS_AVAILABLE, APPROVED_BY)
ALL_FOUR = REQUIRED + (TWG,)


def _scan_blocks():
    return json.loads(SCANNED_TEXTRACT.read_text(encoding="utf-8"))["Blocks"]


def _assert_all_present(result):
    for key in ALL_FOUR:
        info = result["signatories"][key]
        assert info["state"] == STATE_PRESENT, (key, info.get("reason"), info.get("metrics"))
        # A clear pass, not a fallback of any kind.
        assert "reason" not in info, (key, info.get("reason"))
    assert result["summary"]["can_save"] is True
    assert result["summary"]["needs_confirmation"] is False


def test_digital_fixture_all_four_signatures_present():
    _assert_all_present(analyze(DIGITAL_PR))


def test_scanned_fixture_all_four_signatures_present_with_textract_geometry():
    _assert_all_present(analyze(SCANNED_PR, _scan_blocks()))


def test_scanned_fixture_recheck_from_stored_regions_matches():
    first = analyze(SCANNED_PR, _scan_blocks())
    _assert_all_present(reanalyze(SCANNED_PR, first["regions"]))


def test_scanned_fixture_masks_never_cover_the_signatures():
    # Textract reads each signature as a word ("fl"/"ft"). Before the fix every
    # recognised word was masked, which erased the signatures themselves.
    regions = analyze(SCANNED_PR, _scan_blocks())["regions"]
    signature_words = [
        b for b in _scan_blocks()
        if b["BlockType"] == "WORD" and b.get("TextType") == "HANDWRITING"
    ]
    assert len(signature_words) == 4
    for word in signature_words:
        box = word["Geometry"]["BoundingBox"]
        cx, cy = box["Left"] + box["Width"] / 2, box["Top"] + box["Height"] / 2
        for region in regions.values():
            for mx0, my0, mx1, my1 in region["masks"]:
                assert not (mx0 <= cx <= mx1 and my0 <= cy <= my1), (word["Text"], region)


def test_signature_word_tagged_printed_still_counts():
    # Textract can mislabel a signature as PRINTED. Masks follow what the form
    # is expected to print, never TextType, so the signature must still count.
    blocks = _scan_blocks()
    for block in blocks:
        if block.get("TextType") == "HANDWRITING":
            block["TextType"] = "PRINTED"
    _assert_all_present(analyze(SCANNED_PR, blocks))


def test_scanned_fixture_without_geometry_asks_for_confirmation():
    # Textract failed: no text layer, no OCR boxes. Nothing is guessed.
    result = analyze(SCANNED_PR, None)
    for key in ALL_FOUR:
        info = result["signatories"][key]
        assert info["state"] == STATE_UNCERTAIN
        assert info["reason"] == "no_ocr_geometry"
    summary = result["summary"]
    assert summary["can_save"] is False
    assert summary["needs_confirmation"] is True
    assert summary["uncertain_keys"] == list(REQUIRED)


# ===========================================================================
# Masking rules and states (unit level)
# ===========================================================================
def test_word_masks_cover_expected_printed_text_only():
    from ocr.signature_detection import TextLine, _word_masks

    row = TextLine(text="Printed Name : JUAN CRUZ", page=1, x0=0.10, y0=0.50, x1=0.40, y1=0.51)
    words = [
        TextLine(text="Signature", page=1, x0=0.10, y0=0.48, x1=0.16, y1=0.49, text_type="PRINTED"),
        TextLine(text=":", page=1, x0=0.161, y0=0.48, x1=0.164, y1=0.49, text_type="PRINTED"),
        # The signature, read as text and wrongly tagged PRINTED.
        TextLine(text="fl", page=1, x0=0.25, y0=0.47, x1=0.30, y1=0.495, text_type="PRINTED"),
        # A signature tagged HANDWRITING.
        TextLine(text="Sb", page=1, x0=0.55, y0=0.47, x1=0.60, y1=0.495, text_type="HANDWRITING"),
        # Printed name the extractor returned, and one it garbled (on the row).
        TextLine(text="JUAN", page=1, x0=0.20, y0=0.50, x1=0.24, y1=0.51, text_type="PRINTED"),
        TextLine(text="CRU2", page=1, x0=0.25, y0=0.50, x1=0.29, y1=0.51, text_type="PRINTED"),
    ]
    masks, handwriting = _word_masks(
        words, [row], page=1, band_top=0.47, band_bottom=0.50,
        printed_terms=frozenset({"juan"}),
    )
    masked = {(m[0], m[1]) for m in masks}
    assert (0.10, 0.48) in masked      # label word
    assert (0.161, 0.48) in masked     # its colon
    assert (0.20, 0.50) in masked      # extracted printed name
    assert (0.25, 0.50) in masked      # garbled name on the Printed Name row
    assert (0.25, 0.47) not in masked  # signature tagged PRINTED - kept
    assert (0.55, 0.47) not in masked  # signature tagged HANDWRITING - kept
    assert handwriting == [(0.55, 0.47, 0.60, 0.495)]


def test_handwriting_word_with_weak_ink_is_uncertain_not_present(tmp_path):
    # OCR claims handwriting in the Funds box, but the box has no ink: the OCR
    # label alone must never pass a signature.
    clean = tmp_path / "blank.pdf"
    _build_pr_pdf(clean, signed={REQUESTED_BY: True, APPROVED_BY: True})
    scan = tmp_path / "blank-scan.pdf"
    size = degrade_to_scan(clean, scan, angle_deg=0.6)
    ghost = ("fl", (270 / PAGE_W, 1 - 190 / PAGE_H, 300 / PAGE_W, 1 - 176 / PAGE_H), "HANDWRITING")
    blocks = textract_blocks_for(clean, angle_deg=0.6, size=size, extra_words=[ghost])
    result = analyze(scan, blocks)
    funds = result["signatories"][FUNDS_AVAILABLE]
    assert funds["state"] == STATE_UNCERTAIN
    assert funds["reason"] == "handwriting_weak_ink"
    assert result["summary"]["can_save"] is False


def test_ambiguous_ink_is_uncertain_not_a_silent_pass():
    # Replaces the old "lenient_mark" pass: a short upright tick that is more
    # than speckle but not a confident stroke has to be confirmed by a person.
    import numpy as np
    from ocr.signature_detection import _classify_region

    gray = np.full((1000, 1000), 255, dtype=np.uint8)
    gray[420:470, 300:303] = 0  # 3px x 50px tick inside a 300x80 band
    region = Region(page=1, x0=0.2, y0=0.4, x1=0.5, y1=0.48)
    result = _classify_region(gray, region)
    assert result["state"] == STATE_UNCERTAIN
    assert result["reason"] == "ambiguous_ink"


def test_summary_states():
    from ocr.signature_detection import _summarise

    def summary(*states):
        return _summarise({key: {"state": state} for key, state in zip(REQUIRED, states)})

    assert summary("present", "present", "present")["can_save"] is True
    needs = summary("present", "uncertain", "present")
    assert needs["can_save"] is False and needs["needs_confirmation"] is True
    assert needs["uncertain_keys"] == [FUNDS_AVAILABLE]
    assert needs["status"] == "needs_confirmation"
    # A blank box can never be confirmed away.
    blank = summary("absent", "uncertain", "present")
    assert blank["needs_confirmation"] is False and blank["status"] == "incomplete"
    assert blank["missing_keys"] == [REQUESTED_BY]


def test_summary_unverifiable_goes_to_the_bac():
    from ocr.signature_detection import _summarise

    def summary(*states):
        return _summarise({key: {"state": state} for key, state in zip(REQUIRED, states)})

    unread = summary("present", "unverifiable", "present")
    assert unread["can_save"] is False
    assert unread["needs_bac_verification"] is True
    assert unread["unverifiable_keys"] == [FUNDS_AVAILABLE]
    assert unread["status"] == "unverifiable"
    assert "BAC" in unread["message"]
    # Uncertain + unverifiable: the submitter still confirms the uncertain box.
    mixed = summary("uncertain", "unverifiable", "present")
    assert mixed["needs_confirmation"] is True and mixed["needs_bac_verification"] is True
    assert mixed["status"] == "needs_confirmation"
    # A blank box blocks regardless.
    blank = summary("absent", "unverifiable", "present")
    assert blank["needs_bac_verification"] is False and blank["status"] == "incomplete"


# ===========================================================================
# Ground truth on synthetic forms - digital and scanned
# ===========================================================================
# Every case runs twice: on the clean digital PDF (pdfminer geometry) and on a
# scanned copy - gray paper, noise, dust, a 1 degree tilt, no text layer, with
# Textract-shaped word boxes (see scan_helpers.py).
def _analyze_both(tmp_path, signed, *, angle_deg=1.0, name="pr"):
    clean = tmp_path / f"{name}.pdf"
    _build_pr_pdf(clean, signed=signed)
    scan = tmp_path / f"{name}-scan.pdf"
    size = degrade_to_scan(clean, scan, angle_deg=angle_deg)
    blocks = textract_blocks_for(clean, angle_deg=angle_deg, size=size)
    return {"digital": analyze(clean), "scanned": analyze(scan, blocks)}


def _check_ground_truth(results, signed):
    for version, result in results.items():
        for key in ALL_FOUR:
            info = result["signatories"][key]
            if signed.get(key):
                assert info["state"] == STATE_PRESENT, (version, key, info)
            else:
                # The rule that matters most: a blank box is never "present".
                assert info["state"] != STATE_PRESENT, (version, key, info)
                assert info["state"] == STATE_ABSENT, (version, key, info)
        all_signed = all(signed.get(key) for key in REQUIRED)
        assert result["summary"]["can_save"] is all_signed, version


COMBINATIONS = [dict(zip(REQUIRED, combo)) for combo in itertools.product([False, True], repeat=3)]


@pytest.mark.parametrize(
    "signed", COMBINATIONS,
    ids=["".join("S" if combo[k] else "-" for k in REQUIRED) for combo in COMBINATIONS],
)
def test_every_signed_blank_combination_matches_ground_truth(tmp_path, signed):
    _check_ground_truth(_analyze_both(tmp_path, signed), signed)


@pytest.mark.parametrize("style", ["initials", "faint", "pencil", "marker", "loop", "crossing"])
def test_writing_styles_are_present(tmp_path, style):
    signed = {key: style for key in ALL_FOUR}
    _check_ground_truth(_analyze_both(tmp_path, signed), signed)


def test_long_signature_overhanging_into_a_blank_column_is_not_counted(tmp_path):
    # Requested-by's signature runs 230pt - past the Funds Available label -
    # while the Funds box itself is blank.
    signed = {REQUESTED_BY: "long", APPROVED_BY: True}
    _check_ground_truth(_analyze_both(tmp_path, signed), signed)


def test_signature_leaning_into_a_blank_column_is_not_counted(tmp_path):
    # Approved-by's signature starts 30pt left of its own label, over the blank
    # Funds box.
    signed = {REQUESTED_BY: True, APPROVED_BY: "leaning"}
    _check_ground_truth(_analyze_both(tmp_path, signed), signed)


@pytest.mark.parametrize("angle_deg", [-2.0, 2.0])
@pytest.mark.parametrize("signed", [
    {},
    {REQUESTED_BY: True, APPROVED_BY: True},
    {REQUESTED_BY: True, FUNDS_AVAILABLE: True, APPROVED_BY: True, TWG: True},
], ids=["blank", "funds-missing", "all-signed"])
def test_tilted_scans(tmp_path, signed, angle_deg):
    _check_ground_truth(_analyze_both(tmp_path, signed, angle_deg=angle_deg), signed)

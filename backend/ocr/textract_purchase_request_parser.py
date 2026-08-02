from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from .debug_utils import get_parser_logger, write_debug_json
except ImportError:  # pragma: no cover
    from backend.ocr.debug_utils import get_parser_logger, write_debug_json

logger = get_parser_logger()

LOW_CONFIDENCE_THRESHOLD = 85.0


def is_effectively_blank(value: str) -> bool:
    cleaned = normalize_space(value)
    if not cleaned:
        return True
    # Treat separator-only OCR artifacts as blank values.
    return bool(re.fullmatch(r"[:\-_/\\|.\s]+", cleaned))


@dataclass
class ParsedField:
    value: str
    confidence: float
    needs_review: bool
    block_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
            "block_id": self.block_id,
        }


@dataclass
class ParsedItem:
    stock_no: str
    unit: str
    description: str
    quantity: float | int | str
    unit_cost: float | int | str
    total_cost: float | int | str
    confidence: float
    needs_review: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stock_no": self.stock_no,
            "unit": self.unit,
            "description": self.description,
            "quantity": self.quantity,
            "unit_cost": self.unit_cost,
            "total_cost": self.total_cost,
            "confidence": round(self.confidence, 2),
            "needs_review": self.needs_review,
        }


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_label(value: str) -> str:
    lowered = normalize_space(value).lower()
    lowered = lowered.replace("/", " ")
    lowered = re.sub(r"[^a-z0-9 ]", "", lowered)
    tokens = normalize_space(lowered).split(" ")
    merged_tokens: List[str] = []
    i = 0
    while i < len(tokens):
        if len(tokens[i]) == 1:
            chunk = [tokens[i]]
            j = i + 1
            while j < len(tokens) and len(tokens[j]) == 1:
                chunk.append(tokens[j])
                j += 1
            merged_tokens.append("".join(chunk))
            i = j
            continue
        merged_tokens.append(tokens[i])
        i += 1
    return normalize_space(" ".join(merged_tokens))


def safe_float(value: str) -> Optional[float]:
    cleaned = re.sub(r"[^0-9.,-]", "", value or "")
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def is_low_confidence(confidence: float) -> bool:
    return confidence < LOW_CONFIDENCE_THRESHOLD


def index_blocks(blocks: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {block.get("Id"): block for block in blocks if block.get("Id")}


def relationship_ids(block: Dict[str, Any], rel_type: str) -> List[str]:
    ids: List[str] = []
    for relation in block.get("Relationships", []) or []:
        if relation.get("Type") == rel_type:
            ids.extend(relation.get("Ids", []) or [])
    return ids


def extract_text_from_block(block: Dict[str, Any], block_map: Dict[str, Dict[str, Any]]) -> Tuple[str, float]:
    if not block:
        return "", 0.0

    block_type = block.get("BlockType")
    if block_type == "WORD":
        text = normalize_space(str(block.get("Text") or ""))
        confidence = float(block.get("Confidence") or 0.0)
        return text, confidence

    if block_type == "SELECTION_ELEMENT":
        status = block.get("SelectionStatus")
        text = "X" if status == "SELECTED" else ""
        confidence = float(block.get("Confidence") or 0.0)
        return text, confidence

    child_ids = relationship_ids(block, "CHILD")
    texts: List[str] = []
    confidences: List[float] = []
    for child_id in child_ids:
        child = block_map.get(child_id)
        if not child:
            continue
        child_type = child.get("BlockType")
        if child_type not in {"WORD", "SELECTION_ELEMENT"}:
            continue
        text, conf = extract_text_from_block(child, block_map)
        if text:
            texts.append(text)
        if conf:
            confidences.append(conf)

    merged_text = normalize_space(" ".join(texts))
    avg_conf = mean(confidences) if confidences else float(block.get("Confidence") or 0.0)
    return merged_text, float(avg_conf)


def build_line_index(blocks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lines = [block for block in blocks if block.get("BlockType") == "LINE"]
    lines.sort(
        key=lambda block: (
            int(block.get("Page", 1) or 1),
            float(((block.get("Geometry") or {}).get("BoundingBox") or {}).get("Top") or 0.0),
            float(((block.get("Geometry") or {}).get("BoundingBox") or {}).get("Left") or 0.0),
        )
    )
    return lines


def parse_key_value_sets(blocks: List[Dict[str, Any]]) -> Dict[str, ParsedField]:
    """Parse KEY_VALUE_SET relationships into normalized key -> ParsedField."""
    block_map = index_blocks(blocks)
    kv_fields: Dict[str, ParsedField] = {}

    key_blocks = [
        block
        for block in blocks
        if block.get("BlockType") == "KEY_VALUE_SET"
        and "KEY" in (block.get("EntityTypes") or [])
    ]

    for key_block in key_blocks:
        key_text, key_conf = extract_text_from_block(key_block, block_map)
        if not key_text:
            continue

        value_texts: List[str] = []
        value_confidences: List[float] = []
        for value_id in relationship_ids(key_block, "VALUE"):
            value_block = block_map.get(value_id)
            if not value_block:
                continue
            value_text, value_conf = extract_text_from_block(value_block, block_map)
            if value_text:
                value_texts.append(value_text)
            if value_conf:
                value_confidences.append(value_conf)

        value = normalize_space(" ".join(value_texts))
        confidence = mean(value_confidences) if value_confidences else key_conf
        norm_key = normalize_label(key_text)

        if norm_key and value and not is_effectively_blank(value):
            kv_fields[norm_key] = ParsedField(
                value=value,
                confidence=float(confidence),
                needs_review=is_low_confidence(float(confidence)),
                block_id=str(key_block.get("Id") or ""),
            )

            logger.info(
                "FIELD %s | value=%s | confidence=%.2f | block_id=%s",
                key_text,
                value,
                float(confidence),
                str(key_block.get("Id") or ""),
            )

    logger.info("Textract KV parsed: %s keys", len(kv_fields))
    write_debug_json(
        "form_fields.json",
        {
            key: {
                "value": field.value,
                "confidence": field.confidence,
                "needs_review": field.needs_review,
                "block_id": field.block_id,
            }
            for key, field in kv_fields.items()
        },
    )
    return kv_fields


def extract_cells(table_block: Dict[str, Any], block_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract CELL blocks from one TABLE and apply MERGED_CELL text when present."""
    child_ids = relationship_ids(table_block, "CHILD")
    cell_ids: List[str] = []
    merged_cell_ids: List[str] = []

    for child_id in child_ids:
        child = block_map.get(child_id)
        if not child:
            continue
        block_type = child.get("BlockType")
        if block_type == "CELL":
            cell_ids.append(child_id)
        elif block_type == "MERGED_CELL":
            merged_cell_ids.append(child_id)

    merged_map: Dict[str, Tuple[str, float]] = {}
    for merged_id in merged_cell_ids:
        merged_block = block_map.get(merged_id)
        if not merged_block:
            continue
        merged_text, merged_conf = extract_text_from_block(merged_block, block_map)
        if not merged_text:
            continue
        for merged_child_id in relationship_ids(merged_block, "CHILD"):
            merged_map[merged_child_id] = (merged_text, float(merged_conf))

    cells: List[Dict[str, Any]] = []
    for cell_id in cell_ids:
        cell = block_map.get(cell_id)
        if not cell:
            continue
        text, confidence = extract_text_from_block(cell, block_map)
        if not text and cell_id in merged_map:
            text, confidence = merged_map[cell_id]

        cells.append(
            {
                "id": cell_id,
                "row_index": int(cell.get("RowIndex", 0) or 0),
                "column_index": int(cell.get("ColumnIndex", 0) or 0),
                "row_span": int(cell.get("RowSpan", 1) or 1),
                "column_span": int(cell.get("ColumnSpan", 1) or 1),
                "text": normalize_space(text),
                "confidence": float(confidence or cell.get("Confidence") or 0.0),
                "entity_types": list(cell.get("EntityTypes") or []),
            }
        )

    return cells


def reconstruct_table_rows(cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reconstruct ordered table rows from CELL records."""
    rows: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        row_idx = int(cell.get("row_index", 0) or 0)
        if row_idx <= 0:
            continue
        rows[row_idx].append(cell)

    ordered_rows: List[Dict[str, Any]] = []
    for row_idx in sorted(rows.keys()):
        row_cells = sorted(rows[row_idx], key=lambda item: int(item.get("column_index", 0) or 0))
        row_conf = mean([float(cell.get("confidence") or 0.0) for cell in row_cells]) if row_cells else 0.0
        ordered_rows.append(
            {
                "row_index": row_idx,
                "cells": row_cells,
                "confidence": float(row_conf),
            }
        )
    return ordered_rows


def find_header_map(row: Dict[str, Any]) -> Dict[str, int]:
    aliases = {
        "stock_no": {"stock property no", "stock no", "stock property number"},
        "unit": {"unit"},
        "description": {"item description", "description"},
        "quantity": {"quantity", "qty"},
        "unit_cost": {"unit cost"},
        "total_cost": {"total cost", "amount"},
    }

    header_map: Dict[str, int] = {}
    for cell in row.get("cells", []):
        label = normalize_label(str(cell.get("text") or ""))
        for target, names in aliases.items():
            if label in names:
                header_map[target] = int(cell.get("column_index", 0) or 0)
    return header_map


def get_cell_value(row: Dict[str, Any], column_index: int) -> Tuple[str, float]:
    for cell in row.get("cells", []):
        if int(cell.get("column_index", 0) or 0) == column_index:
            return normalize_space(str(cell.get("text") or "")), float(cell.get("confidence") or 0.0)
    return "", 0.0


def parse_item_row(row: Dict[str, Any], header_map: Dict[str, int]) -> Optional[ParsedItem]:
    description, description_conf = get_cell_value(row, header_map.get("description", -1))
    if not description:
        return None

    stock_no, stock_conf = get_cell_value(row, header_map.get("stock_no", -1))
    unit, unit_conf = get_cell_value(row, header_map.get("unit", -1))
    quantity_raw, qty_conf = get_cell_value(row, header_map.get("quantity", -1))
    unit_cost_raw, unit_cost_conf = get_cell_value(row, header_map.get("unit_cost", -1))
    total_cost_raw, total_cost_conf = get_cell_value(row, header_map.get("total_cost", -1))

    quantity_num = safe_float(quantity_raw)
    unit_cost_num = safe_float(unit_cost_raw)
    total_cost_num = safe_float(total_cost_raw)

    row_confidence_parts = [
        conf
        for conf in [description_conf, stock_conf, unit_conf, qty_conf, unit_cost_conf, total_cost_conf]
        if conf > 0
    ]
    row_conf = mean(row_confidence_parts) if row_confidence_parts else float(row.get("confidence") or 0.0)

    if quantity_raw and quantity_num is None:
        logger.warning("VALIDATION quantity not numeric | row=%s | value=%s", row.get("row_index"), quantity_raw)
    if unit_cost_raw and unit_cost_num is None:
        logger.warning("VALIDATION unit_cost not numeric | row=%s | value=%s", row.get("row_index"), unit_cost_raw)
    if total_cost_raw and total_cost_num is None:
        logger.warning("VALIDATION total_cost not numeric | row=%s | value=%s", row.get("row_index"), total_cost_raw)
    if not description:
        logger.warning("VALIDATION description is empty | row=%s", row.get("row_index"))

    return ParsedItem(
        stock_no=stock_no,
        unit=unit,
        description=description,
        quantity=int(quantity_num) if quantity_num is not None and quantity_num.is_integer() else (quantity_num if quantity_num is not None else quantity_raw),
        unit_cost=unit_cost_num if unit_cost_num is not None else unit_cost_raw,
        total_cost=total_cost_num if total_cost_num is not None else total_cost_raw,
        confidence=float(row_conf),
        needs_review=is_low_confidence(float(row_conf)),
    )


def parse_tables(blocks: List[Dict[str, Any]]) -> Tuple[List[ParsedItem], List[Dict[str, Any]]]:
    """Parse TABLE/CELL/MERGED_CELL into line items and table diagnostics."""
    block_map = index_blocks(blocks)
    table_blocks = [block for block in blocks if block.get("BlockType") == "TABLE"]
    table_blocks.sort(
        key=lambda block: (
            int(block.get("Page", 1) or 1),
            float(((block.get("Geometry") or {}).get("BoundingBox") or {}).get("Top") or 0.0),
        )
    )

    parsed_items: List[ParsedItem] = []
    table_info: List[Dict[str, Any]] = []
    debug_rows: List[Dict[str, Any]] = []

    for table_idx, table_block in enumerate(table_blocks, start=1):
        logger.info(
            "TABLE %s detected | page=%s | block_id=%s",
            table_idx,
            int(table_block.get("Page", 1) or 1),
            str(table_block.get("Id") or ""),
        )
        cells = extract_cells(table_block, block_map)
        rows = reconstruct_table_rows(cells)

        header_map: Dict[str, int] = {}
        header_row_index = 0
        for row in rows:
            candidate_map = find_header_map(row)
            if "description" in candidate_map and ("quantity" in candidate_map or "unit_cost" in candidate_map):
                header_map = candidate_map
                header_row_index = int(row.get("row_index", 0) or 0)
                break

        row_count = 0
        if header_map:
            for row in rows:
                logger.info("TABLE %s ROW %s", table_idx, row.get("row_index"))
                for cell in row.get("cells", []):
                    logger.info(
                        "TABLE %s ROW %s COLUMN %s | text=%s | confidence=%.2f | cell_id=%s",
                        table_idx,
                        row.get("row_index"),
                        cell.get("column_index"),
                        cell.get("text", ""),
                        float(cell.get("confidence") or 0.0),
                        cell.get("id", ""),
                    )

                if int(row.get("row_index", 0) or 0) <= header_row_index:
                    continue
                item = parse_item_row(row, header_map)
                if item is None:
                    continue
                parsed_items.append(item)
                row_count += 1
                debug_rows.append(
                    {
                        "row_index": row.get("row_index"),
                        "stock_no": item.stock_no,
                        "unit": item.unit,
                        "description": item.description,
                        "quantity": item.quantity,
                        "unit_cost": item.unit_cost,
                        "total_cost": item.total_cost,
                        "confidence": {
                            "row": round(item.confidence, 2),
                            "needs_review": item.needs_review,
                        },
                    }
                )

        table_info.append(
            {
                "table_index": table_idx,
                "page": int(table_block.get("Page", 1) or 1),
                "rows": len(rows),
                "parsed_item_rows": row_count,
                "header_map": header_map,
            }
        )

    logger.info("Textract tables detected: %s, parsed item rows: %s", len(table_blocks), len(parsed_items))
    write_debug_json("table_rows.json", debug_rows)
    return parsed_items, table_info


def match_field(kv_fields: Dict[str, ParsedField], aliases: List[str]) -> Optional[ParsedField]:
    for alias in aliases:
        norm_alias = normalize_label(alias)
        if norm_alias in kv_fields:
            return kv_fields[norm_alias]

    for key, value in kv_fields.items():
        for alias in aliases:
            alias_norm = normalize_label(alias)
            if alias_norm in key or key in alias_norm:
                return value
    return None


def extract_header_fields(kv_fields: Dict[str, ParsedField]) -> Dict[str, ParsedField]:
    """Extract CTU Purchase Request header fields from KEY_VALUE_SET blocks."""
    mapping = {
        "entity_name": ["entity name", "name of entity"],
        "fund_cluster": ["fund cluster"],
        "office": ["office section", "office"],
        "pr_number": ["pr no", "pr number"],
        "date": ["date"],
        "responsibility_center_code": ["responsibility center code", "responsibility center"],
    }

    result: Dict[str, ParsedField] = {}
    for target, aliases in mapping.items():
        matched = match_field(kv_fields, aliases)
        if matched:
            result[target] = matched
        else:
            result[target] = ParsedField(value="", confidence=0.0, needs_review=True)
    return result


def extract_header_fields_from_lines(blocks: List[Dict[str, Any]]) -> Dict[str, ParsedField]:
    """Fallback header extraction from LINE blocks when KEY_VALUE_SET links are incomplete."""
    patterns = {
        "entity_name": [r"entity\s*name\s*[:\-]\s*(.+)$"],
        "fund_cluster": [r"fund\s*cluster\s*[:\-]\s*(.+)$"],
        "office": [r"office\s*/?\s*section\s*[:\-]\s*(.+)$", r"office\s*[:\-]\s*(.+)$"],
        "pr_number": [r"p\.?r\.?\s*(?:no\.?|number)?\s*[:\-]\s*(.+)$"],
        "date": [r"date\s*[:\-]\s*(.+)$"],
        "responsibility_center_code": [r"responsibility\s*center\s*code\s*[:\-]\s*(.+)$"],
    }

    line_blocks = build_line_index(blocks)
    extracted: Dict[str, ParsedField] = {}
    for line in line_blocks:
        text = normalize_space(str(line.get("Text") or ""))
        if not text:
            continue
        for target, regexes in patterns.items():
            if target in extracted and extracted[target].value:
                continue
            for pattern in regexes:
                match = re.search(pattern, text, re.I)
                if not match:
                    continue
                value = normalize_space(match.group(1))
                if not value:
                    continue
                confidence = float(line.get("Confidence") or 0.0)
                extracted[target] = ParsedField(
                    value=value,
                    confidence=confidence,
                    needs_review=True,
                )
                break
    return extracted


def parse_signatories(blocks: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Parse CTU signatories footer using Textract geometry, not table row/column indexes."""

    result = {
        "requested_by": {"printed_name": "", "designation": ""},
        "funds_available": {"printed_name": "", "designation": ""},
        "approved_by": {"printed_name": "", "designation": ""},
    }

    block_map = index_blocks(blocks)

    def bbox(block: Dict[str, Any]) -> Tuple[float, float, float, float]:
        box = ((block.get("Geometry") or {}).get("BoundingBox") or {})
        left = float(box.get("Left") or 0.0)
        top = float(box.get("Top") or 0.0)
        width = float(box.get("Width") or 0.0)
        height = float(box.get("Height") or 0.0)
        return left, top, left + width, top + height

    line_blocks = [block for block in blocks if block.get("BlockType") == "LINE"]

    anchors: Dict[str, Dict[str, float]] = {}
    twg_heading: Optional[Dict[str, float]] = None

    for block in line_blocks:
        text = normalize_space(str(block.get("Text") or ""))
        norm = normalize_label(text)
        left, top, right, bottom = bbox(block)
        page = int(block.get("Page", 1) or 1)

        if "requested by" in norm and "requested_by" not in anchors:
            anchors["requested_by"] = {"page": page, "left": left, "top": top, "right": right, "bottom": bottom}
        if "funds available" in norm and "funds_available" not in anchors:
            anchors["funds_available"] = {"page": page, "left": left, "top": top, "right": right, "bottom": bottom}
        if "approved by" in norm and "approved_by" not in anchors:
            anchors["approved_by"] = {"page": page, "left": left, "top": top, "right": right, "bottom": bottom}
        if (
            "specifications verified by technical working group" in norm
            or norm == "technical working group"
            or "technical working group" in norm
        ) and twg_heading is None:
            twg_heading = {"page": page, "left": left, "top": top, "right": right, "bottom": bottom}

    if not all(key in anchors for key in ("requested_by", "funds_available", "approved_by")):
        logger.warning("SIGNATORY region not detected: missing one or more anchor labels")
        return result

    page_candidates = [int(anchors[key]["page"]) for key in ("requested_by", "funds_available", "approved_by")]
    region_page = max(set(page_candidates), key=page_candidates.count)

    region_top = min(float(anchors[key]["top"]) for key in ("requested_by", "funds_available", "approved_by"))
    region_bottom = region_top + 0.12
    if twg_heading and int(twg_heading.get("page", 0) or 0) == region_page and float(twg_heading.get("top", 0.0) or 0.0) > region_top:
        region_bottom = float(twg_heading.get("top", 0.0) or 0.0)

    region_left = max(0.0, min(float(anchors[key]["left"]) for key in ("requested_by", "funds_available", "approved_by")) - 0.20)
    region_right = min(1.0, max(float(anchors[key]["right"]) for key in ("requested_by", "funds_available", "approved_by")) + 0.20)

    if region_right <= region_left:
        region_left, region_right = 0.0, 1.0

    region_width = region_right - region_left
    col1_end = region_left + (region_width / 3.0)
    col2_end = region_left + ((region_width * 2.0) / 3.0)

    logger.info(
        "Detected signatory region | page=%s top=%.4f bottom=%.4f left=%.4f right=%.4f",
        region_page,
        region_top,
        region_bottom,
        region_left,
        region_right,
    )
    logger.info(
        "Detected column boundaries | left_end=%.4f middle_end=%.4f",
        col1_end,
        col2_end,
    )

    def in_region(record: Dict[str, Any]) -> bool:
        if int(record.get("page", 1) or 1) != region_page:
            return False
        left = float(record.get("left") or 0.0)
        right = float(record.get("right") or 0.0)
        top = float(record.get("top") or 0.0)
        bottom = float(record.get("bottom") or 0.0)
        overlaps_x = right >= region_left and left <= region_right
        overlaps_y = bottom >= region_top and top <= region_bottom
        return overlaps_x and overlaps_y

    region_records: List[Dict[str, Any]] = []
    seen_keys = set()
    for block in blocks:
        block_type = str(block.get("BlockType") or "")
        if block_type not in {"WORD", "LINE", "CELL", "MERGED_CELL"}:
            continue

        text, _ = extract_text_from_block(block, block_map)
        text = normalize_space(text)
        if not text:
            continue

        left, top, right, bottom = bbox(block)
        record = {
            "id": str(block.get("Id") or ""),
            "type": block_type,
            "text": text,
            "norm": normalize_label(text),
            "page": int(block.get("Page", 1) or 1),
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "cx": (left + right) / 2.0,
        }

        if not in_region(record):
            continue

        dedupe_key = (
            record["type"],
            round(record["left"], 4),
            round(record["top"], 4),
            record["text"],
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        region_records.append(record)

    column_map = {
        0: "requested_by",
        1: "funds_available",
        2: "approved_by",
    }
    columns: Dict[str, List[Dict[str, Any]]] = {
        "requested_by": [],
        "funds_available": [],
        "approved_by": [],
    }

    for record in sorted(region_records, key=lambda item: (item["top"], item["left"], item["type"])):
        cx = float(record.get("cx") or 0.0)
        col_idx = 0 if cx < col1_end else 1 if cx < col2_end else 2
        col_key = column_map[col_idx]
        columns[col_key].append(record)
        logger.info(
            "Assigned signatory block | column=%s type=%s top=%.4f left=%.4f text=%s",
            col_key,
            record["type"],
            record["top"],
            record["left"],
            record["text"],
        )

    printed_name_y: Optional[float] = None
    designation_y: Optional[float] = None
    signature_y: Optional[float] = None
    for record in sorted(region_records, key=lambda item: (item["top"], item["left"])):
        norm = record["norm"]
        if printed_name_y is None and norm.startswith("printed name"):
            printed_name_y = float(record["top"])
        if designation_y is None and norm.startswith("designation"):
            designation_y = float(record["top"])
        if signature_y is None and norm.startswith("signature"):
            signature_y = float(record["top"])

    def inline_value(text: str) -> str:
        candidate = normalize_space(text.split(":", 1)[-1]) if ":" in text else ""
        if is_effectively_blank(candidate):
            return ""
        if normalize_label(candidate) in {"printed name", "designation", "signature"}:
            return ""
        return candidate

    def is_label_like(norm: str) -> bool:
        if not norm:
            return True
        if norm.startswith("requested by"):
            return True
        if norm.startswith("funds available"):
            return True
        if norm.startswith("approved by"):
            return True
        if norm.startswith("signature"):
            return True
        if norm.startswith("printed name"):
            return True
        if norm.startswith("designation"):
            return True
        return False

    def pick_near_row(records: List[Dict[str, Any]], row_y: Optional[float], upper: Optional[float], lower: Optional[float]) -> str:
        candidates: List[Tuple[int, float, str]] = []
        type_priority = {"LINE": 0, "MERGED_CELL": 1, "CELL": 2, "WORD": 3}
        for record in records:
            text = record["text"]
            norm = record["norm"]
            top = float(record["top"])
            block_type = str(record.get("type") or "")

            if is_label_like(norm):
                continue
            if not re.search(r"[A-Za-z]", text):
                continue

            if upper is not None and top < upper:
                continue
            if lower is not None and top > lower:
                continue

            if row_y is not None:
                distance = abs(top - row_y)
                if distance > 0.03:
                    continue
                candidates.append((type_priority.get(block_type, 9), distance, text))
            else:
                candidates.append((type_priority.get(block_type, 9), 0.0, text))

        if not candidates:
            return ""
        candidates.sort(key=lambda item: (item[0], item[1]))
        return normalize_space(candidates[0][2])

    def preferred_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        non_word = [record for record in records if str(record.get("type") or "") != "WORD"]
        return non_word if non_word else records

    for col_key, records in columns.items():
        ordered = sorted(records, key=lambda item: (item["top"], item["left"], item["type"]))
        extract_records = preferred_records(ordered)

        printed_name = ""
        designation = ""

        for record in extract_records:
            norm = record["norm"]
            if norm.startswith("printed name"):
                candidate = inline_value(record["text"])
                if candidate:
                    printed_name = candidate
                    break

        if not printed_name:
            upper = signature_y - 0.002 if signature_y is not None else None
            lower = (designation_y - 0.002) if designation_y is not None else region_bottom
            printed_name = pick_near_row(extract_records, printed_name_y, upper, lower)

        for record in extract_records:
            norm = record["norm"]
            if norm.startswith("designation"):
                candidate = inline_value(record["text"])
                if candidate:
                    designation = candidate
                    break

        if not designation:
            upper = (designation_y - 0.005) if designation_y is not None else None
            designation = pick_near_row(extract_records, designation_y, upper, region_bottom)

        result[col_key]["printed_name"] = printed_name
        result[col_key]["designation"] = designation

    logger.info("Final extracted names and designations | %s", result)
    return result


def extract_footer_fields(
    blocks: List[Dict[str, Any]],
    kv_fields: Dict[str, ParsedField],
    tables: List[Dict[str, Any]],
) -> Tuple[Dict[str, ParsedField], Dict[str, Dict[str, str]]]:
    """Extract CTU footer fields, preferring KEY_VALUE_SET and using LINE fallback for missing values."""
    footer_mapping = {
        "purpose": ["purpose"],
        "requested_by": ["requested by", "requested"],
        "budget_officer": ["funds available", "budget officer"],
        "approved_by": ["approved by", "approved"],
        "twg": ["specifications verified by technical working group", "technical working group", "twg"],
    }

    result: Dict[str, ParsedField] = {}
    for target, aliases in footer_mapping.items():
        matched = match_field(kv_fields, aliases)
        if matched:
            result[target] = matched
        else:
            result[target] = ParsedField(value="", confidence=0.0, needs_review=True)

    lines = build_line_index(blocks)
    if not lines:
        return result, {
            "requested_by": {"name": "", "designation": ""},
            "budget_officer": {"name": "", "designation": ""},
            "approved_by": {"name": "", "designation": ""},
            "twg": {"name": "", "designation": ""},
        }

    table_cut_page = 0
    table_cut_top = 0.0
    if tables:
        last_table = sorted(tables, key=lambda item: (item.get("page", 0), item.get("table_index", 0)))[-1]
        table_cut_page = int(last_table.get("page", 0) or 0)

    footer_lines: List[Dict[str, Any]] = []
    for line in lines:
        page = int(line.get("Page", 1) or 1)
        top = float(((line.get("Geometry") or {}).get("BoundingBox") or {}).get("Top") or 0.0)
        if table_cut_page and page < table_cut_page:
            continue
        if table_cut_page and page == table_cut_page and top < table_cut_top:
            continue
        footer_lines.append(line)

    line_texts = [normalize_space(str(line.get("Text") or "")) for line in footer_lines]

    def find_after_heading(heading: str) -> str:
        for idx, text in enumerate(line_texts):
            if normalize_label(heading) in normalize_label(text):
                for nxt in line_texts[idx + 1 :]:
                    cleaned = normalize_space(nxt)
                    if not cleaned:
                        continue
                    if re.match(r"^signature\s*:?$", cleaned, re.I):
                        continue
                    if normalize_label(cleaned) in {
                        "purpose",
                        "requested by",
                        "funds available",
                        "approved by",
                        "specifications verified by technical working group",
                    }:
                        break
                    if is_effectively_blank(cleaned):
                        continue
                    if cleaned.lower().startswith("printed name"):
                        return normalize_space(cleaned.split(":", 1)[-1])
                    return cleaned
        return ""

    def parse_signatory_sections() -> Dict[str, Dict[str, str]]:
        anchors = {
            "requested_by": ["requested by"],
            "budget_officer": ["funds available"],
            "approved_by": ["approved by"],
            "twg": ["specifications verified by technical working group", "technical working group"],
        }

        boundaries = [
            "purpose",
            "requested by",
            "funds available",
            "approved by",
            "specifications verified by technical working group",
            "technical working group",
        ]

        parsed: Dict[str, Dict[str, str]] = {
            "requested_by": {"name": "", "designation": ""},
            "budget_officer": {"name": "", "designation": ""},
            "approved_by": {"name": "", "designation": ""},
            "twg": {"name": "", "designation": ""},
        }

        for key, labels in anchors.items():
            start_index = -1
            for idx, text in enumerate(line_texts):
                norm = normalize_label(text)
                if any(normalize_label(label) in norm for label in labels):
                    start_index = idx
                    break

            if start_index == -1:
                continue

            section_lines: List[str] = []
            for nxt in line_texts[start_index + 1 :]:
                cleaned = normalize_space(nxt)
                if not cleaned:
                    continue
                norm_clean = normalize_label(cleaned)
                if norm_clean in boundaries:
                    break
                section_lines.append(cleaned)

            name = ""
            designation = ""

            def is_label_only(value: str) -> bool:
                norm = normalize_label(value)
                return norm in {"printed name", "name", "designation", "position", "title"}

            def is_name_candidate(value: str) -> bool:
                cleaned = normalize_space(value)
                if not cleaned:
                    return False
                if re.match(r"^signature\s*:?$", cleaned, re.I):
                    return False
                if is_label_only(cleaned):
                    return False
                return True

            for idx, line in enumerate(section_lines):
                if re.match(r"^signature\s*:?$", line, re.I):
                    continue

                if re.match(r"^printed\s+name\s*:?", line, re.I):
                    name_candidate = normalize_space(line.split(":", 1)[-1])
                    if name_candidate and not is_label_only(name_candidate):
                        name = name_candidate
                    elif idx + 1 < len(section_lines):
                        for nxt in section_lines[idx + 1 :]:
                            next_line = normalize_space(nxt)
                            if is_name_candidate(next_line) and not re.match(r"^designation\b", next_line, re.I):
                                name = next_line
                                break
                    continue

                if re.match(r"^designation\s*:?", line, re.I):
                    designation_candidate = normalize_space(line.split(":", 1)[-1])
                    if designation_candidate and not is_label_only(designation_candidate):
                        designation = designation_candidate
                    elif idx + 1 < len(section_lines):
                        for nxt in section_lines[idx + 1 :]:
                            next_line = normalize_space(nxt)
                            if is_name_candidate(next_line):
                                designation = next_line
                                break
                    continue

                if not name and is_name_candidate(line) and not re.match(r"^designation\b", line, re.I):
                    name = line

            parsed[key] = {
                "name": name,
                "designation": designation,
            }

        return parsed

    def parse_grouped_signatories() -> Dict[str, Dict[str, str]]:
        """Handle layouts where Requested/Funds/Approved share one Printed Name + Designation block."""

        parsed = {
            "requested_by": {"name": "", "designation": ""},
            "budget_officer": {"name": "", "designation": ""},
            "approved_by": {"name": "", "designation": ""},
            "twg": {"name": "", "designation": ""},
        }

        heading_indices: Dict[str, int] = {}
        for idx, text in enumerate(line_texts):
            norm = normalize_label(text)
            if "requested by" in norm and "requested_by" not in heading_indices:
                heading_indices["requested_by"] = idx
            if "funds available" in norm and "budget_officer" not in heading_indices:
                heading_indices["budget_officer"] = idx
            if "approved by" in norm and "approved_by" not in heading_indices:
                heading_indices["approved_by"] = idx

        if not all(key in heading_indices for key in ("requested_by", "budget_officer", "approved_by")):
            return parsed

        ordered_heads = [heading_indices["requested_by"], heading_indices["budget_officer"], heading_indices["approved_by"]]
        if (max(ordered_heads) - min(ordered_heads)) > 12:
            return parsed

        start_idx = min(ordered_heads)
        end_idx = len(line_texts)
        for idx in range(max(ordered_heads) + 1, len(line_texts)):
            norm = normalize_label(line_texts[idx])
            if norm in {
                "specifications verified by technical working group",
                "technical working group",
                "purpose",
            }:
                end_idx = idx
                break

        section_lines = [normalize_space(line_texts[idx]) for idx in range(start_idx, end_idx)]

        def is_person_name(value: str) -> bool:
            cleaned = normalize_space(value)
            if not cleaned:
                return False
            if re.match(r"^(signature|printed\s+name|designation|requested\s+by|funds\s+available|approved\s+by)\b", cleaned, re.I):
                return False
            if not re.search(r"[A-Za-z]", cleaned):
                return False
            return len(cleaned.split()) >= 2

        def is_designation(value: str) -> bool:
            cleaned = normalize_space(value)
            if not cleaned:
                return False
            if re.match(r"^(signature|printed\s+name|designation|requested\s+by|funds\s+available|approved\s+by)\b", cleaned, re.I):
                return False
            if not re.search(r"[A-Za-z]", cleaned):
                return False
            return True

        names: List[str] = []
        designations: List[str] = []

        in_names = False
        in_designations = False
        for line in section_lines:
            if re.match(r"^signature\s*:?", line, re.I):
                continue

            if re.match(r"^printed\s+name\s*:?", line, re.I):
                in_names = True
                in_designations = False
                inline = normalize_space(line.split(":", 1)[-1]) if ":" in line else ""
                if is_person_name(inline):
                    names.append(inline)
                continue

            if re.match(r"^designation\s*:?", line, re.I):
                in_names = False
                in_designations = True
                inline = normalize_space(line.split(":", 1)[-1]) if ":" in line else ""
                if is_designation(inline):
                    designations.append(inline)
                continue

            if in_names and is_person_name(line):
                names.append(line)
                continue

            if in_designations and is_designation(line):
                designations.append(line)

        ordered_keys = ["requested_by", "budget_officer", "approved_by"]
        for idx, key in enumerate(ordered_keys):
            if idx < len(names):
                parsed[key]["name"] = names[idx]
            if idx < len(designations):
                parsed[key]["designation"] = designations[idx]

        return parsed

    section_signatories = parse_signatory_sections()
    grouped_signatories = parse_grouped_signatories()

    for key in section_signatories:
        grouped_name = grouped_signatories.get(key, {}).get("name", "")
        grouped_designation = grouped_signatories.get(key, {}).get("designation", "")
        if grouped_name:
            section_signatories[key]["name"] = grouped_name
        if grouped_designation:
            section_signatories[key]["designation"] = grouped_designation

    def parse_signatories_by_geometry() -> Dict[str, Dict[str, str]]:
        line_objs: List[Dict[str, Any]] = []
        for line in lines:
            text = normalize_space(str(line.get("Text") or ""))
            box = ((line.get("Geometry") or {}).get("BoundingBox") or {})
            line_objs.append(
                {
                    "text": text,
                    "norm": normalize_label(text),
                    "left": float(box.get("Left") or 0.0),
                    "top": float(box.get("Top") or 0.0),
                }
            )

        def find_heading(label_variants: List[str]) -> Optional[Dict[str, Any]]:
            for obj in line_objs:
                if any(normalize_label(variant) in obj["norm"] for variant in label_variants):
                    return obj
            return None

        def is_person_line(value: str) -> bool:
            cleaned = normalize_space(value)
            if not cleaned:
                return False
            if re.match(r"^(signature|designation|printed\s+name)\b", cleaned, re.I):
                return False
            if re.match(r"^(purpose|requested by|funds available|approved by|specifications verified)\b", cleaned, re.I):
                return False
            return bool(re.search(r"[A-Za-z]", cleaned))

        def extract_for_heading(heading_obj: Dict[str, Any], stop_top: float) -> Dict[str, str]:
            left = float(heading_obj.get("left") or 0.0)
            top = float(heading_obj.get("top") or 0.0)
            upper_bound = min(top + 0.28, stop_top) if stop_top > top else top + 0.28

            column_lines = [
                obj
                for obj in line_objs
                if obj["top"] > top and obj["top"] < upper_bound and abs(obj["left"] - left) <= 0.22
            ]
            column_lines.sort(key=lambda obj: obj["top"])

            name = ""
            designation = ""
            for idx, obj in enumerate(column_lines):
                text = obj["text"]
                if re.match(r"^signature\s*:?$", text, re.I):
                    continue

                if re.match(r"^printed\s+name\s*:?", text, re.I):
                    candidate = normalize_space(text.split(":", 1)[-1])
                    if candidate and normalize_label(candidate) not in {"printed name", "name"}:
                        name = candidate
                    else:
                        for nxt in column_lines[idx + 1 :]:
                            if is_person_line(nxt["text"]):
                                name = nxt["text"]
                                break
                    continue

                if re.match(r"^designation\s*:?", text, re.I):
                    candidate = normalize_space(text.split(":", 1)[-1])
                    if candidate and normalize_label(candidate) not in {"designation", "position", "title"}:
                        designation = candidate
                    else:
                        for nxt in column_lines[idx + 1 :]:
                            if is_person_line(nxt["text"]):
                                designation = nxt["text"]
                                break
                    continue

                if not name and is_person_line(text):
                    name = text

            return {"name": name, "designation": designation}

        geometry_result = {
            "requested_by": {"name": "", "designation": ""},
            "budget_officer": {"name": "", "designation": ""},
            "approved_by": {"name": "", "designation": ""},
            "twg": {"name": "", "designation": ""},
        }

        heading_map = {
            "requested_by": ["requested by"],
            "budget_officer": ["funds available"],
            "approved_by": ["approved by"],
            "twg": ["specifications verified by technical working group", "technical working group"],
        }

        heading_positions: List[float] = []
        heading_objs_by_key: Dict[str, Dict[str, Any]] = {}
        for key, labels in heading_map.items():
            heading_obj = find_heading(labels)
            if not heading_obj:
                continue
            heading_objs_by_key[key] = heading_obj
            heading_positions.append(float(heading_obj.get("top") or 0.0))

        for key, heading_obj in heading_objs_by_key.items():
            heading_top = float(heading_obj.get("top") or 0.0)
            future_tops = [value for value in heading_positions if value > heading_top]
            stop_top = min(future_tops) if future_tops else heading_top + 0.28
            geometry_result[key] = extract_for_heading(heading_obj, stop_top)

        return geometry_result

    geometry_signatories = parse_signatories_by_geometry()
    for key in section_signatories:
        if not section_signatories[key].get("name") and geometry_signatories.get(key, {}).get("name"):
            section_signatories[key]["name"] = geometry_signatories[key]["name"]
        if not section_signatories[key].get("designation") and geometry_signatories.get(key, {}).get("designation"):
            section_signatories[key]["designation"] = geometry_signatories[key]["designation"]

    for key, heading in {
        "purpose": "purpose",
        "requested_by": "requested by",
        "budget_officer": "funds available",
        "approved_by": "approved by",
        "twg": "specifications verified by technical working group",
    }.items():
        current_value = normalize_space(result[key].value)
        current_invalid = not current_value or re.match(r"^signature\s*:?$", current_value, re.I)
        section_name = section_signatories.get(key, {}).get("name", "")
        if current_invalid and section_name and not re.match(r"^(signature\s*:?)|(printed\s+name\s*:?)$", section_name, re.I):
            result[key] = ParsedField(value=section_name, confidence=90.0, needs_review=False)
            continue

        if result[key].value:
            if re.match(r"^signature\s*:?$", result[key].value, re.I):
                logger.warning("FALLBACK replacement for signature-only value | field=%s", key)
            else:
                continue

        if result[key].value and not re.match(r"^signature\s*:?$", result[key].value, re.I):
            continue

        logger.warning("FALLBACK footer field using LINE blocks | field=%s", key)
        value = find_after_heading(heading)
        if value:
            needs_review = is_low_confidence(75.0)
            result[key] = ParsedField(value=value, confidence=75.0, needs_review=needs_review)

    return result, section_signatories


def parse_ctu_purchase_request(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Primary structured parser for CTU Purchase Request documents using Textract blocks."""
    kv_fields = parse_key_value_sets(blocks)
    header_fields = extract_header_fields(kv_fields)
    line_header_fallback = extract_header_fields_from_lines(blocks)
    for key, field in header_fields.items():
        if field.value:
            continue
        if key in line_header_fallback:
            logger.warning("FALLBACK header field using LINE blocks | field=%s", key)
            header_fields[key] = line_header_fallback[key]

    items, table_info = parse_tables(blocks)
    signatories = parse_signatories(blocks)
    footer_fields, signatory_sections = extract_footer_fields(blocks, kv_fields, table_info)

    for internal_key, external_key in {
        "requested_by": "requested_by",
        "budget_officer": "funds_available",
        "approved_by": "approved_by",
    }.items():
        signatory_payload = signatories.get(external_key, {}) or {}
        printed_name = normalize_space(str(signatory_payload.get("printed_name") or ""))
        designation = normalize_space(str(signatory_payload.get("designation") or ""))

        if printed_name:
            footer_fields[internal_key] = ParsedField(value=printed_name, confidence=90.0, needs_review=False)
            signatory_sections.setdefault(internal_key, {"name": "", "designation": ""})
            signatory_sections[internal_key]["name"] = printed_name
        if designation:
            signatory_sections.setdefault(internal_key, {"name": "", "designation": ""})
            signatory_sections[internal_key]["designation"] = designation

    confidence_values = [
        field.confidence for field in list(header_fields.values()) + list(footer_fields.values()) if field.confidence > 0
    ]
    confidence_values.extend([item.confidence for item in items if item.confidence > 0])
    avg_conf = mean(confidence_values) if confidence_values else 0.0

    missing_required = [
        name
        for name in ["entity_name", "pr_number", "date", "office", "purpose"]
        if not (header_fields.get(name) or footer_fields.get(name))
        or not ((header_fields.get(name) or footer_fields.get(name)).value)
    ]

    logger.info("Textract fields extracted: %s", sum(1 for f in list(header_fields.values()) + list(footer_fields.values()) if f.value))
    logger.info("Textract missing required fields: %s", missing_required)
    logger.info("Textract confidence avg: %.2f", avg_conf)
    if not footer_fields["purpose"].value:
        logger.warning("VALIDATION purpose is empty")
    if not header_fields["office"].value:
        logger.warning("VALIDATION office is empty")

    return {
        "entity_name": header_fields["entity_name"].value,
        "fund_cluster": header_fields["fund_cluster"].value,
        "office": header_fields["office"].value,
        "pr_number": header_fields["pr_number"].value,
        "date": header_fields["date"].value,
        "responsibility_center_code": header_fields["responsibility_center_code"].value,
        "purpose": footer_fields["purpose"].value,
        "requested_by": footer_fields["requested_by"].value,
        "budget_officer": footer_fields["budget_officer"].value,
        "approved_by": footer_fields["approved_by"].value,
        "twg": footer_fields["twg"].value,
        "signatory_designations": {
            "requested_by": signatory_sections.get("requested_by", {}).get("designation", ""),
            "budget_officer": signatory_sections.get("budget_officer", {}).get("designation", ""),
            "approved_by": signatory_sections.get("approved_by", {}).get("designation", ""),
            "twg": signatory_sections.get("twg", {}).get("designation", ""),
        },
        "signatory_names": {
            "requested_by": signatory_sections.get("requested_by", {}).get("name", ""),
            "budget_officer": signatory_sections.get("budget_officer", {}).get("name", ""),
            "approved_by": signatory_sections.get("approved_by", {}).get("name", ""),
            "twg": signatory_sections.get("twg", {}).get("name", ""),
        },
        "signatories": signatories,
        "items": [item.to_dict() for item in items],
        "fields_confidence": {
            "entity_name": header_fields["entity_name"].to_dict(),
            "fund_cluster": header_fields["fund_cluster"].to_dict(),
            "office": header_fields["office"].to_dict(),
            "pr_number": header_fields["pr_number"].to_dict(),
            "date": header_fields["date"].to_dict(),
            "responsibility_center_code": header_fields["responsibility_center_code"].to_dict(),
            "purpose": footer_fields["purpose"].to_dict(),
            "requested_by": footer_fields["requested_by"].to_dict(),
            "budget_officer": footer_fields["budget_officer"].to_dict(),
            "approved_by": footer_fields["approved_by"].to_dict(),
            "twg": footer_fields["twg"].to_dict(),
        },
        "table_diagnostics": table_info,
        "missing_required_fields": missing_required,
        "confidence_summary": {
            "average": round(avg_conf, 2),
            "threshold": LOW_CONFIDENCE_THRESHOLD,
            "items_count": len(items),
        },
    }

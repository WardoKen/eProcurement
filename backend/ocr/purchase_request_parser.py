from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

try:
    from .layout_parser import DocumentLayoutParser
    from .header_parser import HeaderParser
    from .textract_purchase_request_parser import parse_ctu_purchase_request
    from .debug_utils import get_parser_logger
except ImportError:  # pragma: no cover
    from backend.ocr.layout_parser import DocumentLayoutParser
    from backend.ocr.header_parser import HeaderParser
    from backend.ocr.textract_purchase_request_parser import parse_ctu_purchase_request
    from backend.ocr.debug_utils import get_parser_logger


logger = get_parser_logger()


def _is_effectively_blank(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if not cleaned:
        return True
    return bool(re.fullmatch(r"[:\-_/\\|.\s]+", cleaned))


def _normalize_code_like(value: str, allow_dash: bool = True) -> str:
    """Normalize OCR artifacts for code-like fields by removing punctuation noise."""
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    if _is_effectively_blank(cleaned):
        return ""

    if allow_dash:
        cleaned = re.sub(r"[^A-Za-z0-9\- ]", "", cleaned)
    else:
        cleaned = re.sub(r"[^A-Za-z0-9 ]", "", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if _is_effectively_blank(cleaned):
        return ""
    return cleaned


class PurchaseRequestParser:
    def __init__(self) -> None:
        self.layout_parser = DocumentLayoutParser()
        self.header_parser = HeaderParser()

    def parse(self, raw_text: str, layout: Dict[str, Any] | None = None) -> Dict[str, Any]:
        layout = layout or {}
        sections = self._normalize_layout_sections(layout)

        header = self._parse_header_from_layout(sections.get("header", []), raw_text)
        items = self._parse_items_from_layout(sections.get("items", []), raw_text)
        footer_blocks = sections.get("footer", [])
        footer = self._parse_footer_from_layout(footer_blocks, raw_text)
        requested_by = self._parse_signatory_from_blocks(footer_blocks, "requested")
        approved_by = self._parse_signatory_from_blocks(footer_blocks, "approved")
        lines = self._prepare_lines(raw_text)

        if not header.get("entityName") and not header.get("prNumber"):
            header = self._parse_header(lines)
            items = self._parse_items(lines)
            footer = {
                "purpose": self._parse_purpose(lines),
                "requestedBy": self._parse_signatory(lines, "requested"),
                "approvedBy": self._parse_signatory(lines, "approved"),
            }
            requested_by = footer.get("requestedBy", {})
            approved_by = footer.get("approvedBy", {})

        if not requested_by.get("name"):
            fallback_requested = self._parse_signatory(lines, "requested")
            block_requested = self._parse_signatory_from_blocks(footer_blocks, "requested")
            requested_by = block_requested if block_requested.get("name") else fallback_requested
        if not approved_by.get("name"):
            fallback_approved = self._parse_signatory(lines, "approved")
            block_approved = self._parse_signatory_from_blocks(footer_blocks, "approved")
            approved_by = block_approved if block_approved.get("name") else fallback_approved

        purpose = footer.get("purpose", "") or self._parse_purpose(lines)
        validation = self._build_validation(header, items, purpose, requested_by, approved_by)

        return {
            "header": {
                "entityName": header.get("entityName", ""),
                "fundCluster": header.get("fundCluster", ""),
                "office": header.get("office", ""),
                "prNumber": header.get("prNumber", ""),
                "date": header.get("date", ""),
                "responsibilityCenterCode": header.get("responsibilityCenterCode", ""),
            },
            "items": items,
            "footer": {
                "purpose": purpose,
                "requestedBy": requested_by.get("name", ""),
                "approvedBy": approved_by.get("name", ""),
            },
            "purpose": purpose,
            "requestedBy": requested_by,
            "approvedBy": approved_by,
            "validation": validation,
            "raw_text": raw_text,
            "requested_items": self._adapt_items(items),
            "entityName": header.get("entityName", ""),
            "fundCluster": header.get("fundCluster", ""),
            "officeSection": header.get("office", ""),
            "prNumber": header.get("prNumber", ""),
            "date": header.get("date", ""),
            "responsibilityCenterCode": header.get("responsibilityCenterCode", ""),
            "requested_by_name": requested_by.get("name", ""),
            "requested_by_designation": requested_by.get("designation", ""),
            "funds_available_name": self._extract_section_signatory(raw_text, "funds available").get("name", ""),
            "funds_available_designation": self._extract_section_signatory(raw_text, "funds available").get("designation", ""),
            "approved_by_name": approved_by.get("name", ""),
            "approved_by_designation": approved_by.get("designation", ""),
            "twg_name": self._extract_section_signatory(raw_text, "specifications verified").get("name", ""),
            "twg_designation": self._extract_section_signatory(raw_text, "specifications verified").get("designation", ""),
            "grand_total": self._compute_grand_total(items),
        }

    def _normalize_layout_sections(self, layout: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        sections = layout.get("sections") or {}
        if isinstance(sections, dict):
            return {
                key: value if isinstance(value, list) else []
                for key, value in {
                    "header": sections.get("header", []),
                    "items": sections.get("items", []),
                    "footer": sections.get("footer", []),
                }.items()
            }

        blocks = layout.get("blocks") or []
        if not blocks:
            return {"header": [], "items": [], "footer": []}
        return self._derive_sections_from_blocks(blocks)

    def _derive_sections_from_blocks(self, blocks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        sections = {"header": [], "items": [], "footer": []}
        if not blocks:
            return sections

        ordered = sorted(blocks, key=lambda item: (item.get("page", 0), self._block_y(item), self._block_x(item)))
        items_start = None
        footer_start = None
        for index, block in enumerate(ordered):
            text = self._clean(block.get("text", ""))
            if items_start is None and self._looks_like_table_anchor(text):
                items_start = index
                continue
            if footer_start is None and self._looks_like_footer_anchor(text):
                footer_start = index
                break

        if items_start is None:
            items_start = len(ordered)
        if footer_start is None:
            footer_start = len(ordered)

        sections["header"] = ordered[:items_start]
        sections["items"] = ordered[items_start:footer_start]
        sections["footer"] = ordered[footer_start:]
        return sections

    def _prepare_lines(self, raw_text: str) -> List[str]:
        return [self._clean(line) for line in (raw_text or "").splitlines() if self._clean(line)]

    def _parse_header(self, lines: List[str]) -> Dict[str, str]:
        header: Dict[str, str] = {}
        for field_name, labels in {
            "entityName": ["entity name", "name of entity"],
            "fundCluster": ["fund cluster"],
            "office": ["office/section", "office/department", "office"],
            "prNumber": ["pr no", "pr number", "pr"],
            "date": ["date"],
            "responsibilityCenterCode": ["responsibility center code", "responsibility center"],
        }.items():
            raw_val = self._extract_value(lines, labels)
            if raw_val:
                # If the captured value contains other field labels (e.g. 'Fund Cluster:'), split at that point
                sep = re.compile(r"\b(?:fund cluster|pr no|pr number|pr|responsibility center code|responsibility center|date)\b", re.I)
                header[field_name] = sep.split(raw_val)[0].strip()
            else:
                header[field_name] = raw_val
        return header

    def _parse_header_from_layout(self, blocks: List[Dict[str, Any]], raw_text: str) -> Dict[str, str]:
        header = {}
        if blocks:
            for field_name, labels in {
                "entityName": ["entity name", "name of entity"],
                "fundCluster": ["fund cluster"],
                "office": ["office/section", "office/department", "office"],
                "prNumber": ["pr no", "pr number"],
                "date": ["date"],
                "responsibilityCenterCode": ["responsibility center code", "responsibility center"],
            }.items():
                value = self._extract_field_value(blocks, labels)
                if value:
                    sep = re.compile(r"\b(?:fund cluster|pr no|pr number|pr|responsibility center code|responsibility center|date)\b", re.I)
                    header[field_name] = sep.split(value)[0].strip()
        if not header:
            lines = self._prepare_lines(raw_text)
            header = self._parse_header(lines)
        return header

    def _parse_items_from_layout(self, blocks: List[Dict[str, Any]], raw_text: str) -> List[Dict[str, Any]]:
        if not blocks:
            lines = self._prepare_lines(raw_text)
            return self._parse_items(lines)

        rows: List[List[Dict[str, Any]]] = []
        current_row: List[Dict[str, Any]] = []
        for block in sorted(blocks, key=lambda item: (item.get("page", 0), self._block_y(item), self._block_x(item))):
            text = self._clean(block.get("text", ""))
            if not text or self._looks_like_header(text) or self._looks_like_footer_anchor(text):
                continue
            if self._looks_like_separator(text):
                if current_row:
                    rows.append(current_row)
                    current_row = []
                continue
            if current_row and not self._same_row(block, current_row[-1]):
                rows.append(current_row)
                current_row = []
            current_row.append(block)
        if current_row:
            rows.append(current_row)

        items: List[Dict[str, Any]] = []
        for row in rows:
            values = [self._clean(block.get("text", "")) for block in sorted(row, key=lambda item: self._block_x(item)) if self._clean(block.get("text", ""))]
            if not values:
                continue
            if self._looks_like_header(values[0]):
                continue
            if self._looks_like_numeric(values[0]) and len(values) == 1:
                continue
            # If table has many columns (e.g., stock_no, unit, description, qty, unit_cost, total_cost),
            # prefer extracting numeric columns from the right so description isn't polluted.
            description = ""
            quantity = ""
            unit_cost = ""
            total_cost = ""
            if len(values) >= 4:
                # take last 3 values as quantity, unit_cost, total_cost when they look numeric
                maybe_total = values[-1]
                maybe_unit = values[-2]
                maybe_qty = values[-3]
                if self._looks_like_numeric(maybe_total):
                    total_cost = maybe_total
                    if self._looks_like_numeric(maybe_unit):
                        unit_cost = maybe_unit
                        if self._looks_like_numeric(maybe_qty):
                            quantity = maybe_qty
                            description = " ".join(values[:-3])
                        else:
                            # qty not numeric, assume values[:-2] is description
                            description = " ".join(values[:-2])
                    else:
                        # unit not numeric, maybe table has qty and total only
                        if self._looks_like_numeric(maybe_qty):
                            quantity = maybe_qty
                            description = " ".join(values[:-2])
                        else:
                            description = " ".join(values[:-1])
                else:
                    # fallback: take first as description and next fields as qty/unit/total
                    description = values[0]
                    if len(values) >= 4:
                        quantity = values[1]
                        unit_cost = values[2]
                        total_cost = values[3]
                    elif len(values) == 3:
                        quantity = values[1]
                        unit_cost = values[2]
                    else:
                        quantity = values[1] if len(values) > 1 and self._looks_like_numeric(values[1]) else ""
            else:
                if items and not self._looks_like_numeric(values[0]):
                    items[-1]["description"] = f"{items[-1].get('description', '')} {values[0]}".strip()
                continue

            if description and not self._looks_like_numeric(description):
                items.append({
                    "itemNo": len(items) + 1,
                    "unit": "",
                    "description": description,
                    "quantity": quantity,
                    "unitCost": unit_cost,
                    "totalCost": total_cost,
                })

        if not items:
            lines = self._prepare_lines(raw_text)
            items = self._parse_items(lines)
        return items

    def _parse_footer_from_layout(self, blocks: List[Dict[str, Any]], raw_text: str) -> Dict[str, Any]:
        if not blocks:
            lines = self._prepare_lines(raw_text)
            return {
                "purpose": self._parse_purpose(lines),
                "requestedBy": self._parse_signatory(lines, "requested"),
                "approvedBy": self._parse_signatory(lines, "approved"),
            }

        purpose = self._extract_section_value(blocks, ["purpose"])
        requested_by = self._extract_signatory_value(blocks, "requested")
        approved_by = self._extract_signatory_value(blocks, "approved")
        return {
            "purpose": purpose,
            "requestedBy": requested_by,
            "approvedBy": approved_by,
        }

    def _parse_items(self, lines: List[str]) -> List[Dict[str, Any]]:
        item_header_index = None
        for index, line in enumerate(lines):
            if re.search(r"item description|stock/property no|stock\s*no|unit|quantity|unit cost|total cost", line, re.I):
                item_header_index = index + 1
                break

        if item_header_index is None:
            return []

        purpose_index = len(lines)
        for index in range(item_header_index, len(lines)):
            if re.search(r"^purpose\b", lines[index], re.I):
                purpose_index = index
                break

        candidates = [line for line in lines[item_header_index:purpose_index] if self._clean(line)]
        items: List[Dict[str, Any]] = []
        current: Dict[str, Any] | None = None

        for line in candidates:
            cleaned = self._clean(line)
            if self._is_table_header(cleaned) or self._is_section_heading(cleaned) or self._is_metadata_line(cleaned):
                continue
            if re.search(r"^stock/property no\b", cleaned, re.I):
                continue
            # If the entire line is numeric, assign sequentially to quantity/unitCost/totalCost
            if self._is_numeric(cleaned):
                if current is None:
                    continue
                if not current.get("quantity"):
                    current["quantity"] = cleaned
                elif not current.get("unitCost"):
                    current["unitCost"] = cleaned
                elif not current.get("totalCost"):
                    current["totalCost"] = cleaned
                continue

            # If the line contains embedded numeric tokens (e.g., 'unit 1 145,000 145,000.00'),
            # extract numbers from the right and keep the rest as description.
            # Only consider numeric tokens at the END of the line to avoid picking numbers from the description
            tokens = cleaned.split()
            numeric_tokens = []
            num_re = re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$")
            for tok in reversed(tokens):
                if num_re.match(tok):
                    numeric_tokens.insert(0, tok)
                    if len(numeric_tokens) >= 3:
                        break
                else:
                    break
            nums = numeric_tokens
            if nums:
                total = nums[-1] if len(nums) >= 1 else ""
                unitCost = nums[-2] if len(nums) >= 2 else ""
                quantity_num = nums[-3] if len(nums) >= 3 else ""
                # remove only the trailing numeric tokens from the line to form description
                if nums:
                    desc_tokens = tokens[:len(tokens) - len(nums)]
                    desc = " ".join(desc_tokens).strip()
                else:
                    desc = cleaned
                if current is None:
                    current = {"itemNo": len(items) + 1, "unit": "", "description": desc or cleaned, "quantity": quantity_num or "", "unitCost": unitCost or "", "totalCost": total or ""}
                    continue
                # If we already have a current and it's missing numeric fields, fill them
                if not current.get("quantity") and quantity_num:
                    current["quantity"] = quantity_num
                elif not current.get("unitCost") and unitCost:
                    current["unitCost"] = unitCost
                elif not current.get("totalCost") and total:
                    current["totalCost"] = total
                continue

            if current is None:
                current = {"itemNo": len(items) + 1, "unit": "", "description": cleaned, "quantity": "", "unitCost": "", "totalCost": ""}
                continue

            if current.get("quantity") or current.get("unitCost") or current.get("totalCost"):
                items.append(current)
                current = {"itemNo": len(items) + 1, "unit": "", "description": cleaned, "quantity": "", "unitCost": "", "totalCost": ""}
            else:
                current["description"] = f"{current.get('description', '')} {cleaned}".strip()

        if current and self._has_item_content(current):
            items.append(current)

        if not items and current:
            items.append(current)
        return items

    def _parse_purpose(self, lines: List[str]) -> str:
        for index, line in enumerate(lines):
            if re.search(r"^purpose\b", line, re.I):
                section_lines = []
                for next_line in lines[index + 1:]:
                    if re.search(r"^(requested by|approved by|funds available|specifications verified)", next_line, re.I):
                        break
                    if self._clean(next_line):
                        section_lines.append(self._clean(next_line))
                return " ".join(section_lines).strip()
        return ""

    def _parse_signatory(self, lines: List[str], role: str) -> Dict[str, str]:
        result = {"name": "", "designation": ""}
        heading = "requested by" if role == "requested" else "approved by"
        start_index = None
        for index, line in enumerate(lines):
            if re.search(rf"^{re.escape(heading)}\b", line, re.I):
                start_index = index + 1
                break

        if start_index is None:
            return result

        block = []
        for line in lines[start_index:]:
            if re.search(r"^(requested by|approved by|funds available|specifications verified|purpose)\b", line, re.I):
                break
            cleaned = self._clean(line)
            if self._is_meaningful_signatory_line(cleaned):
                block.append(cleaned)

        for index, line in enumerate(block):
            if re.match(r"^(printed\s+name|name)\s*[:\-]?", line, re.I):
                remainder = line.split(":", 1)[-1].split("-", 1)[-1].strip() if ":" in line else ""
                if remainder:
                    result["name"] = remainder
                else:
                    next_line = self._first_non_empty(block[index + 1:])
                    if next_line and not re.match(r"^(printed\s+name|name|designation|position|title)\b", next_line, re.I):
                        result["name"] = next_line
                continue

            if re.match(r"^(designation|position|title)\s*[:\-]?", line, re.I):
                remainder = line.split(":", 1)[-1].split("-", 1)[-1].strip() if ":" in line else ""
                if remainder:
                    result["designation"] = remainder
                else:
                    next_line = self._first_non_empty(block[index + 1:])
                    if next_line and not re.match(r"^(printed\s+name|name|designation|position|title)\b", next_line, re.I):
                        result["designation"] = next_line
                continue

            if not result["name"] and not re.match(r"^(designation|position|title)\b", line, re.I):
                result["name"] = line

            if result["name"] and not result["designation"] and re.match(r"^(twg|budget|campus|director|officer|engineer|engr|mr|ms|mrs)\b", line, re.I):
                result["designation"] = line

        if not result["name"] and block:
            result["name"] = self._first_non_empty(block)
        return result

    def _parse_signatory_from_blocks(self, blocks: List[Dict[str, Any]], role: str) -> Dict[str, str]:
        if not blocks:
            return {"name": "", "designation": ""}
        label = "requested by" if role == "requested" else "approved by"
        for index, block in enumerate(blocks):
            text = self._clean(block.get("text", ""))
            if self._fuzzy_matches(text, label):
                for next_block in blocks[index + 1:]:
                    candidate = self._clean(next_block.get("text", ""))
                    if not candidate:
                        continue
                    if self._looks_like_footer_anchor(candidate) and not self._fuzzy_matches(candidate, label):
                        break
                    if self._looks_like_name_candidate(candidate):
                        name = self._extract_name(candidate)
                        if name:
                            return {"name": name, "designation": ""}
                    if self._is_meaningful_signatory_line(candidate):
                        if re.match(r"^(printed\s+name|name)\s*[:\-]?", candidate, re.I):
                            name = self._extract_name(candidate)
                            if name:
                                return {"name": name, "designation": ""}
                        if not self._looks_like_footer_anchor(candidate):
                            return {"name": candidate, "designation": ""}
                break
        return {"name": "", "designation": ""}

    def _build_validation(self, header: Dict[str, str], items: List[Dict[str, Any]], purpose: str, requested_by: Dict[str, str], approved_by: Dict[str, str]) -> Dict[str, Any]:
        fields = {}
        for key, value in header.items():
            fields[key] = {"value": value, "confidence": 0.95 if value else 0.0}
        if items:
            fields["items"] = {"value": len(items), "confidence": 0.9}
        fields["purpose"] = {"value": purpose, "confidence": 0.9 if purpose else 0.0}
        fields["requestedBy"] = {"value": requested_by.get("name", ""), "confidence": 0.9 if requested_by.get("name") else 0.0}
        fields["approvedBy"] = {"value": approved_by.get("name", ""), "confidence": 0.9 if approved_by.get("name") else 0.0}
        return {"fields": fields, "lowConfidenceThreshold": 0.8}

    def _extract_field_value(self, blocks: List[Dict[str, Any]], labels: List[str]) -> str:
        for index, block in enumerate(blocks):
            text = self._clean(block.get("text", ""))
            if not text:
                continue
            if self._looks_like_label(text, labels):
                value = self._extract_value_from_label(text)
                if value:
                    return value
                for candidate in blocks[index + 1:]:
                    candidate_text = self._clean(candidate.get("text", ""))
                    if not candidate_text or self._looks_like_label(candidate_text, labels):
                        continue
                    if self._looks_like_header(candidate_text) or self._looks_like_footer_anchor(candidate_text):
                        break
                    if candidate_text and not self._looks_like_value_label(candidate_text):
                        return candidate_text
                break
        return ""

    def _extract_value(self, lines: List[str], labels: List[str]) -> str:
        for line in lines:
            for label in labels:
                match = re.match(rf"^{re.escape(label)}\s*[:\-]?\s*(.+)$", line, re.I)
                if match:
                    return self._clean(match.group(1))
        return ""

    def _extract_section_value(self, blocks: List[Dict[str, Any]], labels: List[str]) -> str:
        for index, block in enumerate(blocks):
            text = self._clean(block.get("text", ""))
            if self._looks_like_label(text, labels):
                for candidate in blocks[index + 1:]:
                    candidate_text = self._clean(candidate.get("text", ""))
                    if not candidate_text:
                        continue
                    if self._looks_like_label(candidate_text, labels):
                        break
                    if self._looks_like_footer_anchor(candidate_text) or self._looks_like_header(candidate_text):
                        break
                    return candidate_text
        return ""

    def _extract_signatory_value(self, blocks: List[Dict[str, Any]], role: str) -> Dict[str, str]:
        label = "requested by" if role == "requested" else "approved by"
        for index, block in enumerate(blocks):
            text = self._clean(block.get("text", ""))
            if self._fuzzy_matches(text, label):
                block_values: List[str] = []
                for candidate in blocks[index + 1:]:
                    candidate_text = self._clean(candidate.get("text", ""))
                    if not candidate_text:
                        continue
                    if self._looks_like_footer_anchor(candidate_text) and not self._fuzzy_matches(candidate_text, label):
                        break
                    if self._looks_like_name_candidate(candidate_text):
                        block_values.append(candidate_text)
                    elif self._is_meaningful_signatory_line(candidate_text):
                        block_values.append(candidate_text)
                if block_values:
                    name = self._extract_name(block_values[0])
                    return {"name": name, "designation": ""}
                return {"name": "", "designation": ""}
        return {"name": "", "designation": ""}

    def _clean(self, value: str) -> str:
        if not value:
            return ""
        v = re.sub(r"\s+", " ", value).strip()
        if not v:
            return ""

        low = v.lower()
        # Remove obvious filler lines like '****** nothing follows ****' or similar
        if 'nothing follows' in low:
            return ""

        # If the line is only underscores/dashes/asterisks (placeholders), treat as empty
        if re.fullmatch(r"[\_\-\* ]+", v):
            return ""

        # Replace long runs of underscores/dashes/asterisks inside text with a single space
        v = re.sub(r"[\_\-\*]{2,}", " ", v)

        # Trim again and return
        return v.strip()

    def _is_meaningful_signatory_line(self, value: str) -> bool:
        cleaned = self._clean(value)
        if not cleaned:
            return False
        if re.fullmatch(r"[_\-]{2,}", cleaned):
            return False
        if re.fullmatch(r"[\W_]+", cleaned):
            return False
        if re.match(r"^(requested by|approved by|funds available|specifications verified|purpose)\b", cleaned, re.I):
            return False
        if re.match(r"^(printed\s+name|name|designation|position|title)\b", cleaned, re.I):
            return True
        if re.match(r"^(twg|budget|campus|director|officer|engineer|engr|mr|ms|mrs)\b", cleaned, re.I):
            return True
        return True

    def _is_table_header(self, line: str) -> bool:
        return bool(re.search(r"^(item description|stock/property no|stock\s*no|unit|quantity|unit cost|total cost)$", line, re.I))

    def _is_metadata_line(self, line: str) -> bool:
        return bool(re.search(r"^(stock/property no|stock\s*no|unit|quantity|unit cost|total cost|item description)$", line, re.I))

    def _is_section_heading(self, line: str) -> bool:
        return bool(re.search(r"^(purchase request|purpose|requested by|approved by|funds available|specifications verified|item description)$", line, re.I))

    def _is_numeric(self, value: str) -> bool:
        cleaned = value.replace(" ", "")
        return bool(re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", cleaned))

    def _first_non_empty(self, lines: List[str]) -> str:
        for line in lines:
            cleaned = self._clean(line)
            if cleaned:
                return cleaned
        return ""

    def _has_item_content(self, item: Dict[str, Any]) -> bool:
        return bool(item.get("description") or item.get("quantity") or item.get("unitCost") or item.get("totalCost"))

    def _adapt_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "stock_no": "",
                "unit": item.get("unit", ""),
                "description": item.get("description", ""),
                "quantity": item.get("quantity", ""),
                "unit_cost": item.get("unitCost", ""),
                "total_cost": item.get("totalCost", ""),
            }
            for item in items
        ]

    def _compute_grand_total(self, items: List[Dict[str, Any]]) -> str:
        totals = []
        for item in items:
            total = (item.get("totalCost") or item.get("unitCost") or "").strip()
            if total:
                totals.append(float(re.sub(r"[^0-9.]", "", total)))
        if not totals:
            return ""
        return f"{sum(totals):.2f}"

    def _extract_section_signatory(self, raw_text: str, heading: str) -> Dict[str, str]:
        lines = self._prepare_lines(raw_text)
        start_index = None
        for index, line in enumerate(lines):
            if re.search(rf"^{re.escape(heading)}\b", line, re.I):
                start_index = index + 1
                break
        if start_index is None:
            return {"name": "", "designation": ""}

        block = []
        for line in lines[start_index:]:
            if re.search(r"^(purpose|requested by|approved by|funds available|specifications verified)\b", line, re.I):
                break
            cleaned = self._clean(line)
            if cleaned:
                block.append(cleaned)

        result = {"name": "", "designation": ""}
        for index, line in enumerate(block):
            if re.match(r"^(printed\s+name|name)\s*[:\-]?", line, re.I):
                remainder = line.split(":", 1)[-1].split("-", 1)[-1].strip() if ":" in line else ""
                if remainder:
                    result["name"] = remainder
                else:
                    next_line = self._first_non_empty(block[index + 1:])
                    if next_line and not re.match(r"^(printed\s+name|name|designation|position|title)\b", next_line, re.I):
                        result["name"] = next_line
                continue
            if re.match(r"^(designation|position|title)\s*[:\-]?", line, re.I):
                remainder = line.split(":", 1)[-1].split("-", 1)[-1].strip() if ":" in line else ""
                if remainder:
                    result["designation"] = remainder
                else:
                    next_line = self._first_non_empty(block[index + 1:])
                    if next_line and not re.match(r"^(printed\s+name|name|designation|position|title)\b", next_line, re.I):
                        result["designation"] = next_line
        if heading.lower().startswith("spec") and result["designation"]:
            result["designation"] = f"TWG-{result['designation']}"
        return result

    def _extract_value_from_label(self, text: str) -> str:
        if not text:
            return ""
        match = re.match(r"^(.*?)(?:[:\-])\s*(.+)$", text)
        if match:
            return self._clean(match.group(2))
        return ""

    def _looks_like_label(self, text: str, labels: List[str]) -> bool:
        normalized = self._clean(text).lower()
        for label in labels:
            if self._fuzzy_matches(normalized, label):
                return True
        return False

    def _looks_like_value_label(self, text: str) -> bool:
        return any(token in text.lower() for token in ["printed name", "designation", "position", "title", "name", "date", "pr no"])

    def _looks_like_header(self, text: str) -> bool:
        normalized = self._clean(text).lower()
        if not normalized:
            return False
        labels = ["item description", "description", "quantity", "unit cost", "total cost", "stock no", "stock/property no"]
        for label in labels:
            if normalized == label or normalized.startswith(label + " ") or normalized.endswith(" " + label):
                return True
            if label in {"item description", "description", "quantity", "unit cost", "total cost", "stock no", "stock/property no"}:
                if re.fullmatch(r"[\w/\s]+", normalized) and self._fuzzy_matches(normalized, label):
                    return True
        return False

    def _looks_like_footer_anchor(self, text: str) -> bool:
        normalized = self._clean(text).lower()
        return any(self._fuzzy_matches(normalized, label) for label in ["purpose", "requested by", "approved by", "certified correct", "signature", "remarks"])

    def _looks_like_table_anchor(self, text: str) -> bool:
        return self._looks_like_header(text)

    def _looks_like_separator(self, text: str) -> bool:
        return bool(re.fullmatch(r"[_\-]{3,}", self._clean(text)))

    def _looks_like_name_candidate(self, text: str) -> bool:
        normalized = self._clean(text).lower()
        return "printed name" in normalized or "name" in normalized

    def _extract_name(self, text: str) -> str:
        if not text:
            return ""
        if ":" in text:
            _, value = text.split(":", 1)
            return self._clean(value)
        return self._clean(text)

    def _looks_like_numeric(self, value: str) -> bool:
        return self._is_numeric(self._clean(value))

    def _same_row(self, block: Dict[str, Any], reference: Dict[str, Any]) -> bool:
        current_y = self._block_y(block)
        ref_y = self._block_y(reference)
        return abs(current_y - ref_y) <= 0.03

    def _block_x(self, block: Dict[str, Any]) -> float:
        bbox = block.get("bbox") or []
        if not bbox:
            return 0.0
        return float(bbox[0][0]) if len(bbox) > 0 else 0.0

    def _block_y(self, block: Dict[str, Any]) -> float:
        bbox = block.get("bbox") or []
        if not bbox:
            return 0.0
        return float(bbox[0][1]) if len(bbox) > 0 else 0.0

    def _fuzzy_matches(self, text: str, label: str) -> bool:
        value = self._clean(text).lower()
        target = self._clean(label).lower()
        if not value or not target:
            return False
        if target in value or value in target:
            return True
        if re.search(rf"\b{re.escape(target)}\b", value):
            return True
        similarity = SequenceMatcher(None, value, target).ratio()
        return similarity >= 0.78


def _to_legacy_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    legacy_items: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        legacy_items.append(
            {
                "itemNo": index,
                "unit": str(item.get("unit", "") or ""),
                "description": str(item.get("description", "") or ""),
                "quantity": str(item.get("quantity", "") or ""),
                "unitCost": str(item.get("unit_cost", "") or ""),
                "totalCost": str(item.get("total_cost", "") or ""),
            }
        )
    return legacy_items


def _compute_total(items: List[Dict[str, Any]]) -> str:
    total = 0.0
    for item in items:
        raw = item.get("total_cost", "")
        if raw in (None, ""):
            raw = item.get("unit_cost", "")
        try:
            cleaned = re.sub(r"[^0-9.]", "", str(raw))
            if cleaned:
                total += float(cleaned)
        except Exception:
            continue
    return f"{total:.2f}" if total else ""


def _map_structured_to_legacy(structured: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    items = structured.get("items") or []
    fallback_items = fallback.get("requested_items") or []
    use_items = items if items else fallback_items

    field_meta = structured.get("fields_confidence") or {}

    def pick(primary: str, fallback_key: str, default: str = "") -> str:
        value = str(structured.get(primary, "") or "").strip()
        if value and not _is_effectively_blank(value):
            logger.info("Mapped: %s <- Textract Value: %s", primary, value)
            return value
        fb = fallback.get(fallback_key, default)
        if fb and not _is_effectively_blank(str(fb)):
            logger.warning("FALLBACK mapping used for %s from legacy key %s", primary, fallback_key)
            return str(fb)
        return str(default)

    def pick_signatory(primary: str, fallback_key: str, default: str = "") -> str:
        value = str(structured.get(primary, "") or "").strip()
        if value and not _is_effectively_blank(value) and not re.match(r"^signature\s*:?$", value, re.I):
            logger.info("Mapped: %s <- Textract Value: %s", primary, value)
            return value
        if value and re.match(r"^signature\s*:?$", value, re.I):
            logger.warning("FALLBACK mapping used for %s because structured value is signature placeholder", primary)
        fb = str(fallback.get(fallback_key, default) or "").strip()
        if fb and (_is_effectively_blank(fb) or re.match(r"^signature\s*:?$", fb, re.I)):
            logger.warning("Discarding signature placeholder for %s from legacy fallback", primary)
            return ""
        return fb

    mapped_items = use_items if use_items is fallback_items else [
        {
            "stock_no": str(item.get("stock_no", "") or ""),
            "unit": str(item.get("unit", "") or ""),
            "description": str(item.get("description", "") or ""),
            "quantity": item.get("quantity", ""),
            "unit_cost": item.get("unit_cost", ""),
            "total_cost": item.get("total_cost", ""),
            "confidence": float(item.get("confidence", 0.0) or 0.0),
            "needs_review": bool(item.get("needs_review", False)),
        }
        for item in items
    ]

    for row in mapped_items:
        logger.info("Mapped: quantity <- %s", row.get("quantity", ""))
        logger.info("Mapped: unit_cost <- %s", row.get("unit_cost", ""))
        logger.info("Mapped: total_cost <- %s", row.get("total_cost", ""))
        logger.info("Mapped: description <- %s", row.get("description", ""))

    legacy_items = _to_legacy_items(mapped_items)

    validation_fields: Dict[str, Any] = {}
    for target, legacy_key in {
        "entity_name": "entityName",
        "fund_cluster": "fundCluster",
        "office": "office",
        "pr_number": "prNumber",
        "date": "date",
        "responsibility_center_code": "responsibilityCenterCode",
        "purpose": "purpose",
        "requested_by": "requestedBy",
        "approved_by": "approvedBy",
    }.items():
        meta = field_meta.get(target, {})
        confidence_100 = float(meta.get("confidence", 0.0) or 0.0)
        validation_fields[legacy_key] = {
            "value": meta.get("value", ""),
            "confidence": confidence_100 / 100.0 if confidence_100 > 1 else confidence_100,
            "needs_review": bool(meta.get("needs_review", False)),
        }

    for idx, item in enumerate(mapped_items, start=1):
        validation_fields[f"item_{idx}"] = {
            "value": item.get("description", ""),
            "confidence": float(item.get("confidence", 0.0) or 0.0) / 100.0,
            "needs_review": bool(item.get("needs_review", False)),
        }

    entity_name = pick("entity_name", "entityName")
    fund_cluster = _normalize_code_like(pick("fund_cluster", "fundCluster"), allow_dash=False)
    office = pick("office", "officeSection")
    pr_number = _normalize_code_like(pick("pr_number", "prNumber"), allow_dash=True)
    date = pick("date", "date")
    rcc = _normalize_code_like(pick("responsibility_center_code", "responsibilityCenterCode"), allow_dash=True)
    purpose = pick("purpose", "purpose")
    requested_by = pick_signatory("requested_by", "requested_by_name")
    budget_officer = pick_signatory("budget_officer", "funds_available_name")
    approved_by = pick_signatory("approved_by", "approved_by_name")
    twg = pick_signatory("twg", "twg_name")

    signatory_designations = structured.get("signatory_designations", {}) or {}
    signatory_names = structured.get("signatory_names", {}) or {}

    def choose_designation(key: str, selected_name: str, fallback_key: str) -> str:
        section_name = str(signatory_names.get(key, "") or "").strip().lower()
        section_designation = str(signatory_designations.get(key, "") or "").strip()
        selected_norm = str(selected_name or "").strip().lower()

        if section_designation and section_name and selected_norm and section_name in selected_norm:
            return section_designation
        return str(fallback.get(fallback_key, "") or "")

    requested_designation = choose_designation("requested_by", requested_by, "requested_by_designation")
    budget_designation = choose_designation("budget_officer", budget_officer, "funds_available_designation")
    approved_designation = choose_designation("approved_by", approved_by, "approved_by_designation")
    twg_designation = choose_designation("twg", twg, "twg_designation")

    return {
        "header": {
            "entityName": entity_name,
            "fundCluster": fund_cluster,
            "office": office,
            "prNumber": pr_number,
            "date": date,
            "responsibilityCenterCode": rcc,
        },
        "items": legacy_items,
        "footer": {
            "purpose": purpose,
            "requestedBy": requested_by,
            "approvedBy": approved_by,
        },
        "purpose": purpose,
        "requestedBy": {"name": requested_by, "designation": requested_designation},
        "approvedBy": {"name": approved_by, "designation": approved_designation},
        "validation": {
            "fields": validation_fields,
            "lowConfidenceThreshold": 0.85,
        },
        "raw_text": fallback.get("raw_text", ""),
        "requested_items": mapped_items,
        "entityName": entity_name,
        "fundCluster": fund_cluster,
        "officeSection": office,
        "prNumber": pr_number,
        "date": date,
        "responsibilityCenterCode": rcc,
        "requested_by_name": requested_by,
        "requested_by_designation": requested_designation,
        "funds_available_name": budget_officer,
        "funds_available_designation": budget_designation,
        "approved_by_name": approved_by,
        "approved_by_designation": approved_designation,
        "twg_name": twg,
        "twg_designation": twg_designation,
        "grand_total": _compute_total(mapped_items),
        "structured_extraction": structured,
    }


def parse_purchase_request(
    raw_text: str,
    layout: Dict[str, Any] | None = None,
    textract_blocks: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    legacy_result = PurchaseRequestParser().parse(raw_text, layout)

    if not textract_blocks:
        logger.warning("FALLBACK parser used: no Textract blocks provided")
        return legacy_result

    try:
        structured = parse_ctu_purchase_request(textract_blocks)
    except Exception:
        logger.exception("Structured Textract parsing failed; using legacy parser fallback")
        return legacy_result

    structured_result = _map_structured_to_legacy(structured, legacy_result)

    # Section fallback: keep structured-first, fill gaps from legacy when needed.
    if not structured_result.get("requested_items"):
        logger.warning("FALLBACK items section used from legacy parser")
        structured_result["requested_items"] = legacy_result.get("requested_items", [])
        structured_result["items"] = legacy_result.get("items", [])

    for key in [
        "entityName",
        "fundCluster",
        "officeSection",
        "prNumber",
        "date",
        "responsibilityCenterCode",
        "purpose",
        "requested_by_name",
        "funds_available_name",
        "approved_by_name",
        "twg_name",
    ]:
        if not structured_result.get(key):
            legacy_value = legacy_result.get(key, "")
            if legacy_value and not _is_effectively_blank(str(legacy_value)):
                logger.warning("FALLBACK field section used for %s", key)
                structured_result[key] = legacy_value
            else:
                structured_result[key] = structured_result.get(key, "")

    logger.info(
        "PR extraction complete: structured_items=%s fallback_items=%s",
        len(structured_result.get("requested_items") or []),
        len(legacy_result.get("requested_items") or []),
    )
    return structured_result

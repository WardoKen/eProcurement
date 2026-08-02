import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from ocr.purchase_request_parser import parse_purchase_request as _parse_purchase_request


def normalize_text(value: str) -> str:
    """Normalize whitespace in text."""
    return re.sub(r'\s+', ' ', (value or '')).strip()


def normalize_multiline_text(value: str) -> str:
    """Preserve line breaks in multiline text while removing blank lines."""
    if not value:
        return ''

    return '\n'.join(line.strip() for line in str(value).splitlines() if line and line.strip())


def _is_underscore_line(s: str) -> bool:
    s = s.strip()
    return bool(s) and all(ch in '_- ' for ch in s)


def extract_signature_block(lines: List[str], section_keywords: List[str]) -> tuple[str, str]:
    """Extract printed name and designation from a signature block."""
    lowered_keywords = [keyword.lower() for keyword in section_keywords]

    for idx, line in enumerate(lines):
        low = line.strip().lower()
        if not any(keyword in low for keyword in lowered_keywords):
            continue

        block_lines = []
        for j in range(idx + 1, min(len(lines), idx + 12)):
            cand = lines[j].strip()
            if not cand or _is_underscore_line(cand):
                continue

            next_low = cand.lower()
            if any(keyword in next_low for keyword in lowered_keywords):
                if not any(keyword in next_low for keyword in [kw for kw in lowered_keywords if kw != 'technical working group']):
                    break

            if re.search(r'(requested by|funds available|approved by|technical working group|specifications verified)', next_low):
                if not any(keyword in next_low for keyword in lowered_keywords):
                    break

            block_lines.append(cand)

        name_value = ''
        designation_value = ''
        for block_line in block_lines:
            if not name_value:
                printed_match = re.match(r'^(?:printed\s+name|name)\s*[:\-]?\s*(.+)$', block_line, re.I)
                if printed_match and printed_match.group(1).strip():
                    name_value = normalize_text(printed_match.group(1))
                    continue

                if re.fullmatch(r'[A-Z][A-Z0-9 .,&/()-]+', block_line) and len(block_line.split()) >= 2:
                    if re.search(r'[A-Z]', block_line) and not re.search(r'^(?:designation|position|title)\b', block_line, re.I):
                        name_value = normalize_text(block_line)
                        continue

            if not designation_value:
                designation_match = re.match(r'^(?:designation|position|title)\s*[:\-]?\s*(.+)$', block_line, re.I)
                if designation_match:
                    captured = designation_match.group(1).strip()
                    if captured and captured not in {':', '-'}:
                        designation_value = normalize_text(captured)
                        continue

                if not re.match(r'^(?:printed\s+name|name|designation|position|title)\b', block_line, re.I):
                    if name_value and (re.search(r'(twg|electrical|mechanical|director|officer|engineer|committee|chair|member)', block_line, re.I) or len(block_line.split()) <= 6):
                        designation_value = normalize_text(block_line)
                        break

        if name_value or designation_value:
            return name_value, designation_value

    return '', ''


def extract_requested_items(lines: List[str]) -> tuple[List[Dict[str, Any]], str]:
    """Extract requested item rows from OCR text using footer markers and numeric values."""
    footer_indices = [idx for idx, line in enumerate(lines) if re.search(r'nothing follows', line, re.I)]
    items: List[Dict[str, Any]] = []

    for marker_idx in footer_indices:
        header_idx = -1
        for prev_idx in range(marker_idx - 1, -1, -1):
            if re.search(r'item\s+description', lines[prev_idx], re.I):
                header_idx = prev_idx
                break

        start_idx = header_idx + 1 if header_idx >= 0 else None
        if start_idx is None:
            for prev_idx in range(marker_idx - 1, -1, -1):
                low = lines[prev_idx].strip().lower()
                if re.fullmatch(r'(purpose|particulars|description|item description|item|stock no|unit|quantity|unit cost|total cost)\s*[:\-]?', low):
                    start_idx = prev_idx + 1
                    break
            if start_idx is None:
                for prev_idx in range(marker_idx - 1, -1, -1):
                    low = lines[prev_idx].strip().lower()
                    if low in {'purpose', 'particulars', 'description', 'item description', 'item'}:
                        start_idx = prev_idx + 1
                        break
            if start_idx is None:
                start_idx = max(0, marker_idx - 20)

        description_lines: List[str] = []
        metadata_lines: List[str] = []

        for j in range(start_idx, marker_idx):
            raw_line = lines[j].strip()
            if not raw_line or _is_underscore_line(raw_line):
                continue
            if re.search(r'^(stock\s*no\.?|unit|item\s+description|quantity|unit\s*cost|total\s*cost)\b', raw_line, re.I):
                continue
            if re.search(r'nothing follows', raw_line, re.I):
                continue
            if re.fullmatch(r'\*{3,}.*', raw_line):
                continue
            if re.fullmatch(r'\d+(?:,\d{3})*(?:\.\d+)?', raw_line.replace(' ', '')):
                continue
            description_lines.append(raw_line)
            metadata_lines.append(raw_line)

        description = normalize_multiline_text('\n'.join(description_lines))

        values: List[str] = []
        for j in range(marker_idx + 1, min(len(lines), marker_idx + 8)):
            raw_line = lines[j].strip()
            if not raw_line or _is_underscore_line(raw_line):
                continue
            if re.search(r'nothing follows', raw_line, re.I):
                continue
            if re.fullmatch(r'\*{3,}.*', raw_line):
                continue
            if re.fullmatch(r'-{1,}|–|—', raw_line):
                continue
            if re.search(r'\d', raw_line):
                values.append(raw_line)

        quantity = ''
        price_candidates: List[str] = []
        for value in values:
            clean_value = value.replace(',', '').replace(' ', '')
            if re.fullmatch(r'\d+', clean_value):
                if not quantity:
                    quantity = value
                else:
                    price_candidates.append(value)
            elif re.fullmatch(r'\d+\.\d+', clean_value):
                price_candidates.append(value)

        if not price_candidates and values:
            price_candidates = values

        unit_cost = price_candidates[0] if len(price_candidates) >= 1 else ''
        total_cost = price_candidates[1] if len(price_candidates) >= 2 else unit_cost
        grand_total = price_candidates[-1] if price_candidates else ''

        stock_no = ''
        unit = ''
        for candidate in metadata_lines[:6]:
            stock_match = re.match(r'^stock\s*no\.?\s*[:\-]?\s*(.+)$', candidate, re.I)
            if stock_match:
                stock_no = normalize_text(stock_match.group(1))
                continue
            unit_match = re.match(r'^unit\s*[:\-]?\s*(.+)$', candidate, re.I)
            if unit_match:
                unit = normalize_text(unit_match.group(1))
                continue

        if description or quantity or unit_cost or total_cost or grand_total:
            items.append({
                'stock_no': stock_no,
                'unit': unit,
                'description': description,
                'quantity': quantity,
                'unit_cost': unit_cost,
                'total_cost': total_cost,
            })

    grand_total = items[-1].get('total_cost', '') if items else ''
    return items, grand_total


def extract_multiline_field(lines: List[str], start_idx: int, known_labels: List[str]) -> tuple[Optional[str], int]:
    """
    Extract a multiline field starting from a given index.
    Returns (text, next_index) where next_index is the line after the field ends.
    """
    field_lines = []
    current_idx = start_idx + 1

    # Regex pattern for known field labels
    label_pattern = '|'.join(re.escape(label) for label in known_labels)

    while current_idx < len(lines):
        line = lines[current_idx].strip()
        if not line:
            current_idx += 1
            continue

        # Check if this line starts a new field (contains a known label)
        if re.match(rf'^({label_pattern})\s*[:\-]?', line, re.I):
            break

        field_lines.append(line)
        current_idx += 1

    text = ' '.join(field_lines) if field_lines else ''
    return (normalize_text(text) if text else '', current_idx)


def extract_single_line_field(text: str, labels: List[str], fallback_pattern: Optional[str] = None) -> str:
    """
    Extract a single-line field using label matching.

    Args:
        text: Full source text to search
        labels: List of possible field labels
        fallback_pattern: Regex pattern to use if label matching fails

    Returns:
        Extracted value or empty string
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Try to match lines starting with one of the labels
    label_pattern = '|'.join(re.escape(label) for label in labels)
    for line in lines:
        match = re.match(rf'^({label_pattern})\s*[:\-]?\s*(.+)$', line, re.I)
        if match:
            return normalize_text(match.group(2))

    # Try fallback pattern
    if fallback_pattern:
        match = re.search(fallback_pattern, text, re.I)
        if match:
            return normalize_text(match.group(1))

    return ''


def parse_date_formats(date_str: str) -> str:
    """
    Parse various date formats and return YYYY-MM-DD.

    Supports:
    - MM/DD/YYYY (06/15/2026)
    - M/D/YYYY (6/15/2026)
    - YYYY-MM-DD (2026-06-15)
    - Month D, YYYY (June 15, 2026)
    - D Month, YYYY (15 June, 2026)
    """
    if not date_str:
        return ''

    date_str = date_str.strip()

    # Try various date patterns
    patterns = [
        # MM/DD/YYYY or M/D/YYYY
        (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: f"{m.group(3)}-{m.group(1):0>2}-{m.group(2):0>2}"),
        # YYYY-MM-DD
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: f"{m.group(1)}-{m.group(2):0>2}-{m.group(3):0>2}"),
        # Month D, YYYY or D Month YYYY
        (r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', parse_month_day_year),
        (r'(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})', parse_day_month_year),
    ]

    for pattern, formatter in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                if callable(formatter):
                    return formatter(match)
                else:
                    return formatter
            except (ValueError, IndexError):
                continue

    return ''


def parse_month_day_year(match) -> str:
    """Parse 'Month D, YYYY' format."""
    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    month_name = match.group(1).lower()
    if month_name in months:
        month = months[month_name]
        day = int(match.group(2))
        year = int(match.group(3))
        return f"{year}-{month:02d}-{day:02d}"
    return ''


def parse_day_month_year(match) -> str:
    """Parse 'D Month YYYY' format."""
    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    day = int(match.group(1))
    month_name = match.group(2).lower()
    if month_name in months:
        month = months[month_name]
        year = int(match.group(3))
        return f"{year}-{month:02d}-{day:02d}"
    return ''


def normalize_pr_number(pr_num: str) -> str:
    """
    Normalize PR number to YYYY-MM-NNN format.

    Accepts:
    - 2026-01-010
    - 202601010
    - 2026/01/010
    - etc.
    """
    if not pr_num:
        return ''

    # Extract only digits and hyphens
    cleaned = re.sub(r'[^\d\-]', '', pr_num.strip())

    # Try to match YYYY-MM-NNN
    match = re.match(r'^(\d{4})-?(\d{2})-?(\d{3})$', cleaned)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    return pr_num.strip()


def parse_purchase_request(raw_text: str) -> Dict[str, Any]:
    """Delegate to the modular purchase request parser."""
    return _parse_purchase_request(raw_text)


def get_empty_fields() -> Dict[str, Any]:
    """Return a dictionary with all PR fields initialized to empty strings."""
    return {
        'entityName': '',
        'fundCluster': '',
        'officeSection': '',
        'prNumber': '',
        'date': '',
        'responsibilityCenterCode': '',
        'purpose': '',
        'requested_by_name': '',
        'requested_by_designation': '',
        'funds_available_name': '',
        'funds_available_designation': '',
        'approved_by_name': '',
        'approved_by_designation': '',
        'twg_name': '',
        'twg_designation': '',
        'requested_items': [],
        'grand_total': '',
    }

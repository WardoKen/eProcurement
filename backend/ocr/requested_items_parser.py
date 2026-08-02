import re
from typing import Dict, List


class RequestedItemsParser:
    def __init__(self):
        self._item_header = re.compile(r'^(item description|stock/property no\.|unit|quantity|unit cost|total cost)$', re.I)

    def parse(self, lines: List[str]) -> List[Dict[str, str]]:
        cleaned = self._normalize_lines(lines)
        items: List[Dict[str, str]] = []
        current: Dict[str, str] | None = None
        description_lines: List[str] = []
        in_item_section = False

        for line in cleaned:
            low = line.lower().strip()
            # start item section when we see the header anywhere on the line
            if 'item description' in low:
                if current and (description_lines or current['quantity'] or current['unit_cost'] or current['total_cost']):
                    current['description'] = self._join_description(description_lines)
                    items.append(current)
                current = {'description': '', 'quantity': '', 'unit_cost': '', 'total_cost': ''}
                description_lines = []
                in_item_section = True
                continue

            if not in_item_section:
                continue

            if self._looks_like_section_header(low):
                if current and (description_lines or current['quantity'] or current['unit_cost'] or current['total_cost']):
                    current['description'] = self._join_description(description_lines)
                    items.append(current)
                break

            if self._is_header_label(low):
                continue

            if current is None:
                current = {'description': '', 'quantity': '', 'unit_cost': '', 'total_cost': ''}

            # Determine numeric characteristics
            clean_digits = re.sub(r'[^0-9\.]', '', line)
            is_numeric = self._is_numeric_line(line)
            is_currency = self._is_currency_line(line) or (is_numeric and len(clean_digits) >= 4) or ('.' in line and is_numeric)

            # Quantity should be small integers (1-3 digits typically)
            if is_numeric and not is_currency and not current['quantity']:
                current['quantity'] = self._clean_number(line)
                continue

            # Prefer currency-like lines for unit and total cost
            if is_currency and not current['unit_cost']:
                current['unit_cost'] = self._clean_number(line)
                continue

            if is_currency and current['unit_cost'] and not current['total_cost']:
                current['total_cost'] = self._clean_number(line)
                continue

            description_lines.append(line.strip())

            # If a description looks like it begins with 'supply' start description from here
            if 'supply' in low and 'delivery' in low:
                # reset earlier headers and start description at this line
                description_lines = [line.strip()]
                continue

            # skip explicit footer markers but continue scanning numeric rows that follow
            if 'nothing follows' in low:
                # don't include this in description; allow following numeric rows to be parsed
                continue

        if current and (description_lines or current['quantity'] or current['unit_cost'] or current['total_cost']):
            current['description'] = self._join_description(description_lines)
            items.append(current)

        return [self._normalize_item(item) for item in items if item.get('description') or item.get('quantity') or item.get('unit_cost') or item.get('total_cost')]

    def _normalize_lines(self, lines: List[str]) -> List[str]:
        normalized: List[str] = []
        for line in lines:
            cleaned = re.sub(r'\s+', ' ', line).strip()
            if cleaned:
                normalized.append(cleaned)
        return normalized

    def _is_numeric_line(self, value: str) -> bool:
        # reject lines that contain alphabetic characters
        if re.search(r'[A-Za-z]', value):
            return False
        cleaned = value.replace(',', '').strip()
        # allow optional leading hyphen or dash
        return bool(re.fullmatch(r'-?\d+(?:\.\d+)?', cleaned))

    def _is_currency_line(self, value: str) -> bool:
        s = value.replace(' ', '').strip()
        # Reject lines containing alphabetic characters (e.g., 'V', 'Hz')
        if re.search(r'[A-Za-z]', value):
            return False
        # If the line includes thousands separators or decimals, treat as currency
        if ',' in s or '.' in s:
            return bool(re.fullmatch(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?', s))
        # Otherwise, only treat as currency if it's a long digit sequence (>=4 digits)
        digits = re.sub(r'\D', '', s)
        return bool(digits) and len(digits) >= 4

    def _is_header_label(self, value: str) -> bool:
        return bool(re.fullmatch(r'(stock/property no\.|unit|item description|quantity|unit cost|total cost)', value))

    def _looks_like_section_header(self, value: str) -> bool:
        return any(
            re.fullmatch(label, value)
            for label in ['purpose', 'requested by', 'funds available', 'approved by', 'specifications verified by technical working group']
        )

    def _clean_number(self, value: str) -> str:
        raw = value.replace(',', '').strip()
        if re.fullmatch(r'\d+(?:\.\d+)?', raw):
            return value.strip()
        return raw

    def _join_description(self, lines: List[str]) -> str:
        cleaned_lines = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            low = s.lower()
            # skip footer markers and decorative lines
            if 'nothing follows' in low:
                continue
            if re.fullmatch(r'\*{3,}.*', s) or re.fullmatch(r'[-_]{2,}', s) or set(s) <= set('-_ '):
                continue
            cleaned_lines.append(s)
        return ' '.join(cleaned_lines)

    def _normalize_item(self, item: Dict[str, str]) -> Dict[str, str]:
        description = (item.get('description') or '').strip()
        quantity = (item.get('quantity') or '').strip()
        unit_cost = (item.get('unit_cost') or '').strip()
        total_cost = (item.get('total_cost') or '').strip()
        return {
            'description': description,
            'quantity': quantity,
            'unit_cost': unit_cost,
            'total_cost': total_cost,
        }

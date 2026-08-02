import re
from typing import Dict, List


class HeaderParser:
    def __init__(self, markers: Dict[str, str] | None = None):
        self.markers = markers or {}

    def parse(self, lines: List[str]) -> Dict[str, str]:
        fields = {
            'entityName': self._find_label_value(['Entity Name', 'Entity', 'Agency Name', 'Agency', 'Department Name', 'Department'], lines),
            'fundCluster': self._find_label_value(['Fund Cluster', 'Cluster'], lines),
            'officeSection': self._find_label_value(['Office/Section', 'Office / Section', 'Office', 'Section'], lines),
            'prNumber': self._normalize_pr_number(self._find_label_value(['PR No', 'P.R. No', 'PR Number', 'Purchase Request No', 'PR. No'], lines)),
            'date': self._parse_date_formats(self._find_label_value(['Date', 'Date Prepared', 'Date of PR'], lines)),
            'responsibilityCenterCode': self._find_label_value(['Responsibility Center Code', 'RCC', 'Responsibility Center', 'Cost Center'], lines),
        }
        return fields

    def _find_label_value(self, labels: List[str], lines: List[str]) -> str:
        label_re = re.compile(r'(' + '|'.join(re.escape(label) for label in labels) + r')', re.I)
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # match label at line start with optional value after colon
            match = re.match(rf'^\s*(?:' + '|'.join(re.escape(label) for label in labels) + r')\s*[:\-]?\s*(.*)$', stripped, re.I)
            if match:
                val = match.group(1).strip()
                if val:
                    return self._clean_value(val)
                # value is on following non-empty line(s)
                for j in range(idx + 1, min(idx + 4, len(lines))):
                    nxt = lines[j].strip()
                    if not nxt:
                        continue
                    # skip underline/placeholder lines
                    if re.fullmatch(r'[_\-]{3,}', nxt) or set(nxt) <= set('_- '):
                        continue
                    return self._clean_value(nxt)
            # fallback: label appears somewhere in the line with a colon
            if label_re.search(stripped) and ':' in stripped:
                parts = stripped.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    return self._clean_value(parts[1])
        return ''

    def _clean_value(self, value: str) -> str:
        value = (value or '').strip()
        value = re.sub(r'^[\s\.:\-]+', '', value)
        value = re.sub(r'[\s\.:\-_]+$', '', value)
        return re.sub(r'\s+', ' ', value).strip()

    def _normalize_pr_number(self, pr_num: str) -> str:
        if not pr_num:
            return ''
        cleaned = re.sub(r'[^\d\-]', '', pr_num.strip())
        match = re.match(r'^(\d{4})-?(\d{2})-?(\d{3})$', cleaned)
        if match:
            return f'{match.group(1)}-{match.group(2)}-{match.group(3)}'
        return pr_num.strip()

    def _parse_date_formats(self, date_str: str) -> str:
        if not date_str:
            return ''
        patterns = [
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', self._parse_mdY),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', self._parse_yMd),
            (r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})', self._parse_month_day_year),
            (r'(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})', self._parse_day_month_year),
        ]
        for pattern, formatter in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return formatter(match)
                except ValueError:
                    continue
        return ''

    def _parse_mdY(self, match) -> str:
        return f'{match.group(3)}-{int(match.group(1)):02d}-{int(match.group(2)):02d}'

    def _parse_yMd(self, match) -> str:
        return f'{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}'

    def _parse_month_day_year(self, match) -> str:
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        }
        month = months.get(match.group(1).lower())
        if month is None:
            raise ValueError
        return f'{int(match.group(3))}-{month:02d}-{int(match.group(2)):02d}'

    def _parse_day_month_year(self, match) -> str:
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        }
        month = months.get(match.group(2).lower())
        if month is None:
            raise ValueError
        return f'{int(match.group(3))}-{month:02d}-{int(match.group(1)):02d}'

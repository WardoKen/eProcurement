import re
from typing import Dict, List


class SignatoriesParser:
    def parse(self, lines: List[str]) -> Dict[str, Dict[str, str]]:
        result = {
            'requested_by': {'name': '', 'designation': ''},
            'funds_available': {'name': '', 'designation': ''},
            'approved_by': {'name': '', 'designation': ''},
            'twg': {'name': '', 'designation': ''},
        }

        section = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            low = stripped.lower()
            # Detect section starts whether exact or with colon/inline value
            if 'requested by' in low:
                section = 'requested_by'
                # If inline value exists, capture it
                if ':' in stripped and stripped.split(':', 1)[1].strip():
                    val = stripped.split(':', 1)[1].strip()
                    # don't capture inline labels like 'Funds Available' as names
                    lowv = val.lower()
                    if not any(tok in lowv for tok in ('funds available', 'requested by', 'approved by', 'budget officer', 'printed name')):
                        result[section]['name'] = self._clean_value(val)
                continue
            if 'funds available' in low or 'budget officer' in low:
                section = 'funds_available'
                if ':' in stripped and stripped.split(':', 1)[1].strip():
                    val = stripped.split(':', 1)[1].strip()
                    lowv = val.lower()
                    if not any(tok in lowv for tok in ('requested by', 'requested', 'funds available', 'budget officer', 'printed name')):
                        result[section]['name'] = self._clean_value(val)
                continue
            if 'approved by' in low or low.startswith('approved'):
                section = 'approved_by'
                if ':' in stripped and stripped.split(':', 1)[1].strip():
                    val = stripped.split(':', 1)[1].strip()
                    lowv = val.lower()
                    if not any(tok in lowv for tok in ('requested by', 'funds available', 'approved by', 'printed name')):
                        result[section]['name'] = self._clean_value(val)
                continue
            if 'specifications verified' in low or 'technical working group' in low or 'twg' in low:
                section = 'twg'
                if ':' in stripped and stripped.split(':', 1)[1].strip():
                    val = stripped.split(':', 1)[1].strip()
                    lowv = val.lower()
                    if not any(tok in lowv for tok in ('requested by', 'funds available', 'approved by', 'printed name')):
                        result[section]['name'] = self._clean_value(val)
                continue

            if section is None:
                continue

            # Capture printed name or designation inline
            if re.match(r'^(printed\s+name|name)\s*[:\-]?\s*(.+)$', stripped, re.I):
                m = re.match(r'^(?:printed\s+name|name)\s*[:\-]?\s*(.+)$', stripped, re.I)
                result[section]['name'] = self._clean_value(m.group(1))
                continue

            if re.match(r'^(designation|position|title)\s*[:\-]?\s*(.+)$', stripped, re.I):
                m = re.match(r'^(?:designation|position|title)\s*[:\-]?\s*(.+)$', stripped, re.I)
                result[section]['designation'] = self._clean_value(m.group(1))
                continue

            # Fallbacks: if the section name not yet captured, accept capitalized lines
            # but ignore known label tokens (e.g., 'Funds Available', 'Requested by')
            label_tokens = {'requested by', 'funds available', 'approved by', 'printed name', 'designation', 'signature', 'specifications verified', 'technical working group', 'approved'}
            low_str = stripped.lower()
            if not result[section]['name'] and re.search(r'[A-Z]', stripped) and not any(tok in low_str for tok in label_tokens):
                # If multiple names appear on the same line, split by large punctuation or double spaces
                parts = re.split(r'\s{2,}|\s+\|\s+|\s+•\s+|,\s*', stripped)
                # choose the part that looks like a personal name (has at least 2 words)
                candidate = ''
                for p in parts:
                    if len(p.split()) >= 2 and re.search(r'[A-Za-z]', p):
                        candidate = p.strip()
                        break
                if not candidate and parts:
                    candidate = parts[0].strip()
                result[section]['name'] = self._clean_value(candidate)
                continue
            if not result[section]['designation'] and re.search(r'[A-Za-z]', stripped) and not any(tok in low_str for tok in label_tokens):
                result[section]['designation'] = self._clean_value(stripped)
                continue

        return result

    def _clean_value(self, value: str) -> str:
        value = (value or '').strip()
        value = re.sub(r'^[\s\.:\-]+', '', value)
        value = re.sub(r'[\s\.:\-_]+$', '', value)
        return re.sub(r'\s+', ' ', value).strip()

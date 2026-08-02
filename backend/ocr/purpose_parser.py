import re
from typing import List, Dict


class PurposeParser:
    def parse(self, lines: List[str]) -> str:
        start = self._find_section_index(lines, ['Purpose'])
        if start is None:
            return ''

        section_lines = lines[start + 1:]
        end = self._find_section_end(section_lines)
        content = section_lines[:end]
        return self._clean_text(content)

    def _find_section_index(self, lines: List[str], labels: List[str]) -> int | None:
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            low = stripped.lower()
            # Match label exactly or label with trailing colon/characters (e.g. 'Purpose:' or 'Purpose: Purchase of...')
            if any(re.fullmatch(label, stripped, re.I) or label.lower() in low for label in labels):
                return index
        return None

    def _find_section_end(self, lines: List[str]) -> int:
        for index, line in enumerate(lines):
            if self._looks_like_next_section(line):
                return index
        return len(lines)

    def _looks_like_next_section(self, line: str) -> bool:
        trimmed = line.strip()
        low = trimmed.lower()
        return any(
            re.fullmatch(label, trimmed, re.I) or label.lower() in low
            for label in ['Requested by', 'Funds Available', 'Approved by', 'Specifications verified by Technical Working Group']
        )

    def _clean_text(self, lines: List[str]) -> str:
        cleaned = [self._strip_label(line) for line in lines if line.strip()]
        return ' '.join(cleaned).strip()

    def _strip_label(self, line: str) -> str:
        return re.sub(r'^[\s\-:]+', '', line).strip()

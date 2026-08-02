from __future__ import annotations

from typing import Any, Dict


class ValidationService:
    def validate(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        validation = parsed.get("validation", {"fields": {}})
        fields = validation.get("fields", {})
        low_confidence = []
        for name, meta in fields.items():
            confidence = float(meta.get("confidence", 0.0) or 0.0)
            if confidence < 0.8:
                low_confidence.append({"field": name, "confidence": confidence})
        return {
            "lowConfidenceThreshold": 0.8,
            "lowConfidenceFields": low_confidence,
            "fields": fields,
        }

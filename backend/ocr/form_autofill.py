from __future__ import annotations

from typing import Any, Dict


class FormAutoFillService:
    def populate(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        header = parsed.get("header", {})
        return {
            "entityName": header.get("entityName", ""),
            "fundCluster": header.get("fundCluster", ""),
            "officeSection": header.get("office", ""),
            "prNumber": header.get("prNumber", ""),
            "date": header.get("date", ""),
            "responsibilityCenterCode": header.get("responsibilityCenterCode", ""),
            "purpose": parsed.get("purpose", ""),
            "requested_by_name": parsed.get("requestedBy", {}).get("name", ""),
            "requested_by_designation": parsed.get("requestedBy", {}).get("designation", ""),
            "approved_by_name": parsed.get("approvedBy", {}).get("name", ""),
            "approved_by_designation": parsed.get("approvedBy", {}).get("designation", ""),
            "requested_items": parsed.get("requested_items", []),
            "grand_total": parsed.get("grand_total", ""),
            "lineItems": [
                {
                    "stockPropertyNumber": item.get("stock_no", ""),
                    "unit": item.get("unit", ""),
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity", ""),
                    "unitCost": item.get("unit_cost", ""),
                    "totalCost": item.get("total_cost", ""),
                }
                for item in parsed.get("items", [])
            ],
        }

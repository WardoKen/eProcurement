from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import PurchaseRequest, PurchaseRequestItem


@dataclass
class Counters:
    prs_created: int = 0
    prs_updated: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_skipped: int = 0


def parse_date(value: object) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime(value: object) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("T", " ")
    normalized = normalized.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_decimal(value: object, default: str = "0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    cleaned = str(value).replace(",", "").strip()
    if not cleaned:
        return Decimal(default)
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal(default)


class Command(BaseCommand):
    help = "Migrate PurchaseRequest and PurchaseRequestItem records from legacy SQLite DB to current Django default DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=str(Path(settings.BASE_DIR) / "db.sqlite3"),
            help="Path to legacy SQLite database file (default: backend/db.sqlite3)",
        )
        parser.add_argument(
            "--clear-target",
            action="store_true",
            help="Delete existing PurchaseRequest and PurchaseRequestItem records in target DB before import.",
        )

    def handle(self, *args, **options):
        sqlite_path = Path(options["sqlite_path"]).resolve()
        clear_target = bool(options.get("clear_target"))

        if not sqlite_path.exists():
            raise CommandError(f"SQLite source not found: {sqlite_path}")

        counters = Counters()

        self.stdout.write(self.style.NOTICE(f"Source SQLite: {sqlite_path}"))
        self.stdout.write(self.style.NOTICE("Target DB: Django default connection"))

        conn = sqlite3.connect(str(sqlite_path))
        conn.row_factory = sqlite3.Row

        try:
            pr_rows = conn.execute("SELECT * FROM api_purchaserequest ORDER BY id ASC").fetchall()
            item_rows = conn.execute("SELECT * FROM api_purchaserequestitem ORDER BY id ASC").fetchall()
        except sqlite3.Error as exc:
            raise CommandError(f"Failed to read source SQLite tables: {exc}") from exc
        finally:
            conn.close()

        if not pr_rows:
            self.stdout.write(self.style.WARNING("No PurchaseRequest rows found in source SQLite."))
            return

        with transaction.atomic():
            if clear_target:
                deleted_items, _ = PurchaseRequestItem.objects.all().delete()
                deleted_prs, _ = PurchaseRequest.objects.all().delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleared target DB rows: purchase_request_items={deleted_items}, purchase_requests={deleted_prs}"
                    )
                )

            for row in pr_rows:
                row_dict = dict(row)
                defaults = {
                    "entity_name": row_dict.get("entity_name") or "",
                    "fund_cluster": row_dict.get("fund_cluster") or None,
                    "office_section": row_dict.get("office_section") or None,
                    "pr_no": row_dict.get("pr_no") or None,
                    "responsibility_center_code": row_dict.get("responsibility_center_code") or None,
                    "date": parse_date(row_dict.get("date")),
                    "purpose": row_dict.get("purpose") or None,
                    "requested_by": row_dict.get("requested_by") or None,
                    "funds_available_by": row_dict.get("funds_available_by") or None,
                    "approved_by": row_dict.get("approved_by") or None,
                    "twg_verified_by": row_dict.get("twg_verified_by") or None,
                    "grand_total": parse_decimal(row_dict.get("grand_total"), "0"),
                }

                obj, created = PurchaseRequest.objects.update_or_create(
                    id=row_dict["id"],
                    defaults=defaults,
                )

                created_at = parse_datetime(row_dict.get("created_at"))
                if created_at and obj.created_at != created_at:
                    PurchaseRequest.objects.filter(id=obj.id).update(created_at=created_at)

                if created:
                    counters.prs_created += 1
                else:
                    counters.prs_updated += 1

            existing_pr_ids = set(PurchaseRequest.objects.values_list("id", flat=True))

            for row in item_rows:
                row_dict = dict(row)
                pr_id = row_dict.get("purchase_request_id")
                if pr_id not in existing_pr_ids:
                    counters.items_skipped += 1
                    continue

                defaults = {
                    "purchase_request_id": pr_id,
                    "stock_property_no": row_dict.get("stock_property_no") or None,
                    "unit": row_dict.get("unit") or None,
                    "item_description": row_dict.get("item_description") or "",
                    "quantity": parse_decimal(row_dict.get("quantity"), "0"),
                    "unit_cost": parse_decimal(row_dict.get("unit_cost"), "0"),
                    "total_cost": parse_decimal(row_dict.get("total_cost"), "0"),
                }

                _, created = PurchaseRequestItem.objects.update_or_create(
                    id=row_dict["id"],
                    defaults=defaults,
                )

                if created:
                    counters.items_created += 1
                else:
                    counters.items_updated += 1

        self.stdout.write(self.style.SUCCESS("PR migration completed."))
        self.stdout.write(
            f"PurchaseRequest created={counters.prs_created}, updated={counters.prs_updated}"
        )
        self.stdout.write(
            f"PurchaseRequestItem created={counters.items_created}, updated={counters.items_updated}, skipped={counters.items_skipped}"
        )

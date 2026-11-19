"""Purchase Request change history.

Three parts:

* the **original snapshot** (``PurchaseRequest.original_extract_json``) -
  the PR as it came out of upload and extraction, written once at creation;
* the **edit log** (``PRAuditLog``) - one append-only row per field the BAC
  changed, plus item added/removed events, written by ``pr_update``;
* ``compute_changes`` - compares the current PR against the snapshot (not
  against the previous edit) and attaches each field's edit history.

Only data read off the PR document is tracked. ``category`` (set by the BAC
when grouping items for supplier matching), the derived totals and the
system-assigned ``pr_no`` are not.

Values are compared and stored as normalized strings (``normalize_value``)
so ``Decimal('10')`` vs ``'10.00'`` or ``date`` vs ``'2026-01-05'`` never
count as a change.
"""
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import PRAuditLog

SNAPSHOT_VERSION = 1

# (model field, label) - the PR header fields read off the document.
TRACKED_PR_FIELDS = [
    ('entity_name', 'Entity Name'),
    ('fund_cluster', 'Fund Cluster'),
    ('office_section', 'Office / Section'),
    ('responsibility_center_code', 'Responsibility Center Code'),
    ('date', 'Date'),
    ('purpose', 'Purpose'),
    ('requested_by', 'Requested By'),
    ('funds_available_by', 'Funds Available'),
    ('approved_by', 'Approved By'),
    ('twg_verified_by', 'Technical Working Group'),
]

TRACKED_ITEM_FIELDS = [
    ('stock_property_no', 'Stock/Property No.'),
    ('unit', 'Unit'),
    ('item_description', 'Description'),
    ('quantity', 'Quantity'),
    ('unit_cost', 'Unit Cost'),
]

PR_FIELD_LABELS = dict(TRACKED_PR_FIELDS)
ITEM_FIELD_LABELS = dict(TRACKED_ITEM_FIELDS)
_DECIMAL_ITEM_FIELDS = {'quantity', 'unit_cost'}


def normalize_value(value, field_name=''):
    """Canonical string form used for snapshots, log rows and comparisons."""
    if value is None:
        return ''
    if field_name in _DECIMAL_ITEM_FIELDS or isinstance(value, Decimal):
        try:
            return str(Decimal(str(value).replace(',', '') or '0').quantize(Decimal('0.01')))
        except (InvalidOperation, ValueError):
            return str(value).strip()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if field_name == 'date':
        text = str(value).strip()
        parsed = parse_date(text) if text else None
        return parsed.isoformat() if parsed else text
    return str(value).strip()


def pr_field_values(pr):
    return {name: normalize_value(getattr(pr, name), name) for name, _ in TRACKED_PR_FIELDS}


def item_field_values(item):
    return {name: normalize_value(getattr(item, name), name) for name, _ in TRACKED_ITEM_FIELDS}


def item_summary(values):
    """JSON text stored in old_value/new_value for item_added/item_removed."""
    return json.dumps({name: values.get(name, '') for name, _ in TRACKED_ITEM_FIELDS})


def file_sha256(path):
    """Hex SHA-256 of a file, or '' when it is missing/unreadable."""
    try:
        digest = hashlib.sha256()
        with open(Path(path), 'rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ''


def build_original_snapshot(pr, extraction=None):
    """The write-once baseline for ``pr``: its tracked values as created.

    ``pr`` and its line items must already be saved. In the End User path the
    upload review is read-only, so these values are the extraction exactly as
    reviewed. ``extraction`` is the raw parser output kept from the upload
    (or None when it was not available) - stored for reference only;
    comparisons use the normalized ``pr``/``items`` values.
    """
    items = list(pr.line_items.order_by('id'))
    return {
        'version': SNAPSHOT_VERSION,
        'captured_at': timezone.now().isoformat(),
        'pr': pr_field_values(pr),
        'items': {str(item.id): item_field_values(item) for item in items},
        'item_order': [item.id for item in items],
        'extraction': extraction,
    }


def log_edit(pr, user, reason, *, field_name, old_value, new_value, item_id=None,
             event_type=PRAuditLog.EVENT_FIELD_EDIT):
    return PRAuditLog.objects.create(
        pr=pr,
        item_id=item_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        event_type=event_type,
        edited_by=user,
        edited_by_username=getattr(user, 'username', '') or '',
        reason=reason,
    )


# Role names as shown to people (the Role table stores short keys).
ROLE_LABELS = {
    'admin': 'BAC Secretariat',
    'bac_chair': 'BAC Chair',
    'buyer': 'End User',
    'supplier': 'Supplier',
}


def _editor(log):
    """The account that made a logged edit: display name, username and role.

    ``edited_by_username`` is captured at write time, so the account stays
    identified even if the user is later renamed, deactivated or deleted."""
    user = log.edited_by
    username = log.edited_by_username or getattr(user, 'username', '') or ''
    if user is None:
        return {
            'name': username or 'Unknown account',
            'username': username,
            'role': '',
            'account_active': False,
        }
    role = getattr(user.role, 'name', '') if user.role_id else ''
    return {
        'name': user.full_name or user.username,
        'username': username,
        'role': ROLE_LABELS.get(role, role),
        'account_active': bool(user.is_active),
    }


def _editor_fields(log):
    editor = _editor(log)
    return {
        'by': editor['name'],
        'by_username': editor['username'],
        'by_role': editor['role'],
        'by_account_active': editor['account_active'],
    }


def _history_entry(log):
    return {
        'old': log.old_value,
        'new': log.new_value,
        **_editor_fields(log),
        'at': log.edited_at.isoformat(),
        'reason': log.reason,
    }


def _short(text, limit=60):
    text = (text or '').strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def compute_changes(pr):
    """The PR's change set, keyed ``"<item_id or 'pr'>:<field>"``.

    Each value is ``{original, current, history: [{old, new, by, at, reason}]}``.
    ``original`` comes from ``original_extract_json``; a field whose current
    value equals it (including one edited and later changed back) is left
    out. Items added during review use the values they were added with as
    their baseline. For legacy PRs with no snapshot, the first logged
    ``old`` value stands in as the original.

    Item added/removed events are returned separately in ``events``.
    """
    logs = list(pr.audit_logs.select_related('edited_by__role').order_by('edited_at', 'id'))
    snapshot = pr.original_extract_json if isinstance(pr.original_extract_json, dict) else None
    original_pr = (snapshot or {}).get('pr') or {}
    original_items = (snapshot or {}).get('items') or {}

    current_items = list(pr.line_items.order_by('id'))
    current_by_id = {str(item.id): item for item in current_items}
    position = {str(item.id): index + 1 for index, item in enumerate(current_items)}

    history = {}
    added_baseline = {}
    events = []
    for log in logs:
        item_key = str(log.item_id) if log.item_id else 'pr'
        if log.event_type == PRAuditLog.EVENT_FIELD_EDIT:
            history.setdefault(f'{item_key}:{log.field_name}', []).append(log)
            continue
        raw = log.new_value if log.event_type == PRAuditLog.EVENT_ITEM_ADDED else log.old_value
        try:
            values = json.loads(raw or '{}')
        except (TypeError, ValueError):
            values = {}
        if log.event_type == PRAuditLog.EVENT_ITEM_ADDED and item_key not in added_baseline:
            added_baseline[item_key] = values
        events.append({
            'type': log.event_type,
            'item_id': log.item_id,
            'item_label': _short(values.get('item_description')) or f'Item {log.item_id}',
            'value': values,
            **_editor_fields(log),
            'at': log.edited_at.isoformat(),
            'reason': log.reason,
        })

    changes = {}

    def consider(key, *, field, label, item_id, original, current, item_label=None):
        steps = history.get(key, [])
        if original is None:
            if not steps:
                return
            original = steps[0].old_value or ''
        if original == current:
            return
        changes[key] = {
            'field': field,
            'label': label,
            'item_id': item_id,
            'item_position': position.get(str(item_id)) if item_id else None,
            'item_label': item_label,
            'original': original,
            'current': current,
            'history': [_history_entry(step) for step in steps],
        }

    current_pr = pr_field_values(pr)
    for field, label in TRACKED_PR_FIELDS:
        consider(
            f'pr:{field}', field=field, label=label, item_id=None,
            original=original_pr.get(field) if snapshot else None,
            current=current_pr[field],
        )

    for item_key, item in current_by_id.items():
        current = item_field_values(item)
        baseline = original_items.get(item_key) or added_baseline.get(item_key)
        for field, label in TRACKED_ITEM_FIELDS:
            consider(
                f'{item_key}:{field}', field=field,
                label=f'Item {position[item_key]} · {label}', item_id=item.id,
                original=baseline.get(field) if baseline else None,
                current=current[field],
                item_label=_short(item.item_description),
            )

    # Every account that edited this PR, in order of their first edit, with
    # their edit count and latest edit - for "Edited by ..." summaries.
    editors = {}
    for log in logs:
        key = log.edited_by_username or f'user-{log.edited_by_id}'
        entry = editors.get(key)
        if entry is None:
            entry = editors[key] = {**_editor(log), 'edit_count': 0, 'first_at': log.edited_at.isoformat()}
        entry['edit_count'] += 1
        entry['last_at'] = log.edited_at.isoformat()

    return {
        'original_available': snapshot is not None,
        'changes': changes,
        'events': events,
        'editors': list(editors.values()),
        'changed_count': len(changes) + len(events),
    }

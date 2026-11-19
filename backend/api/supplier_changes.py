"""Supplier account change log (``SupplierChangeLog``), for BAC review.

When a supplier edits their profile, changes categories or resubmits a
document - and especially when that sends an approved account back to
Pending Review - the BAC sees exactly what changed, by whom and when, next to
its own past decisions.

Callers pass one ``changed_at`` for every row of a single save so the rows
read as one change set.
"""
from django.utils import timezone

from .models import SupplierChangeLog

# Profile fields a supplier can edit, with the labels the BAC sees.
SUPPLIER_FIELD_LABELS = {
    'company_name': 'Company Name',
    'business_type': 'Business Type',
    'tin': 'TIN',
    'business_address': 'Address',
    'email': 'Email',
    'contact_phone': 'Phone',
    'contact_person': 'Contact Person',
    'nature_of_business': 'Nature of Business',
    'goods_services': 'Goods/Services',
    'categories': 'Categories',
    'status': 'Status',
}


def _text(value):
    return '' if value is None else str(value).strip()


def actor(request):
    """(user, username, role) of the request's signed-in user."""
    user = getattr(request, 'auth_user', None)
    return user, getattr(user, 'username', '') or '', getattr(request, 'auth_role', '') or ''


def record(supplier, request, event_type, *, field_name='', old_value='', new_value='', note='', changed_at=None):
    user, username, role = actor(request)
    return SupplierChangeLog.objects.create(
        supplier=supplier, event_type=event_type, field_name=field_name,
        old_value=_text(old_value), new_value=_text(new_value), note=note,
        changed_by=user, changed_by_username=username, changed_by_role=role,
        changed_at=changed_at or timezone.now(),
    )


def record_field_changes(supplier, request, before, after, changed_at):
    """One row per profile field whose value actually changed."""
    for field, old in before.items():
        new = after.get(field)
        if _text(old) != _text(new):
            record(supplier, request, SupplierChangeLog.EVENT_FIELD_EDIT,
                   field_name=field, old_value=old, new_value=new, changed_at=changed_at)


def record_category_change(supplier, request, old_names, new_names, changed_at):
    old_sorted, new_sorted = sorted(old_names), sorted(new_names)
    if old_sorted == new_sorted:
        return
    added = [name for name in new_sorted if name not in old_names]
    removed = [name for name in old_sorted if name not in new_names]
    parts = []
    if added:
        parts.append('Added: ' + ', '.join(added))
    if removed:
        parts.append('Removed: ' + ', '.join(removed))
    record(supplier, request, SupplierChangeLog.EVENT_CATEGORIES, field_name='categories',
           old_value=', '.join(old_sorted), new_value=', '.join(new_sorted),
           note='; '.join(parts), changed_at=changed_at)


def record_status_change(supplier, request, old_status, new_status, note='', changed_at=None):
    if _text(old_status) == _text(new_status):
        return
    record(supplier, request, SupplierChangeLog.EVENT_STATUS, field_name='status',
           old_value=old_status, new_value=new_status, note=note, changed_at=changed_at)


def changes_since_last_decision(supplier):
    """The supplier's own changes since the BAC's most recent status decision.

    Oldest first. These are what a Pending Review is waiting on, and what a
    following approval approves.
    """
    rows = SupplierChangeLog.objects.filter(supplier=supplier)
    last_decision = (
        rows.filter(event_type=SupplierChangeLog.EVENT_STATUS, changed_by_role='admin')
        .order_by('-changed_at', '-id').first()
    )
    if last_decision:
        rows = rows.filter(changed_at__gt=last_decision.changed_at)
    return list(rows.filter(changed_by_role='supplier').order_by('changed_at', 'id'))


def describe(row, document_label=lambda key: key.replace('_', ' ').title()) -> str:
    """One plain-text line for an email, e.g. "Contact Person: Rep -> New Rep"."""
    if row.event_type == SupplierChangeLog.EVENT_DOCUMENT:
        return f'Document resubmitted: {document_label(row.field_name)} ({row.new_value or "new file"})'
    label = SUPPLIER_FIELD_LABELS.get(row.field_name, row.field_name.replace('_', ' ').title())
    if row.event_type == SupplierChangeLog.EVENT_CATEGORIES and row.note:
        return f'{label}: {row.note}'
    return f'{label}: {row.old_value or "(blank)"} -> {row.new_value or "(blank)"}'


def serialize(supplier):
    """The supplier's change log, newest first."""
    rows = SupplierChangeLog.objects.filter(supplier=supplier).order_by('-changed_at', '-id')
    return [{
        'id': row.id,
        'event_type': row.event_type,
        'field_name': row.field_name,
        'field_label': SUPPLIER_FIELD_LABELS.get(row.field_name, row.field_name.replace('_', ' ').title()),
        'old_value': row.old_value,
        'new_value': row.new_value,
        'note': row.note,
        'changed_by': row.changed_by_username,
        'changed_by_role': row.changed_by_role,
        'changed_at': row.changed_at.isoformat(),
    } for row in rows]

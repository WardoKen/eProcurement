"""Procurement Activity Summary: a printable PDF of one period's activity.

Built only from what eProcure records. Each section counts records by the
date that matters for it:

* Purchase Requests - the date the PR was uploaded (``created_at``);
* RFQs - the date the RFQ was sent (``sent_at``);
* postings - the date of the post (``PRPostingLog.changed_at``);
* supplier registrations - the date the supplier registered;
* BAC supplier decisions - the date of the decision (``SupplierChangeLog``).

It reports counts, totals and durations only. Quotations are never compared
or ranked: evaluation and award are outside eProcure's scope. This is not the
GPPB Procurement Monitoring Report, which also covers award and contract.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.db.models import Count, Min, Q, Sum
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from api.models import (
    Category, PRPostingLog, PurchaseRequest, PurchaseRequestItem, Quotation, RFQ, Supplier,
    SupplierChangeLog,
)
from api.rfq.procurement_modes import normalize_procurement_mode

LOGO_PATH = Path(__file__).resolve().parent / 'assets' / 'eprocure-logo.png'

# The labels the BAC sees in the app (see prStatusMeta in src/App.jsx).
PR_STATUS_LABELS = [
    (PurchaseRequest.STATUS_UPLOADED, 'Submitted'),
    (PurchaseRequest.STATUS_IN_REVIEW, 'In Review'),
    (PurchaseRequest.STATUS_MATCHED, 'Matched'),
    (PurchaseRequest.STATUS_APPROVED, 'Completed'),
    (PurchaseRequest.STATUS_REJECTED, 'Rejected'),
]

# An RFQ counts as answered once the supplier uploads the completed RFQ or
# submits a quotation; both set this status (same rule as supplier scoring).
RESPONDED_STATUSES = (RFQ.STATUS_QUOTATION_RECEIVED, RFQ.STATUS_COMPLETED)

SUPPLIER_STATUS_ORDER = ['Pending Review', 'Pending', 'In Review', 'For Compliance', 'Approved', 'Rejected']

NOT_SPECIFIED = 'Not specified'


def peso(value) -> str:
    """xhtml2pdf's built-in fonts have no peso sign, so amounts read "Php 1,234.50"."""
    return f'Php {Decimal(value or 0):,.2f}'


def percent(part, whole) -> str:
    return f'{round(100 * part / whole)}%' if whole else '-'


def days(seconds_list) -> str:
    """Average of a list of durations in seconds: hours under a day, else days."""
    if not seconds_list:
        return '-'
    seconds = sum(seconds_list) / len(seconds_list)
    if seconds < 3600:
        return 'under 1 hour'
    if seconds < 86400:
        hours = round(seconds / 3600)
        return f'{hours} hour' + ('' if hours == 1 else 's')
    average = seconds / 86400
    return f'{average:.1f} day' + ('' if round(average, 1) == 1.0 else 's')


def _period(field, start, end) -> Q:
    q = Q()
    if start:
        q &= Q(**{f'{field}__gte': start})
    if end:
        q &= Q(**{f'{field}__lt': end})
    return q


def _purchase_requests(start, end):
    prs = PurchaseRequest.objects.filter(_period('created_at', start, end))
    totals = prs.aggregate(count=Count('id'), value=Sum('grand_total'))

    by_status_rows = {
        row['status']: row
        for row in prs.values('status').annotate(count=Count('id'), value=Sum('grand_total'))
    }
    by_status = [
        {'label': label, 'count': by_status_rows.get(code, {}).get('count', 0),
         'value': peso(by_status_rows.get(code, {}).get('value'))}
        for code, label in PR_STATUS_LABELS
    ]
    # Any status outside the known list is still shown, not dropped.
    known = {code for code, _ in PR_STATUS_LABELS}
    by_status += [
        {'label': code, 'count': row['count'], 'value': peso(row['value'])}
        for code, row in sorted(by_status_rows.items()) if code not in known
    ]

    by_office = [
        {'label': (row['office_section'] or '').strip() or NOT_SPECIFIED, 'count': row['count'],
         'value': peso(row['value'])}
        for row in prs.values('office_section').annotate(count=Count('id'), value=Sum('grand_total'))
        .order_by('-value', 'office_section')
    ]

    # Category is assigned per item, so a mixed PR counts under each of its
    # categories with that category's share of the value.
    by_category = [
        {'label': (row['category'] or '').strip() or 'Not yet categorised', 'prs': row['prs'],
         'items': row['items'], 'value': peso(row['value'])}
        for row in PurchaseRequestItem.objects.filter(purchase_request__in=prs)
        .values('category')
        .annotate(prs=Count('purchase_request', distinct=True), items=Count('id'), value=Sum('total_cost'))
        .order_by('-value', 'category')
    ]

    return prs, {
        'count': totals['count'] or 0,
        'value': peso(totals['value']),
        'numbered': prs.exclude(pr_no__isnull=True).exclude(pr_no='').count(),
        'by_status': by_status,
        'by_office': by_office,
        'by_category': by_category,
    }


def _rfqs(start, end, tz):
    rfqs = RFQ.objects.exclude(status=RFQ.STATUS_DRAFT).filter(_period('sent_at', start, end))
    sent = rfqs.count()
    responded = rfqs.filter(status__in=RESPONDED_STATUSES).count()
    quotations = Quotation.objects.filter(rfq__in=rfqs).exclude(status=Quotation.STATUS_DRAFT).count()

    modes = defaultdict(lambda: {'rfqs': 0, 'prs': set()})
    for mode, pr_id in rfqs.values_list('mode_of_procurement', 'purchase_request_id'):
        bucket = modes[normalize_procurement_mode(mode) or NOT_SPECIFIED]
        bucket['rfqs'] += 1
        bucket['prs'].add(pr_id)
    by_mode = sorted(
        ({'label': label, 'rfqs': data['rfqs'], 'prs': len(data['prs'])} for label, data in modes.items()),
        key=lambda row: (-row['rfqs'], row['label']),
    )

    per_pr = []
    for row in (
        rfqs.values('purchase_request_id', 'purchase_request__pr_no', 'purchase_request__office_section')
        .annotate(
            sent=Count('id'),
            responded=Count('id', filter=Q(status__in=RESPONDED_STATUSES)),
            manual=Count('id', filter=Q(delivery_method=RFQ.DELIVERY_MANUAL) | Q(supplier__isnull=True)),
        )
        .order_by('purchase_request__pr_no')
    ):
        per_pr.append({
            'pr_no': row['purchase_request__pr_no'] or f"PR-{row['purchase_request_id']}",
            'office': (row['purchase_request__office_section'] or '').strip() or NOT_SPECIFIED,
            'sent': row['sent'],
            'manual': row['manual'],
            'responded': row['responded'],
            'awaiting': row['sent'] - row['responded'],
            'rate': percent(row['responded'], row['sent']),
        })

    response_seconds = [
        (submitted - sent_at).total_seconds()
        for sent_at, submitted in rfqs.filter(status__in=RESPONDED_STATUSES, submitted_at__isnull=False)
        .values_list('sent_at', 'submitted_at')
        if submitted >= sent_at
    ]

    splitting = [
        {
            'rfq_no': rfq.rfq_no or f'RFQ {rfq.id}',
            'pr_no': rfq.purchase_request.pr_no or f'PR-{rfq.purchase_request_id}',
            'category': rfq.category.name if rfq.category_id else NOT_SPECIFIED,
            'by': rfq.splitting_justified_by_username or '-',
            'at': timezone.localtime(rfq.splitting_justified_at, tz).strftime('%Y-%m-%d')
            if rfq.splitting_justified_at else '-',
            'justification': _clip(rfq.splitting_justification, 220),
        }
        for rfq in rfqs.exclude(splitting_justification='')
        .select_related('purchase_request', 'category').order_by('sent_at', 'id')
    ]

    return {
        'sent': sent,
        'prs': rfqs.values('purchase_request_id').distinct().count(),
        'responded': responded,
        'awaiting': rfqs.filter(status=RFQ.STATUS_SENT).count(),
        'rate': percent(responded, sent),
        'quotations': quotations,
        'by_mode': by_mode,
        'per_pr': per_pr,
        'avg_response': days(response_seconds),
        'response_count': len(response_seconds),
    }, splitting


def _postings(prs, start, end):
    """Time from upload to first posting (PRs uploaded in the period), and how
    long postings in the period stayed up before being taken down."""
    first_posts = {
        row['pr_id']: row['first']
        for row in PRPostingLog.objects.filter(pr__in=prs, action=PRPostingLog.ACTION_POSTED)
        .values('pr_id').annotate(first=Min('changed_at'))
    }
    to_post_seconds = [
        (first_posts[pr_id] - created).total_seconds()
        for pr_id, created in prs.values_list('id', 'created_at')
        if pr_id in first_posts and first_posts[pr_id] >= created
    ]

    # Pair each post made in the period with the take-down that follows it
    # (which may fall after the period), per PR.
    logs = defaultdict(list)
    for pr_id, action, at in (
        PRPostingLog.objects.order_by('changed_at', 'id').values_list('pr_id', 'action', 'changed_at')
    ):
        logs[pr_id].append((action, at))
    posted_durations = []
    for entries in logs.values():
        opened = None
        for action, at in entries:
            if action == PRPostingLog.ACTION_POSTED:
                in_window = (not start or at >= start) and (not end or at < end)
                opened = at if in_window else None
            elif opened is not None:
                posted_durations.append((at - opened).total_seconds())
                opened = None

    posts_in_period = PRPostingLog.objects.filter(
        _period('changed_at', start, end), action=PRPostingLog.ACTION_POSTED,
    ).count()
    return {
        'avg_to_post': days(to_post_seconds),
        'posted_count': len(to_post_seconds),
        'not_posted': prs.count() - len(to_post_seconds),
        'posts_in_period': posts_in_period,
        'avg_posted': days(posted_durations),
        'closed_postings': len(posted_durations),
        'currently_posted': PurchaseRequest.objects.filter(is_posted=True).count(),
    }


def _suppliers(start, end):
    registrations = Supplier.objects.filter(_period('created_at', start, end)).count()

    decisions = defaultdict(int)
    for new_status in SupplierChangeLog.objects.filter(
        _period('changed_at', start, end),
        event_type=SupplierChangeLog.EVENT_STATUS, changed_by_role='admin',
    ).values_list('new_value', flat=True):
        decisions[new_status or NOT_SPECIFIED] += 1
    decision_rows = [{'label': label, 'count': decisions[label]} for label in ('Approved', 'For Compliance', 'Rejected')]
    decision_rows += [{'label': label, 'count': count} for label, count in sorted(decisions.items())
                      if label not in ('Approved', 'For Compliance', 'Rejected')]

    current = defaultdict(int)
    for status in Supplier.objects.values_list('status', flat=True):
        current[status or 'Pending Review'] += 1
    current_rows = [{'label': s, 'count': current.pop(s)} for s in SUPPLIER_STATUS_ORDER if s in current]
    current_rows += [{'label': s, 'count': c} for s, c in sorted(current.items())]

    categories = list(
        Category.objects.annotate(
            approved=Count('supplier_categories', filter=Q(supplier_categories__supplier__status='Approved'),
                           distinct=True),
        ).values('name', 'approved').order_by('-approved', 'name')
    )
    covered = [{'label': row['name'], 'count': row['approved']} for row in categories if row['approved']]
    # Two category/count pairs per row keep a long list to half the length.
    half = (len(covered) + 1) // 2
    category_rows = [
        (covered[i], covered[i + half] if i + half < len(covered) else None) for i in range(half)
    ]

    return {
        'registrations': registrations,
        'decisions': decision_rows,
        'decision_total': sum(decisions.values()),
        'current': current_rows,
        'total': Supplier.objects.count(),
        'category_rows': category_rows,
        'categories_covered': len(covered),
        'categories_uncovered': len(categories) - len(covered),
    }


def _bac_verified_signatures(prs):
    """PRs whose required signatures the BAC verified by hand because the
    detector could not confirm them (see api/signature_review.py)."""
    rows = []
    for pr in prs.exclude(signature_confirmations=[]).order_by('created_at'):
        bac = [c for c in (pr.signature_confirmations or []) if c.get('confirmed_role') == 'bac']
        if bac:
            rows.append({
                'pr_no': pr.pr_no or f'PR-{pr.id}',
                'office': (pr.office_section or '').strip() or NOT_SPECIFIED,
                'signatures': ', '.join(c.get('label') or c.get('key') or '?' for c in bac),
                'by': ', '.join(sorted({c.get('confirmed_by') or '?' for c in bac})),
            })
    return rows


def _clip(text, limit):
    text = ' '.join((text or '').split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def build_summary(*, start, end, tz, period_label, generated_by):
    """Everything the template shows, for records in [start, end)."""
    prs, pr_section = _purchase_requests(start, end)
    rfq_section, splitting = _rfqs(start, end, tz)
    signature_flags = _bac_verified_signatures(prs)
    return {
        'title': 'Procurement Activity Summary',
        'period_label': period_label,
        'generated_at': timezone.localtime(timezone.now(), tz).strftime('%Y-%m-%d %H:%M'),
        'generated_by': generated_by,
        'logo_path': LOGO_PATH.as_posix() if LOGO_PATH.exists() else '',
        'pr': pr_section,
        'rfq': rfq_section,
        'timeliness': _postings(prs, start, end),
        'suppliers': _suppliers(start, end),
        'splitting': splitting,
        'signature_flags': signature_flags,
    }


def render_pdf(context) -> bytes:
    html = render_to_string('reports/procurement_summary.html', context)
    buffer = BytesIO()
    status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8')
    if status.err:
        raise ValueError('PDF generation failed.')
    return buffer.getvalue()

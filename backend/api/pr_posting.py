"""Explicit posting of Purchase Requests as procurement opportunities.

A PR becomes an opportunity only when the BAC posts it. Posted PRs appear on
the public Opportunities page and in the supplier portal (to category-matched
suppliers); unposted PRs appear in neither.

Rules:
* Only a PR at a postable status (``POSTABLE_STATUSES``) with at least one
  categorized line item can be posted - suppliers are matched by item
  category.
* Unposting needs a reason (``MIN_REASON_LENGTH`` characters or more).
* A posted PR whose status leaves the postable statuses is taken down
  automatically, with the status change as the reason
  (``unpost_if_ineligible``).
* Every post and unpost is recorded in the append-only ``PRPostingLog``.
"""
from django.db import transaction
from django.utils import timezone

from .models import PRPostingLog, PurchaseRequest

POSTABLE_STATUSES = {PurchaseRequest.STATUS_MATCHED, PurchaseRequest.STATUS_APPROVED}
MIN_REASON_LENGTH = 10

STATUS_LABELS = {
    PurchaseRequest.STATUS_UPLOADED: 'Submitted',
    PurchaseRequest.STATUS_IN_REVIEW: 'In Review',
    PurchaseRequest.STATUS_MATCHED: 'Matched',
    PurchaseRequest.STATUS_APPROVED: 'Completed',
    PurchaseRequest.STATUS_REJECTED: 'Rejected',
}


class PostingError(ValueError):
    """The requested post/unpost is not allowed; the message says why."""


def _actor(request):
    user = getattr(request, 'auth_user', None) if request is not None else None
    return user, getattr(user, 'username', '') or ''


def _log(pr, request, action, reason='', automatic=False):
    user, username = _actor(request)
    return PRPostingLog.objects.create(
        pr=pr, action=action, reason=reason, automatic=automatic,
        changed_by=user, changed_by_username=username,
    )


def has_categorized_item(pr) -> bool:
    return pr.line_items.exclude(category__isnull=True).exclude(category='').exists()


def post_problem(pr) -> str:
    """Why ``pr`` cannot be posted right now, or '' when it can."""
    if pr.is_posted:
        return 'This Purchase Request is already posted.'
    if pr.status not in POSTABLE_STATUSES:
        return (
            f'Only a Matched or Completed Purchase Request can be posted. '
            f'This one is {STATUS_LABELS.get(pr.status, pr.status)}.'
        )
    if not has_categorized_item(pr):
        return 'Assign a category to at least one line item before posting: suppliers are matched by item category.'
    return ''


def _locked(pr):
    """Re-read ``pr`` with a row lock, so two BAC users acting at once cannot
    both post (or both unpost) it."""
    return PurchaseRequest.objects.select_for_update().get(pk=pr.pk)


def post(pr, request):
    _, username = _actor(request)
    with transaction.atomic():
        pr = _locked(pr)
        problem = post_problem(pr)
        if problem:
            raise PostingError(problem)
        pr.is_posted = True
        pr.posted_at = timezone.now()
        pr.posted_by = username
        pr.save(update_fields=['is_posted', 'posted_at', 'posted_by'])
        _log(pr, request, PRPostingLog.ACTION_POSTED)


def _clear(pr):
    pr.is_posted = False
    pr.posted_at = None
    pr.posted_by = ''
    return ['is_posted', 'posted_at', 'posted_by']


def unpost(pr, request, reason):
    cleaned = ' '.join((reason or '').split())
    if len(cleaned) < MIN_REASON_LENGTH:
        raise PostingError(f'Enter a reason of at least {MIN_REASON_LENGTH} characters for taking this posting down.')
    with transaction.atomic():
        pr = _locked(pr)
        if not pr.is_posted:
            raise PostingError('This Purchase Request is not posted.')
        pr.save(update_fields=_clear(pr))
        _log(pr, request, PRPostingLog.ACTION_UNPOSTED, reason=cleaned)


def unpost_if_ineligible(pr, request):
    """Take a posted PR down when its new status can no longer be posted.

    Call after setting ``pr.status`` and before saving; returns the fields it
    changed for the caller's ``save(update_fields=...)``. The log row is
    written now, so call inside the caller's transaction.
    """
    if not pr.is_posted or pr.status in POSTABLE_STATUSES:
        return []
    fields = _clear(pr)
    _log(
        pr, request, PRPostingLog.ACTION_UNPOSTED, automatic=True,
        reason=f'Taken down automatically: status changed to {STATUS_LABELS.get(pr.status, pr.status)}.',
    )
    return fields


def serialize(pr):
    """The PR's posting state and history (newest first), for the BAC."""
    return {
        'is_posted': pr.is_posted,
        'posted_at': pr.posted_at.isoformat() if pr.posted_at else None,
        'posted_by': pr.posted_by,
        'can_post': not post_problem(pr),
        'post_problem': '' if pr.is_posted else post_problem(pr),
        'min_reason_length': MIN_REASON_LENGTH,
        'history': [{
            'id': row.id,
            'action': row.action,
            'reason': row.reason,
            'automatic': row.automatic,
            'changed_by': row.changed_by_username,
            'changed_at': row.changed_at.isoformat(),
        } for row in pr.posting_logs.order_by('-changed_at', '-id')],
    }

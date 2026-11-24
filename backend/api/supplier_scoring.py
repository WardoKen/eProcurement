"""Advisory ranking of category-matched suppliers.

Scoring runs only on suppliers that already passed the eligibility check in
``pr_supplier_match`` (approved, registered under the category, every required
document verified). It never excludes anyone: it orders the eligible list and
explains the order so the BAC can see why a supplier ranked where it did. The
BAC still decides who receives an RFQ.

Only data the system already collects is used - RFQ issue/response records,
submitted quotations, registered categories and the supplier's own
goods/services description. There is no vendor rating here.

Document currency is not scored: ``SupplierDocument`` records when a file was
uploaded but not when BAC verified it, and every eligible supplier already has
all required documents verified, so the factor cannot tell eligible suppliers
apart. Its share of the 100 points is spread over the factors below.
"""

import re
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .models import RFQ, Quotation, SupplierCategory

# --- Weights (points out of 100) -------------------------------------------
RESPONSIVENESS_WEIGHT = 40
QUOTATION_HISTORY_WEIGHT = 20
CATEGORY_FOCUS_WEIGHT = 25
ITEM_RELEVANCE_WEIGHT = 15

# --- Tuning ----------------------------------------------------------------
# Share of the responsiveness points given to a supplier with no RFQ history,
# so new suppliers sit in the middle rather than at the bottom.
NEUTRAL_RESPONSIVENESS = 0.5
# An unanswered RFQ sent within this many days is still open and is not
# counted against the supplier.
RESPONSE_GRACE_DAYS = 7
# Submitted quotations beyond this count earn no extra points.
QUOTATION_HISTORY_CAP = 5
# Category focus: full points for one registered category, minus this share
# for each additional category, never below the floor.
FOCUS_STEP_PER_EXTRA_CATEGORY = 0.2
FOCUS_FLOOR = 0.2

_RESPONDED_STATUSES = (RFQ.STATUS_QUOTATION_RECEIVED, RFQ.STATUS_COMPLETED)
_STOPWORDS = frozenset({
    'and', 'the', 'for', 'with', 'from', 'into', 'per', 'each', 'set', 'sets',
    'pcs', 'pc', 'piece', 'pieces', 'unit', 'units', 'lot', 'lots', 'item',
    'items', 'other', 'others', 'various', 'assorted', 'supply', 'supplies',
    'delivery', 'including', 'size', 'type', 'new', 'use',
})


def _keywords(text):
    """Lower-case content words of ``text`` with a naive plural strip."""
    words = set()
    for word in re.findall(r'[a-z]+', (text or '').lower()):
        if len(word) < 3 or word in _STOPWORDS:
            continue
        if len(word) > 3 and word.endswith('s') and not word.endswith('ss'):
            word = word[:-1]
        words.add(word)
    return words


def build_scoring_context(supplier_ids, items_by_category, exclude_pr_id=None, now=None):
    """Load every count the scorer needs in a fixed number of queries.

    ``items_by_category`` maps a category name to the item descriptions of
    that procurement group. RFQs and quotations on ``exclude_pr_id`` (the PR
    being matched) are left out so the ranking does not shift while the BAC
    is issuing RFQs for it.
    """
    supplier_ids = list(supplier_ids)
    now = now or timezone.now()
    grace_cutoff = now - timedelta(days=RESPONSE_GRACE_DAYS)

    rfqs = RFQ.objects.filter(supplier_id__in=supplier_ids).exclude(status=RFQ.STATUS_DRAFT)
    quotations = Quotation.objects.filter(supplier_id__in=supplier_ids).exclude(status=Quotation.STATUS_DRAFT)
    if exclude_pr_id is not None:
        rfqs = rfqs.exclude(purchase_request_id=exclude_pr_id)
        quotations = quotations.exclude(purchase_request_id=exclude_pr_id)

    responded_q = Q(submitted_at__isnull=False) | Q(status__in=_RESPONDED_STATUSES)
    still_open_q = ~responded_q & Q(sent_at__gt=grace_cutoff)
    rfq_stats = {
        row['supplier_id']: row
        for row in rfqs.values('supplier_id').annotate(
            issued=Count('id'),
            responded=Count('id', filter=responded_q),
            still_open=Count('id', filter=still_open_q),
        )
    }
    quotation_counts = dict(
        quotations.values('supplier_id').annotate(n=Count('id')).values_list('supplier_id', 'n')
    )
    category_counts = dict(
        SupplierCategory.objects.filter(supplier_id__in=supplier_ids)
        .values('supplier_id').annotate(n=Count('id')).values_list('supplier_id', 'n')
    )
    item_keywords = {
        name: [_keywords(desc) for desc in descriptions]
        for name, descriptions in items_by_category.items()
    }
    return {
        'rfq_stats': rfq_stats,
        'quotation_counts': quotation_counts,
        'category_counts': category_counts,
        'item_keywords': item_keywords,
    }


def _factor(name, points, max_points, explanation):
    return {
        'factor': name,
        'points': round(points, 1),
        'max_points': max_points,
        'explanation': explanation,
    }


def _responsiveness(supplier_id, context):
    stats = context['rfq_stats'].get(supplier_id) or {}
    responded = stats.get('responded', 0)
    # RFQs still inside the grace period are pending, not ignored.
    counted = stats.get('issued', 0) - stats.get('still_open', 0)
    if counted <= 0:
        return _factor(
            'RFQ responsiveness', RESPONSIVENESS_WEIGHT * NEUTRAL_RESPONSIVENESS, RESPONSIVENESS_WEIGHT,
            'No completed RFQ history yet; given a neutral score.',
        )
    rate = responded / counted
    return _factor(
        'RFQ responsiveness', RESPONSIVENESS_WEIGHT * rate, RESPONSIVENESS_WEIGHT,
        f'Responded to {responded} of {counted} previous RFQ{"s" if counted != 1 else ""} ({round(rate * 100)}%).',
    )


def _quotation_history(supplier_id, context):
    count = context['quotation_counts'].get(supplier_id, 0)
    capped = min(count, QUOTATION_HISTORY_CAP)
    if count == 0:
        explanation = 'No quotations submitted yet.'
    else:
        explanation = f'{count} quotation{"s" if count != 1 else ""} submitted on previous requests'
        explanation += f' (counted up to {QUOTATION_HISTORY_CAP}).' if count > QUOTATION_HISTORY_CAP else '.'
    return _factor(
        'Quotation history', QUOTATION_HISTORY_WEIGHT * capped / QUOTATION_HISTORY_CAP,
        QUOTATION_HISTORY_WEIGHT, explanation,
    )


def _category_focus(supplier_id, category_name, context):
    total = max(context['category_counts'].get(supplier_id, 1), 1)
    others = total - 1
    share = max(FOCUS_FLOOR, 1 - others * FOCUS_STEP_PER_EXTRA_CATEGORY)
    if others == 0:
        explanation = f'Registered only under {category_name}.'
    else:
        explanation = f'Registered under {category_name} and {others} other categor{"ies" if others != 1 else "y"}.'
    return _factor('Category focus', CATEGORY_FOCUS_WEIGHT * share, CATEGORY_FOCUS_WEIGHT, explanation)


def _item_relevance(supplier, category_name, context):
    items = [kw for kw in context['item_keywords'].get(category_name, []) if kw]
    offered = _keywords(' '.join(filter(None, (
        supplier.goods_services, supplier.products_services, supplier.nature_of_business,
    ))))
    if not offered:
        return _factor('Item relevance', 0, ITEM_RELEVANCE_WEIGHT,
                       'No goods/services description on file to compare with the items.')
    if not items:
        return _factor('Item relevance', 0, ITEM_RELEVANCE_WEIGHT,
                       'Item descriptions have no keywords to compare.')
    hits = sum(1 for kw in items if kw & offered)
    return _factor(
        'Item relevance', ITEM_RELEVANCE_WEIGHT * hits / len(items), ITEM_RELEVANCE_WEIGHT,
        f'Goods/services description mentions {hits} of {len(items)} requested item{"s" if len(items) != 1 else ""}.',
    )


def score_supplier(supplier, category_name, context):
    """Score one eligible supplier for one category group.

    Returns ``{'match_score': float, 'score_breakdown': [...]}`` where each
    breakdown entry is ``{factor, points, max_points, explanation}`` and
    ``match_score`` is the sum of the rounded points (0-100).
    """
    breakdown = [
        _responsiveness(supplier.id, context),
        _quotation_history(supplier.id, context),
        _category_focus(supplier.id, category_name, context),
        _item_relevance(supplier, category_name, context),
    ]
    return {
        'match_score': round(sum(f['points'] for f in breakdown), 1),
        'score_breakdown': breakdown,
    }


def rank_key(entry):
    """Sort key: highest score first, then company name."""
    return (-entry['match_score'], (entry.get('company_name') or '').lower())

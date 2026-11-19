"""Mode-of-procurement checks run when an RFQ is issued.

Two checks, applied only at issue (never to drafts or previews):

* **ABC ceiling** - a mode with a ``max_abc`` in PROCUREMENT_MODES (Small
  Value Procurement: P2M, Sec. 39) cannot be issued for a PR whose ABC is
  above it. The ABC is the whole PR's grand total, so a PR split into
  several category-group RFQs is still measured as one procurement.
* **Possible contract splitting** - an SVP RFQ is flagged when other PRs from
  the same requesting office, for the same category, already issued under SVP
  in the same calendar year bring the combined amount over the ceiling.
  Flagged RFQs may still be issued, but only with a written justification
  from the BAC (``MIN_JUSTIFICATION_LENGTH`` characters or more), recorded
  with who gave it, when, and the check as it stood (``record_justification``).
  When the combined amount is far above the ceiling
  (``BIDDING_ADVICE_FACTOR`` x), the warning advises Competitive Bidding;
  that advice is not enforced.
"""
from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.utils import timezone

from api.models import RFQ, PurchaseRequestItem
from api.rfq.procurement_modes import PROCUREMENT_MODES

MIN_JUSTIFICATION_LENGTH = 20
BIDDING_ADVICE_FACTOR = 2

SPLITTING_CODE = 'possible_contract_splitting'
CEILING_CODE = 'abc_exceeds_mode_ceiling'


def _peso(amount) -> str:
    return f"₱{Decimal(amount or 0):,.2f}"


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value or 0).replace('₱', '').replace('Php', '').replace(',', '').strip() or 0)
    except (InvalidOperation, ValueError):
        return Decimal(0)


def mode_rule(mode: str):
    """The PROCUREMENT_MODES entry with a ceiling that ``mode`` refers to.

    Matches the label anywhere in the stored text, case-insensitively, so a
    typed variant such as "Negotiated Procurement - Small Value Procurement"
    is still held to the SVP ceiling.
    """
    text = (mode or '').strip().lower()
    for entry in PROCUREMENT_MODES:
        if entry.get('max_abc') and entry['label'].lower() in text:
            return entry
    return None


def _mode_name(rule) -> str:
    basis = rule.get('legal_basis')
    return f"{rule['label']} ({basis})" if basis else rule['label']


def check_abc_ceiling(mode: str, abc) -> dict | None:
    """Error payload when ``abc`` is above the mode's ceiling, else None."""
    rule = mode_rule(mode)
    if not rule:
        return None
    ceiling = Decimal(rule['max_abc'])
    abc = _decimal(abc)
    if abc <= ceiling:
        return None
    return {
        'success': False,
        'code': CEILING_CODE,
        'message': (
            f"{_mode_name(rule)} is limited to an ABC of {_peso(ceiling)}. "
            f"This Purchase Request's ABC is {_peso(abc)}. Choose another mode of procurement, "
            "such as Competitive Bidding."
        ),
        'ceiling': float(ceiling),
        'abc': float(abc),
    }


def _office_key(office) -> str:
    return ' '.join((office or '').split()).lower()


def _category_amount(pr, category_name: str) -> Decimal:
    total = PurchaseRequestItem.objects.filter(
        purchase_request=pr, category__iexact=category_name,
    ).aggregate(total=Sum('total_cost'))['total']
    return Decimal(total or 0)


def find_possible_splitting(pr, category, mode: str, now=None) -> dict | None:
    """The splitting check for issuing an RFQ, or None when nothing is flagged.

    Compares like with like: the amount of this PR's items in the RFQ's
    category, plus the same category's amount on each related PR.
    """
    rule = mode_rule(mode)
    office = (pr.office_section or '').strip()
    if not rule or category is None or not office:
        return None
    now = now or timezone.now()
    ceiling = Decimal(rule['max_abc'])
    office_key = _office_key(office)

    related_rfqs = (
        RFQ.objects.exclude(purchase_request=pr)
        .exclude(status=RFQ.STATUS_DRAFT)
        .filter(
            mode_of_procurement__icontains=rule['label'],
            category__name__iexact=category.name,
            sent_at__year=now.year,
        )
        .select_related('purchase_request')
        .order_by('sent_at', 'id')
    )
    related = {}
    for rfq in related_rfqs:
        other = rfq.purchase_request
        # Office names are typed (or OCR-read), so compare them ignoring case
        # and spacing, in Python rather than with a database lookup.
        if other.id in related or _office_key(other.office_section) != office_key:
            continue
        related[other.id] = {
            'pr_id': other.id,
            'pr_no': other.pr_no or f'PR-{other.id}',
            'office_section': other.office_section or '',
            'amount': float(_category_amount(other, category.name)),
            'issued_at': rfq.sent_at.isoformat() if rfq.sent_at else None,
            'rfq_no': rfq.rfq_no or '',
        }
    if not related:
        return None

    this_amount = _category_amount(pr, category.name)
    combined = this_amount + sum(Decimal(str(row['amount'])) for row in related.values())
    if combined <= ceiling:
        return None

    advise_bidding = combined >= ceiling * BIDDING_ADVICE_FACTOR
    message = (
        f"Possible contract splitting: {len(related)} other Purchase Request"
        f"{'s' if len(related) != 1 else ''} from {office} for {category.name} "
        f"{'were' if len(related) != 1 else 'was'} already issued under {rule['label']} in {now.year}. "
        f"Together with this one, the combined amount is {_peso(combined)}, above the "
        f"{_peso(ceiling)} {rule['label']} ceiling. To issue this RFQ, the BAC must record a justification "
        f"of at least {MIN_JUSTIFICATION_LENGTH} characters."
    )
    if advise_bidding:
        message += (
            f" The combined amount is {BIDDING_ADVICE_FACTOR} times the ceiling or more; "
            "the BAC should consider Competitive Bidding instead."
        )
    return {
        'mode': rule['label'],
        'office_section': office,
        'category': category.name,
        'year': now.year,
        'ceiling': float(ceiling),
        'this_pr': {'pr_id': pr.id, 'pr_no': pr.pr_no or f'PR-{pr.id}', 'amount': float(this_amount)},
        'related': list(related.values()),
        'combined_total': float(combined),
        'advise_competitive_bidding': advise_bidding,
        'message': message,
    }


def splitting_error(check: dict, justification_problem: str = '') -> dict:
    """409 payload asking the BAC for a justification."""
    message = check['message']
    if justification_problem:
        message = f"{justification_problem} {message}"
    return {
        'success': False,
        'code': SPLITTING_CODE,
        'message': message,
        'splitting': check,
        'min_justification_length': MIN_JUSTIFICATION_LENGTH,
    }


def justification_problem(text: str) -> str:
    """Why a *provided* justification is not acceptable, or '' when it is.

    Blank text is the caller's "not provided yet" case (it shows the warning
    first) and returns ''. Whitespace runs collapse before measuring, so
    padding with spaces does not reach the minimum.
    """
    cleaned = ' '.join((text or '').split())
    if not cleaned:
        return ''
    if len(cleaned) < MIN_JUSTIFICATION_LENGTH:
        return f"The justification must be at least {MIN_JUSTIFICATION_LENGTH} characters."
    return ''


def record_justification(rfq, request, text: str, check: dict) -> list[str]:
    """Store the justification, who gave it, when, and the check at that moment.

    Returns the RFQ fields set, for ``save(update_fields=...)``.
    """
    user = getattr(request, 'auth_user', None)
    rfq.splitting_justification = ' '.join(text.split())
    rfq.splitting_justified_by = user
    rfq.splitting_justified_by_username = getattr(user, 'username', '') or ''
    rfq.splitting_justified_at = timezone.now()
    rfq.splitting_check = {key: value for key, value in check.items() if key != 'message'}
    return [
        'splitting_justification', 'splitting_justified_by', 'splitting_justified_by_username',
        'splitting_justified_at', 'splitting_check',
    ]
